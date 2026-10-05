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
    resumo = PipelineController().etl_completo(alvos)
    print(resumo)
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
    return 1


def cmd_pdf(args: argparse.Namespace) -> int:
    from workers.deck_pdf import gerar_pdf
    destino = gerar_pdf(args.saida, args.periodo)
    print(f"Slide deck PDF: {destino}")
    return 0


def cmd_email(args: argparse.Namespace) -> int:
    """Gera (ou envia) o e-mail com o gráfico anexado: HTML + PNG + CSV."""
    import os
    import webbrowser
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
    pdf = sub.add_parser("pdf")
    pdf.add_argument("--periodo", default="2026Q2")
    pdf.add_argument("--saida", default=None)
    email = sub.add_parser("email")
    email.add_argument("--para", required=True)
    email.add_argument("--rubrica", default="RECEITA_LIQUIDA")
    email.add_argument("--periodo", default="2026Q2")
    email.add_argument("--enviar", action="store_true",
                       help="envia via SMTP (sem flag: salva .eml em data/outbox)")
    email.add_argument("--sem-grafico", action="store_true",
                       help="somente CSV, sem HTML/PNG do gráfico")
    email.add_argument("--abrir", action="store_true",
                       help="abre o .eml gerado no programa de e-mail padrão")
    fontes = sub.add_parser("fontes", help="CRUD do catalogo de fontes publicas")
    fontes.add_argument("acao", choices=["list", "add", "edit", "del", "show", "api", "check"])
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
    tri = sub.add_parser("trimestre")
    tri.add_argument("--novo", default=None, help="ex.: 2026Q3")
    tri.add_argument("--pasta", default=None, help="só cria a pasta do trimestre")
    tri.add_argument("--serve", action="store_true")
    sub.add_parser("status")
    sub.add_parser("reset")
    args = parser.parse_args(argv)
    return {"full": cmd_full, "etl": cmd_etl, "web": cmd_web, "gui": cmd_gui,
            "sec": cmd_sec, "efetivo": cmd_efetivo, "coleta": cmd_coleta,
            "derivados": cmd_derivados, "powerbi": cmd_powerbi,
            "pdf": cmd_pdf, "email": cmd_email, "trimestre": cmd_trimestre,
            "fontes": cmd_fontes, "status": cmd_status, "reset": cmd_reset}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
