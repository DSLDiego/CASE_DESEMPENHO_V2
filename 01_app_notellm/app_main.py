"""app_main.py — ponto de entrada do PetroAnalytics PoC (MVC-W + SQLite + ETL).

Uso:
  python app_main.py full              # pipeline completo + painel web
  python app_main.py etl               # scan + parse + carga + auditoria
  python app_main.py web [--periodo 2026Q2] [--serve]   # gera (e serve) o painel
  python app_main.py gui               # interface desktop PySide6
  python app_main.py sec               # coleta SEC EDGAR (requer internet)
  python app_main.py status            # resumo do banco
  python app_main.py reset             # limpa o banco (cuidado)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import PERIODS, WEB_HTML  # noqa: E402
from controllers import AnalyticsController, PipelineController, SourceController  # noqa: E402
from models.database import DatabaseManager  # noqa: E402


def cmd_full(_: argparse.Namespace) -> int:
    print("== PetroAnalytics PoC: pipeline completo ==")
    pipe = PipelineController()
    resumo = pipe.etl_completo()
    print(f"scan: {resumo['scan']}")
    print(f"processados={resumo['arquivos_processados']} extracoes={resumo['extracoes']} "
          f"cargas={resumo['cargas']} revisao={resumo['revisao']} pdfs_pulados={resumo['pulados_pdf']}")
    print(f"auditoria: {resumo['auditoria']}")
    cmd_efetivo(argparse.Namespace())
    cmd_derivados(argparse.Namespace())
    return cmd_web(argparse.Namespace(periodo="2026Q2", serve=False))


def cmd_etl(args: argparse.Namespace) -> int:
    from config import PERIODS
    alvos = set(PERIODS) | set(args.extra or [])
    ctl = PipelineController()
    if getattr(args, "novos", False):
        print("== ETL incremental: varredura do Container + somente arquivos novos ==")
        resumo = ctl.etl_incremental(alvos, jobs=getattr(args, "jobs", None))
        scan = resumo.get("scan", {})
        print(f"Inventario: {scan.get('novos', 0)} novo(s), "
              f"{scan.get('duplicados', 0)} duplicado(s) por hash, {scan.get('erros', 0)} erro(s)")
        print(f"Processados: {resumo.get('arquivos_processados', 0)} | "
              f"cargas: {resumo.get('cargas', 0)} | revisao: {resumo.get('revisao', 0)}"
              f" | parse em {resumo.get('jobs', 1)} processo(s)")
        if not scan.get("novos", 0) and not resumo.get("arquivos_processados", 0):
            print("Nada novo no Container e nada aguardando parse: nada a fazer.")
        elif not scan.get("novos", 0):
            print("Sem arquivo novo, mas havia documento baixado ainda não processado.")
    else:
        resumo = ctl.etl_completo(alvos)
        print(resumo)
    return 0


def cmd_descoberta(args: argparse.Namespace) -> int:
    """Acha o que foi anunciado (SEC/RI) e ainda nao esta no acervo."""
    from workers.discovery import resumo_texto
    site = (args.site or "all").upper()
    dados = PipelineController().descoberta(
        periodo=args.periodo, incluir_sec=site in ("ALL", "SEC"),
        incluir_ri=site in ("ALL", "RI"), registrar=not args.sem_registrar,
        baixar=args.baixar,
        empresas=args.empresa or None)
    if args.json:
        print(json.dumps(dados, ensure_ascii=False, indent=2))
        return 0
    print(resumo_texto(dados))
    lacunas = sum(len(r["lacunas"]) for r in dados["empresas"])
    if lacunas and site in ("ALL", "SEC"):
        print("\nDica: XBRL do trimestre so aparece depois da publicacao. "
              " Rode de novo em novembro.")
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    from views.web_app import build_dashboard
    destino = build_dashboard(args.periodo)
    print(f"Painel gerado: {destino}")
    insight = AnalyticsController().insight_executivo(args.periodo)
    print(f"Leitura executiva [{args.periodo}]: {insight}")
    if args.serve:
        from views.web_server import serve
        print(f"Servindo em http://localhost:8080/{WEB_HTML.name} (API CRUD: /api/fontes)")
        return serve(WEB_HTML.parent)
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    from views.gui_app import BenchmarkGUI
    return BenchmarkGUI(periodo=args.periodo).run()


def cmd_sec(args: argparse.Namespace) -> int:
    from config import COMPANIES
    from models.repositories import FatoRepository, FonteRepository, QualityRepository
    from workers.sec_edgar import BASE, collect_empresa
    fatos = FatoRepository()
    fontes = FonteRepository()
    quality = QualityRepository()
    periodos = set(getattr(args, "periodos", None) or PERIODS) | set(PERIODS)
    total = 0
    for empresa, meta in COMPANIES.items():
        try:
            exts = collect_empresa(meta["cik"], empresa, periodos)
        except Exception as exc:
            print(f"[SEC] {empresa}: falha ({exc})")
            continue
        url = BASE.format(cik=meta["cik"].zfill(10))
        id_fonte = fontes.registrar(empresa, url, "JSON", None, meta["cik"], "PROCESSADO")
        for ext in exts:
            atual = fatos.obter(empresa, ext.periodo, ext.rubrica)
            if atual and atual.get("valor"):
                base = abs(atual["valor"])
                div = abs(ext.valor - atual["valor"]) / base if base else 0.0
                if div > 0.15:
                    quality.alertar("tb_fato_financeiro", 0, "DIVERGENCIA_FONTE",
                                    f"{ext.rubrica} {empresa} {ext.periodo}: RI={atual['valor']:.2f} "
                                    f"x SEC={ext.valor:.2f} ({div:.0%})", "MEDIUM")
                continue  # RI (fonte primaria) nunca e sobrescrita pela SEC
            fatos.upsert_financeiro(empresa, ext.periodo, ext.rubrica, ext.valor,
                                    "USD", id_fonte, ext.confianca)
            total += 1
        print(f"[SEC] {empresa}: {len(exts)} fatos XBRL.")
    print(f"Total SEC: {total} cargas.")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    db = DatabaseManager()
    from models.repositories import FatoRepository
    cont = FatoRepository(db).contar()
    print(f"fontes={cont['fontes']} fatos={cont['fatos']} operacionais={cont['operacionais']}")
    for periodo in PERIODS:
        print(f"[{periodo}] {AnalyticsController(db).insight_executivo(periodo)}")
    fontes = SourceController(db).catalogo()[:5]
    for fnt in fontes:
        print(f"  #{fnt['id_fonte']} {fnt['nome_empresa']} {fnt['tipo_arquivo']} {fnt['status_processamento']}")
    return 0


def cmd_reset(_: argparse.Namespace) -> int:
    DatabaseManager().reset()
    print("Banco reiniciado.")
    return 0


def cmd_efetivo(_: argparse.Namespace) -> int:
    from models.seed_efetivo import aplicar
    print(f"Ancoras de efetivo aplicadas: {aplicar()} cargas.")
    return 0


def cmd_derivados(_: argparse.Namespace) -> int:
    from workers.derived import compute_derived
    print(compute_derived())
    return 0


def cmd_powerbi(_: argparse.Namespace) -> int:
    from pathlib import Path
    import csv as _csv
    from models.database import DatabaseManager
    destino = Path("data/powerbi")
    destino.mkdir(parents=True, exist_ok=True)
    db = DatabaseManager()
    with db.connect() as conn:
        tabelas = {
            "fatos_financeiros": "SELECT * FROM tb_fato_financeiro",
            "fatos_operacionais": "SELECT * FROM tb_fato_operacional",
            "fontes": "SELECT * FROM tb_fonte_dados",
            "alertas_qualidade": "SELECT * FROM tb_quality_alerts",
            "fila_revisao": "SELECT * FROM tb_review_queue",
        }
        for nome, query in tabelas.items():
            rows = conn.execute(query).fetchall()
            caminho = destino / f"{nome}.csv"
            with open(caminho, "w", newline="", encoding="utf-8-sig") as fh:
                writer = _csv.writer(fh, delimiter=";")
                if rows:
                    writer.writerow(rows[0].keys())
                    writer.writerows([tuple(r) for r in rows])
            print(f"{nome}.csv: {len(rows)} linhas")
    (destino / "LEIAME.txt").write_text(
        "Importe os CSVs no Power BI (delimitador ';').\n"
        "Relacione fatos_financeiros[id_fonte] -> fontes[id_fonte].\n"
        "Ordene periodo como texto YYYYQn.\n", encoding="utf-8")
    return 0


MKT_MAP = {"COTACAO": ("COTACAO", None),  # moeda vem do snapshot (_MOEDA)
           "P/L": ("P_L", "x"),
           "DY": ("DIVIDEND_YIELD", "%")}


def cmd_coleta(args: argparse.Namespace) -> int:
    from config import COMPANIES
    from workers.ri_collector import I10_SITES, RI_SITES, collect_site, trimestre_corrente
    from models.repositories import FatoRepository, FonteRepository
    from models.database import DatabaseManager
    db = DatabaseManager()
    repo, fatos = FonteRepository(db), FatoRepository(db)
    if args.site == "RI":
        alvos = [(e, "RI") for e in RI_SITES]
    elif args.site == "I10":
        alvos = [(e, "I10") for e in I10_SITES]
    elif args.site == "all":
        alvos = [(e, "RI") for e in RI_SITES] + [(e, "I10") for e in I10_SITES]
    else:
        alvos = [(args.site, "RI" if args.site in RI_SITES else "I10")]
    total_links, total_mkt = 0, 0
    for empresa, origem in alvos:
        resumo = collect_site(empresa, origem, baixar=args.baixar, repo=repo)
        if resumo["erro"] and not resumo["links"]:
            print(f"[{origem}] {empresa}: {resumo['erro']}")
            continue
        total_links += len(resumo["links"])
        print(f"[{origem}] {empresa}: {len(resumo['links'])} docs, "
              f"{len(resumo['downloads'])} downloads"
              + (f", erro: {resumo['erro']}" if resumo["erro"] else ""))
        if origem == "I10" and args.mercado and resumo["snapshot"]:
            per = trimestre_corrente()
            idf = repo.registrar(empresa, I10_SITES[empresa], "HTML", None,
                                 COMPANIES.get(empresa, {}).get("cik"), "PROCESSADO")
            for rot, val in resumo["snapshot"].items():
                if rot in MKT_MAP and rot != "_MOEDA":
                    ind, uni = MKT_MAP[rot]
                    if rot == "COTACAO":
                        uni = {"US$": "USD", "R$": "BRL"}.get(resumo["snapshot"].get("_MOEDA", ""), uni or "")
                    fatos.upsert_operacional(empresa, per, ind, val, uni or "", idf)
                    total_mkt += 1
    print(f"Total: {total_links} links, {total_mkt} snapshots de mercado.")
    return 0


def cmd_qualidade(args: argparse.Namespace) -> int:
    """Gestao e controle de qualidade e rastreabilidade (M7)."""
    from workers.quality_score import painel_qualidade, run_quality_score
    if args.acao == "rodar":
        r = run_quality_score()
        print(f"DQS medio: {r['dqs_medio']} · scorecards: {r['cards']} "
              f"· desvios: {r['desvios']} (novos {r['alertas_novos']})")
        print(f"dimensoes: {r['por_dimensao']}")
        print(f"classificacao: {r['classificacao']}")
        print(f"fila de analise: {r['fila']} (P1={r['p1']} P2={r['p2']} P3={r['p3']})")
        for p in r["pior"]:
            print(f"  pior: {p['nome_empresa']} {p['periodo']} DQS={p['dqs']} {p['classificacao']}")
        return 0
    p = painel_qualidade()
    if args.acao == "resumo":
        print(f"empresas={p['resumo']['empresas']} periodos={p['resumo']['periodos']} "
              f"DQS={p['resumo']['dqs_medio']} class={p['resumo']['classificacao']}")
        print(f"dimensoes: {p['resumo']['por_dimensao']}")
        return 0
    if args.acao == "fila":
        for i in p["fila"][: args.limite]:
            print(f"  {i['prioridade']} {i['codigo']:<24}{i['empresa']:<14}{i['periodo']:<9}"
                  f"{i['motivo'][:70]}")
        return 0
    if args.acao == "historico":
        from workers.quality_score import historico_scorecard
        from models.database import DatabaseManager as _DB
        h = historico_scorecard(_DB(), args.empresa)
        if not h["empresas"]:
            print("sem historico: rode `qualidade rodar` para gravar a primeira serie.")
            return 1
        print(f"DQS medio {h['dqs_inicial']} -> {h['dqs_atual']} "
              f"({h['variacao_media']:+}) em {len(h['periodos'])} periodo(s)")
        for m in h["media_por_periodo"]:
            print(f"  {m['periodo']}  DQS {m['dqs_medio']:>5}  ({m['empresas']} empresas)")
        for v in h["por_empresa"].values():
            print(f"  {v['empresa']:<14} {v['dqs_inicial']:>5} -> {v['dqs_atual']:>5} "
                  f"({v['variacao_total']:+}) {v['classificacao_atual']}")
        return 0
    if args.acao == "regras":
        for r in p["regras"]:
            print(f"  {r['codigo']:<26}{r['limiar']:>6}  {r['severidade']:<7}{r['descricao']}")
        return 0
    print("acoes: rodar | resumo | fila | regras | historico")
    return 1


def cmd_forecast(args: argparse.Namespace) -> int:
    """Projecao estatistica (M3): grava em tb_projecao e mostra o resumo."""
    from workers.forecast_run import run_forecast
    horizonte = max(1, min(args.horizonte, 3))
    print(f"== Projecao estatistica (horizonte {horizonte} trimestre(s)) ==")
    print("metodo: 1 dado -> repete ±15% · 2-5 dados -> média ±2 desvios-padrão · "
          ">=6 dados -> backtesting (Sazonal-Naive, Holt-Winters damped, "
          "Ultima-Observacao) com IC95 pela dispersao dos erros.")
    resumo = run_forecast(horizonte=horizonte,
                          empresas=[args.empresa] if args.empresa else None,
                          rubricas=[args.rubrica] if args.rubrica else None)
    print(f"series projetadas: {resumo['series']} · projecoes gravadas: {resumo['projecoes']}"
          f" · series ignoradas: {resumo['ignoradas']}")
    print(f"metodos: {resumo['metodos']} · confianca media: {resumo['confianca_media']}")
    for aviso in resumo["avisos"][:10]:
        print(f"  aviso: {aviso}")
    return 0


def cmd_auditoria(args: argparse.Namespace) -> int:
    """Gestao e controle da auditoria: KPIs, fila e triagem."""
    from models.repositories import QualityRepository
    q = QualityRepository()
    if args.acao == "resumo":
        r = q.resumo_auditoria()
        print(f"alertas: {r['total_alertas']} · fila: {r['fila_total']} "
              f"(abertas {r['fila_aberta']}) · triagem: {r['triagem']}")
        print(f"severidade: {r['por_severidade']}")
        print(f"aging: {r['aging']} · taxa de resolucao: {r['taxa_resolucao']}%")
        for tipo, n in list(r["por_tipo"].items())[:8]:
            print(f"  {tipo}: {n}")
        return 0
    if args.acao == "fila":
        for r in q.listar_revisao(apenas_abertos=not args.todas)[: args.limite]:
            print(f"  #{r['id_review']:<5} {r['nome_empresa']:<14} {r['periodo']:<8} "
                  f"{r['rubrica']:<22} {r['status']:<10} {r['motivo'][:60]}")
        return 0
    if args.acao == "decidir":
        if not args.id or not args.decisao:
            print("uso: auditoria decidir --id 12 --decisao ACEITO [--comentario '...']")
            return 1
        q.decidir("tb_review_queue", args.id, args.decisao.upper(), args.comentario)
        print(f"registro #{args.id} -> {args.decisao.upper()}")
        return 0
    if args.acao == "reabrir":
        if not args.id:
            print("uso: auditoria reabrir --id 12 [--comentario '...']")
            return 1
        ok = q.reabrir("tb_review_queue", args.id, args.comentario)
        print(f"registro #{args.id} -> {'reaberto (voltou para PENDENTE)' if ok else 'nao estava decidido'}")
        return 0 if ok else 1
    if args.acao == "decisoes":
        from workers.relatorio_auditoria import decisoes_periodo
        linhas = decisoes_periodo(q.db, args.de, args.ate)
        print(f"{len(linhas)} decisao(oes) em {args.de or 'inicio'}..{args.ate or 'hoje'}")
        for d in linhas[: args.limite]:
            print(f"  {d['decidido_em']}  {d['decisao']:<10} "
                  f"{(d['nome_empresa'] or '(alerta)'):<14} {(d['periodo'] or '-'):<9}"
                  f"{(d['rubrica'] or '-'):<22} por {d['decidido_por']}")
        return 0
    if args.acao == "relatorio":
        from controllers import SourceController
        r = SourceController(q.db).relatorio_auditoria(args.de, args.ate, args.saida)
        print(f"Relatorio de auditoria PDF: {r['arquivo']}")
        return 0
    print("acoes: resumo | fila | decidir | reabrir | decisoes | relatorio")
    return 1


def cmd_fontes(args: argparse.Namespace) -> int:
    """CRUD do sub-sistema de gestao de fontes publicas."""
    ctrl = SourceController()
    acao = args.acao
    if acao == "list":
        ctrl.complementar_campos()
        for f in ctrl.catalogo()[: args.limite]:
            print(f"#{f['id_fonte']:<5} {f['nome_empresa']:<14} {(f['extensao'] or ''):<6}"
                  f" {(f['nome_documento'] or '')[:38]:<40} {f['data_download'] or ''}"
                  f" api={f['api_json'] or '-'}")
        return 0
    if acao == "add":
        novo = ctrl.registrar_manual(args.empresa, args.url, args.tipo, args.caminho,
                                     args.nome, args.api_json)
        print(f"Fonte #{novo} registrada.")
        return 0
    if acao == "edit":
        campos = {k: v for k, v in (("nome_empresa", args.empresa), ("url_fonte", args.url),
                                    ("tipo_arquivo", args.tipo), ("caminho_local", args.caminho),
                                    ("nome_documento", args.nome), ("api_json", args.api_json),
                                    ("status_processamento", args.status),
                                    ("cik", args.cik)) if v}
        print("Atualizado." if ctrl.atualizar(args.id, **campos) else "id_fonte inexistente.")
        return 0
    if acao == "del":
        print("Excluida." if ctrl.excluir(args.id) else "id_fonte inexistente.")
        return 0
    if acao == "show":
        fonte = ctrl.obter(args.id)
        print(json.dumps(fonte, indent=2, ensure_ascii=False) if fonte else "id_fonte inexistente.")
        return 0
    if acao == "api":
        resultado = ctrl.escanear_api_json()
        for r in resultado["relatorio"]:
            print(f"  {r['nome_empresa']:<14} {r['fonte']:<15} {r['status']:<12} {r['detalhe']}")
        print(resultado["resumo"])
        return 0
    if acao == "check":
        faltantes = ctrl.integridade()
        print(f"Arquivos locais ausentes: {len(faltantes)}")
        for f in faltantes[:20]:
            print(f"  #{f['id_fonte']} {f['caminho_local']}")
        return 0
    if acao == "metrica":
        # M8.12: mede páginas/tabelas dos PDFs que ainda não têm métrica
        from workers.pdf_metrics import medir_metricas_pdf
        r = medir_metricas_pdf(limite=args.limite if args.limite != 50 else None,
                               jobs=args.jobs, verbose=True)
        print(f"medidos={r['medidos']} paginas={r['paginas']} tabelas={r['tabelas']} "
              f"sem_arquivo={r['sem_arquivo']} restantes={r['restantes']} "
              f"({r['jobs']} processo(s))")
        p = SourceController().resumo_etl()["pdf"]
        print(f"painel ETL: {p['documentos']} PDFs · {p['paginas_lidas']} páginas lidas · "
              f"{p['paginas_por_seg']} pág/s · {p['tabelas']} tabelas")
        return 0
    return 1


def cmd_pdf(args: argparse.Namespace) -> int:
    if getattr(args, "pptx", False):
        from workers.apresentacao_pptx import construir
        destino = construir(args.saida)
        print(f"Apresentacao PPTX: {destino}")
        return 0
    from workers.deck_pdf import gerar_pdf
    destino = gerar_pdf(args.saida, args.periodo)
    print(f"Slide deck PDF: {destino}")
    return 0


def cmd_email(args: argparse.Namespace) -> int:
    """Gera (ou envia) o e-mail com o gráfico anexado: HTML + PNG + CSV."""
    import os
    import webbrowser
    if args.alerta:  # M7.25: e-mail de ALERTAS P1 da fila de qualidade
        from workers.mailer import alertar_p1
        rota = alertar_p1(args.para, dry_run=not args.enviar)
        if rota is None:
            print("sem alertas P1 abertos — nenhum e-mail gerado.")
            return 0
        print(("ENVIADO para" if args.enviar else "e-mail de alerta gerado em"), rota)
        return 0
    from controllers import MailController
    try:
        r = MailController().enviar(args.para, args.rubrica, args.periodo,
                                    enviar_real=args.enviar, anexos=not args.sem_grafico)
    except ValueError as exc:
        print(f"erro: {exc}")
        return 1
    print(f"{'ENVIADO para' if r['enviado'] else 'e-mail gerado em'} {r['resultado']}")
    print(f"assunto: {r['assunto']}")
    print(f"anexos : {', '.join(r['anexos'])}")
    if not r["enviado"]:
        print("dica: abrir o .eml e anexar/encaminhar, ou use --enviar com SMTP_* no env.")
        if args.abrir and os.path.exists(r["resultado"]):
            webbrowser.open(Path(r["resultado"]).as_uri())
    return 0


def cmd_trimestre(args: argparse.Namespace) -> int:
    """Automacao trimestral: prepara pasta, ETL, SEC, derivados, painel e docs."""
    from pathlib import Path
    if args.pasta:
        Path(args.pasta).mkdir(parents=True, exist_ok=True)
        print(f"Pasta do trimestre: {args.pasta} (copie os PDFs/XLSXs e rode sem --pasta)")
        return 0
    print(f"== Atualizacao {args.novo} ==")
    cmd_etl(argparse.Namespace(extra=[args.novo]))
    cmd_sec(argparse.Namespace())
    cmd_efetivo(argparse.Namespace())
    cmd_derivados(argparse.Namespace())
    cmd_powerbi(argparse.Namespace())
    from workers.docsgen import gerar_catalogo, gerar_evidencias
    print(gerar_catalogo())
    print(gerar_evidencias())
    return cmd_web(argparse.Namespace(periodo=args.novo, serve=args.serve))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PetroAnalytics PoC")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("full")
    etl = sub.add_parser("etl")
    etl.add_argument("--extra", nargs="*", default=[],
                     help="periodos adicionais p/ preencher historico (ex.: 2024Q2)")
    etl.add_argument("--novos", action="store_true",
                     help="incremental: varre o Container e processa SO os arquivos novos")
    etl.add_argument("--jobs", type=int, default=None,
                     help="processos para o parse (padrao: automatico, 1 = serial)")
    web = sub.add_parser("web")
    web.add_argument("--periodo", default="2026Q2")
    web.add_argument("--serve", action="store_true")
    gui = sub.add_parser("gui")
    gui.add_argument("--periodo", default="2026Q2")
    sec = sub.add_parser("sec")
    sec.add_argument("--periodos", nargs="*", default=None,
                     help="periodos extras p/ historico (ex.: 2023Q1 2024Q4)")
    sub.add_parser("efetivo")
    sub.add_parser("derivados")
    sub.add_parser("powerbi")
    coleta = sub.add_parser("coleta")
    coleta.add_argument("--site", default="all",
                        help="all|RI|I10 ou nome da empresa (ex.: PETROBRAS)")
    coleta.add_argument("--baixar", action="store_true",
                        help="baixa os documentos descobertos (com dedup)")
    coleta.add_argument("--mercado", action="store_true",
                        help="carrega snapshot Investidor10 no banco")
    descoberta = sub.add_parser("descoberta",
                             help="acha o que foi anunciado (SEC/RI) e ainda nao esta no acervo")
    descoberta.add_argument("--periodo", default=None,
                            help="trimestre alvo (padrao: o que se espera agora, ex.: 2026Q3)")
    descoberta.add_argument("--site", default="all", choices=["all", "sec", "ri"],
                            help="canal de descoberta")
    descoberta.add_argument("--empresa", nargs="*", default=None,
                            help="restringe a empresas (ex.: PETROBRAS BP)")
    descoberta.add_argument("--baixar", action="store_true",
                            help="baixa os documentos novos para data/downloads")
    descoberta.add_argument("--sem-registrar", action="store_true",
                            help="apenas relata: nao grava no catalogo de fontes")
    descoberta.add_argument("--json", action="store_true", help="saida em JSON")
    pdf = sub.add_parser("pdf", help="deck executivo (PDF) ou apresentacao (PPTX)")
    pdf.add_argument("--periodo", default="2026Q2")
    pdf.add_argument("--saida", default=None)
    pdf.add_argument("--pptx", action="store_true",
                     help="gera a apresentacao em PowerPoint (padrao: deck em PDF)")
    email = sub.add_parser("email")
    email.add_argument("--para", required=True)
    email.add_argument("--alerta", action="store_true",
                       help="M7.25: envia o e-mail de ALERTAS P1 da fila de qualidade")
    email.add_argument("--rubrica", default="RECEITA_LIQUIDA")
    email.add_argument("--periodo", default="2026Q2")
    email.add_argument("--enviar", action="store_true",
                       help="envia via SMTP (sem flag: salva .eml em data/outbox)")
    email.add_argument("--sem-grafico", action="store_true",
                       help="somente CSV, sem HTML/PNG do gráfico")
    email.add_argument("--abrir", action="store_true",
                       help="abre o .eml gerado no programa de e-mail padrão")
    fontes = sub.add_parser("fontes", help="CRUD e gestao do catalogo de fontes")
    fontes.add_argument("acao", choices=["list", "add", "edit", "del", "show", "api",
                                        "check", "metrica"])
    fontes.add_argument("--jobs", type=int, default=None,
                        help="processos para medir (metrica); padrao: automatico")
    fontes.add_argument("id", nargs="?", type=int, help="id_fonte (edit/del/show)")
    fontes.add_argument("--empresa", default=None)
    fontes.add_argument("--url", default=None)
    fontes.add_argument("--tipo", default="PDF", help="PDF|XLSX|XLSM|CSV|TXT|DOCX|JSON")
    fontes.add_argument("--caminho", default=None, help="pasta/arquivo local do app")
    fontes.add_argument("--nome", default=None, help="nome do documento")
    fontes.add_argument("--api-json", dest="api_json", default=None,
                        help="URL do servico JSON publico da fonte")
    fontes.add_argument("--status", default=None)
    fontes.add_argument("--cik", default=None)
    fontes.add_argument("--limite", type=int, default=50)
    qa = sub.add_parser("qualidade", help="gestao e controle de qualidade (M7)")
    qa.add_argument("acao", choices=["rodar", "resumo", "fila", "regras", "historico"])
    qa.add_argument("--limite", type=int, default=25)
    qa.add_argument("--empresa", default=None, help="filtra o historico por empresa")
    fc = sub.add_parser("projecao", help="projecao estatistica (M3) ate 3 trimestres")
    fc.add_argument("--horizonte", type=int, default=3)
    fc.add_argument("--empresa", default=None)
    fc.add_argument("--rubrica", default=None)
    aud = sub.add_parser("auditoria", help="gestao e controle da auditoria (M2)")
    aud.add_argument("acao", choices=["resumo", "fila", "decidir", "reabrir",
                                      "decisoes", "relatorio"])
    aud.add_argument("--de", default=None, help="inicio do periodo (YYYY-MM-DD)")
    aud.add_argument("--ate", default=None, help="fim do periodo (YYYY-MM-DD)")
    aud.add_argument("--saida", default=None, help="caminho do PDF (relatorio)")
    aud.add_argument("--id", type=int, default=None, help="id_review (para decidir)")
    aud.add_argument("--decisao", default=None,
                    help="aceito | rejeitado | ignorado (não diferencia maiúsculas)")
    aud.add_argument("--comentario", default=None)
    aud.add_argument("--todas", action="store_true", help="inclui itens ja decididos")
    aud.add_argument("--limite", type=int, default=30)
    tri = sub.add_parser("trimestre")
    tri.add_argument("--novo", default=None, help="ex.: 2026Q3")
    tri.add_argument("--pasta", default=None, help="só cria a pasta do trimestre")
    tri.add_argument("--serve", action="store_true")
    sub.add_parser("status")
    sub.add_parser("reset")
    args = parser.parse_args(argv)
    return {"full": cmd_full, "etl": cmd_etl, "web": cmd_web, "gui": cmd_gui,
            "sec": cmd_sec, "efetivo": cmd_efetivo, "coleta": cmd_coleta,
    "descoberta": cmd_descoberta,
            "derivados": cmd_derivados, "powerbi": cmd_powerbi,
            "pdf": cmd_pdf, "email": cmd_email, "trimestre": cmd_trimestre,
            "fontes": cmd_fontes, "status": cmd_status, "reset": cmd_reset,
            "projecao": cmd_forecast, "auditoria": cmd_auditoria,
            "qualidade": cmd_qualidade}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
