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


def _garantir_ambiente() -> int:
    """Checa Python >= 3.10 e libs do requirements antes de rodar o ETL.

    Se faltarem bibliotecas, tenta instalar; se o Python for insuficiente ou
    a instalação falhar, ainda devolve 2 (o ETL que não roda).
    """
    import subprocess
    check = Path(__file__).with_name("check_env.py")
    try:
        r = subprocess.run([sys.executable, str(check)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=120)
    except Exception as exc:  # noqa: BLE001
        print(f"aviso: não foi possível verificar o ambiente ({exc}); seguindo mesmo assim")
        return 0
    print(r.stdout)
    if r.returncode == 0:
        return 0
    if r.returncode == 1:  # Python insuficiente: não dá para seguir
        print("ETL cancelado: versão de Python insuficiente (exige >= 3.10).")
        return 2
    print("Ambiente incompleto — tentando instalar o que falta...")
    try:
        r2 = subprocess.run([sys.executable, str(check), "--instalar"],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=600)
        print(r2.stdout)
        if r2.returncode == 0:
            return 0
        print("Instalação incompleta: rode `python check_env.py --instalar` manualmente.")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"falha na auto-instalação: {exc}")
        return 2


def cmd_etl(args: argparse.Namespace) -> int:
    rc = _garantir_ambiente()
    if rc == 2:
        print("ETL cancelado: corrija o ambiente e rode de novo.")
        return 2
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
    """Acha o que foi anunciado (SEC/RI) e ainda nao esta no acervo.

    `--etl` fecha o ciclo em uma tacada: descobre, baixa o que falta e roda o
    ETL incremental sobre o que acabou de chegar. Sem isso, o usuário via a
    lista de documentos faltando e tinha que lembrar de duas outras comandos
    (`descoberta --baixar` + `etl --novos`) para o dado virar fato.
    """
    from workers.discovery import resumo_texto
    site = (args.site or "all").upper()
    quer_etl = bool(getattr(args, "etl", False))
    if quer_etl and args.sem_registrar:
        print("--etl precisa das fontes registradas no catálogo: "
              "não combine com --sem-registrar.", file=sys.stderr)
        return 2
    dados = PipelineController().descoberta(
        periodo=args.periodo, incluir_sec=site in ("ALL", "SEC"),
        incluir_ri=site in ("ALL", "RI"), registrar=not args.sem_registrar,
        baixar=args.baixar, empresas=args.empresa or None,
        etl=quer_etl, jobs=getattr(args, "jobs", None))
    if args.json:
        print(json.dumps(dados, ensure_ascii=False, indent=2))
        return 0
    print(resumo_texto(dados))
    if "downloads" in dados:
        baixados = sum(1 for d in dados["downloads"] if d.get("arquivo"))
        falhas = len(dados["downloads"]) - baixados
        print(f"\nDownloads: {baixados} arquivo(s) em data/downloads"
              + (f" · {falhas} com problema (URL morta/bloqueio)" if falhas else ""))
    if "etl" in dados:
        r = dados["etl"]
        print("\n== ETL incremental sobre o que acabou de baixar ==")
        print(f"processados: {r.get('arquivos_processados', 0)} · "
              f"cargas: {r.get('cargas', 0)} · revisão: {r.get('revisao', 0)} · "
              f"erros: {r.get('erros', 0)} · não baixados: {r.get('nao_baixados', 0)}")
        prov = r.get("proveniencia") or {}
        if prov and not prov.get("erro"):
            print(f"procedência: {prov.get('financeiro', 0)} fato(s) financeiro(s), "
                  f"{prov.get('operacional', 0)} operacional(is) — "
                  "níveis em `qualidade proveniencia`")
        print("próximo passo: `python app_main.py web --periodo <trimestre> --serve`")
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
        porta = getattr(args, "porta", None) or 8080
        abrir = not getattr(args, "sem_abrir", False)
        print(f"Servindo em http://localhost:{porta}/{WEB_HTML.name} "
              f"(API CRUD: /api/fontes)")
        return serve(WEB_HTML.parent, porta=porta, abrir=abrir)
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    from views.gui_app import BenchmarkGUI
    return BenchmarkGUI(periodo=args.periodo).run()


def cmd_sec(args: argparse.Namespace) -> int:
    from models.repositories import CikRepository, FatoRepository, FonteRepository, QualityRepository
    from workers.sec_edgar import BASE, cik_da_empresa, collect_empresa
    fatos = FatoRepository()
    fontes = FonteRepository()
    quality = QualityRepository()
    # chaves CIK em vigor vêm do banco (gestao de chaves): as que o usuário
    # gravou mandam sobre o config; empresas novas sem chave ficam de fora
    repositorio_cik = CikRepository()
    repositorio_cik.seed()
    empresas = [c["nome_empresa"] for c in repositorio_cik.listar() if c["ativo"]]
    if getattr(args, "empresa", None):
        pedidas = {e.upper() for e in args.empresa}
        empresas = [e for e in empresas if e in pedidas]
    periodos = set(getattr(args, "periodos", None) or PERIODS) | set(PERIODS)
    total = 0
    for empresa in empresas:
        cik = cik_da_empresa(empresa)
        if not cik:
            print(f"[SEC] {empresa}: sem chave CIK cadastrada (`cik set --empresa {empresa}`).")
            continue
        try:
            exts = collect_empresa(cik, empresa, periodos)
        except Exception as exc:
            print(f"[SEC] {empresa}: falha ({exc})")
            continue
        url = BASE.format(cik=cik.zfill(10))
        id_fonte = fontes.registrar(empresa, url, "JSON", None, cik, "PROCESSADO")
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
    if args.acao == "limiar":
        from controllers import SourceController
        ctrl = SourceController()
        if args.codigo and args.limiar is not None:
            r = ctrl.limiar_regra(args.codigo, args.limiar, args.empresa, args.rubrica)
            print(f"{r['codigo']}: limiar {r['limiar_padrao']} -> {r['limiar_efetivo']} "
                  f"(empresa={r['empresa'] or 'todas'}, rubrica={r['rubrica'] or 'todas'})")
            return 0
        from workers.quality_score import listar_limiares, REGRAS
        from models.database import DatabaseManager as _DB
        excecoes = listar_limiares(_DB())
        if not excecoes:
            print("nenhuma excecao calibrada — todos os limiares sao os globais:")
            for codigo, regra in REGRAS.items():
                print(f"  {codigo:<26}{regra['limiar']:>6}  {regra['descricao']}")
            return 0
        print(f"{len(excecoes)} excecao(oes) calibrada(s) (M7.22):")
        for e in excecoes:
            print(f"  {e['codigo']:<26}{e['limiar']:>6}  "
                  f"empresa={e['empresa'] or '*'} rubrica={e['rubrica'] or '*'}")
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
    if args.acao == "proveniencia":
        from controllers import SourceController
        r = SourceController().proveniencia(args.empresa, args.periodo,
                                            reanotar=args.reanotar)
        rs = r["resumo"]
        if args.reanotar:
            a = r["anotado"]
            print(f"reclassificados: {a['financeiro']} financeiros, {a['operacional']} "
                  f"operacionais ({a['primario']} primario, {a['secundario']} secundario, "
                  f"{a['derivado']} derivados)")
        print(f"fatos classificados: {rs['total']} | score medio de proveniencia: "
              f"{rs['score_medio']}")
        for n in rs["por_nivel"]:
            print(f"  nivel {n['profundidade']} {n['rotulo']:<12} score {n['score']:<4}"
                  f" {n['fatos']:>6} fatos ({n['pct']}%)")
        print("\nrubricas mais fracas primeiro (score menor pesa mais na analise):")
        for r_ in r["rubricas"][:10]:
            print(f"  {r_['rubrica']:<26}{r_['fatos']:>5} fatos  prof {r_['profundidade']:<4}"
                  f" score {r_['score']:<4} conf {r_['confianca']}")
        if "cadeia" in r:
            print(f"\ntrilha de {r['empresa']} em {r['periodo']}:")
            for i in r["cadeia"]:
                print(f"  {i['item']:<26}{i['valor']:>10} {i['moeda']:<5}"
                      f" prof {str(i['profundidade']):<3} {i['rotulo']:<12} | {i['cadeia']}")
        else:
            print("\nDica: de a trilha completa de um trimestre com "
                  "`--empresa PETROBRAS --periodo 2026Q2`.")
        return 0
    print("acoes: rodar | resumo | fila | regras | historico | proveniencia")
    return 1


def cmd_forecast(args: argparse.Namespace) -> int:
    """Projecao estatistica (M3): grava em tb_projecao e mostra o resumo."""
    if args.cenarios:
        from controllers import ForecastController
        emp = args.empresa or "PETROBRAS"
        rub = args.rubrica or "RECEITA_LIQUIDA"
        r = ForecastController().cenarios_macro(emp, rub, horizonte=max(1, min(args.horizonte, 3)))
        if r.get("erro"):
            print(f"sem cenario: {r['erro']}")
            return 1
        s = r["sensibilidade"]
        print(f"== Cenarios Brent/FX — {emp}/{rub} ==")
        print(f"sensibilidade: beta_brent={s['beta_brent']:+.3f} beta_ptax={s['beta_ptax']:+.3f} "
              f"({s['pares']} pares; {s['motivo']}) · cov(brent,ptax)={s['cov_brent_ptax']:+.6f}")
        for c in r["cenarios"]:
            print(f"  {c['periodo']} [{c['metodo']}]")
            for nome in ("pessimista", "base", "otimista"):
                v = c[nome]
                print(f"    {nome:<11} {v['valor']:>10}  IC95 [{v['inf']:>10} … {v['sup']:>10}]")
            print(f"    spread ot-pes: {c['spread']}")
        print("premissa: brent ±15%, ptax +10%/-10% sobre o ultimo trimestre")
        print("nota: cenario nao e fato publicado — ele abre o intervalo quando as premissas variam")
        return 0
    if args.avaliar:
        from controllers import ForecastController
        r = ForecastController().avaliar(args.empresa, args.rubrica)
        er = r["erro_real"]
        print("== Erro real das projecoes gravadas (vs fato publicado) ==")
        if er["total"] == 0:
            print("  ainda nao ha projecao com fato real contraparte — rode de novo outro trimestre")
        else:
            print(f"  comparadas: {er['total']} · cobertura IC95: {er['cobertura_geral']} "
                  f"· MAE {er['mae_geral']} · MAPE {er['mape_geral']}%")
            for m, a in er["por_metodo"].items():
                print(f"    {m:<20} n={a['n']} MAE {a['mae']} MAPE {a['mape']}% "
                      f"cobertura {a['cobertura']}")
        ro = r["rolling_origin"]
        print("== Rolling-origin (MAE/RMSE por metodo, janela 4+) ==")
        for nome, g in ro["geral"].items():
            print(f"    {nome:<20} MAE {g['mae']} RMSE {g['rmse']} MAPE {g['mape']}% (n={g['n']})")
        return 0
    from workers.forecast_run import run_forecast
    horizonte = max(1, min(args.horizonte, 3))
    print(f"== Projecao estatistica (horizonte {horizonte} trimestre(s)) ==")
    print("metodo: 1 dado -> repete ±15% · 2-5 dados -> media ±2 desvios-padrao · "
          ">=6 dados -> backtesting com IC95 pela dispersao dos erros.\n"
          "candidatos por perfil (M10.7): FLUXO (receita, EBITDA, lucro, FCO) "
          "disputa Sazonal-Naive, Holt-Winters damped e Ultima-Observacao; "
          "ESTOQUE (divida, CAPEX) disputa so nivel e tendencia, porque o "
          "sazonal nao descreve saldo.\n"
          "nota: texto em ASCII de proposito — o console do Windows e cp1252 e "
          "sigla nao acentuada quebra a saida.")
    resumo = run_forecast(horizonte=horizonte,
                          empresas=[args.empresa] if args.empresa else None,
                          rubricas=[args.rubrica] if args.rubrica else None)
    print(f"series projetadas: {resumo['series']} · projecoes gravadas: {resumo['projecoes']}"
          f" · series ignoradas: {resumo['ignoradas']}")
    print(f"metodos: {resumo['metodos']} · confianca media: {resumo['confianca_media']}")
    for aviso in resumo["avisos"][:10]:
        print(f"  aviso: {aviso}")
    return 0


def cmd_cik(args: argparse.Namespace) -> int:
    """Gestao das chaves CIK da SEC EDGAR (M9.15)."""
    from models.repositories import CikRepository
    repo = CikRepository()
    repo.seed()
    acao = args.acao
    if acao == "list":
        chaves = repo.listar()
        print(f"chaves CIK cadastradas: {len(chaves)}")
        for c in chaves:
            marca = "" if c["ativo"] else " (inativa)"
            print(f"  {c['nome_empresa']:<16}{c['cik']:<14}{(c['atualizado_em'] or '')[:16]}{marca}")
        return 0
    if acao == "set":
        if not args.empresa or not args.cik:
            print("informe --empresa e --cik.", file=sys.stderr)
            return 2
        try:
            r = repo.salvar(args.empresa, args.cik)
        except ValueError as exc:
            print(f"erro: {exc}", file=sys.stderr)
            return 2
        print(f"CIK de {r['empresa']} gravado: {r['cik']} — a coleta sec já usa esta chave.")
        return 0
    if acao == "testar":
        if not args.empresa:
            print("informe --empresa.", file=sys.stderr)
            return 2
        from controllers import SourceController
        t = SourceController().testar_cik(args.empresa)
        if t["ok"]:
            print(f"OK: SEC respondeu para {t['empresa']} (CIK {t['cik']}) — "
                  f"\"{t.get('nome_na_sec') or 'sem nome'}\" · {t.get('conceitos', 0)} conceitos")
            return 0
        print(f"falhou: {t.get('detalhe')}")
        return 1
    if acao == "del":
        if not args.empresa:
            print("informe --empresa.", file=sys.stderr)
            return 2
        if repo.excluir(args.empresa):
            # config volta a mandar como fallback
            import config
            fallback = config.COMPANIES.get(args.empresa.strip().upper(), {}).get("cik")
            print(f"chave de {args.empresa} removida."
                  + (f" fallback do config: {fallback}" if fallback else
                     " (sem fallback: a coleta pula esta empresa)"))
            return 0
        print("empresa sem chave no banco.")
        return 1
    return 1


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
    if acao == "urls":
        # M1.14: URL quebrada x bloqueio de automacao (403 nao e link morto)
        from workers.api_scan import checar_fontes
        from models.repositories import FonteRepository
        r = checar_fontes(FonteRepository(), limite=args.limite if args.limite != 50 else None)
        print(f"checadas: {r['checadas']} · quebradas/inacessiveis: {len(r['quebradas'])}")
        for b in r["quebradas"]:
            tipo = "BLOQUEIO" if b["bloqueio"] else "QUEBRADA"
            print(f"  [{tipo}] #{b['id_fonte']:<5} {b['nome_empresa']:<14} {b['status']:<12}"
                  f"{b['url'][:52]}")
            print(f"            {b['diagnostico']}")
        return 0 if r["ok"] else 2
    if acao == "aprovar":
        # M1.15: aprovacao em lote. O padrao e so mexer no que esta PENDENTE —
        # "aprovar tudo" sobre um catalogo com 26 pendentes entre 500 linhas
        # mudaria 474 sem o operador pedir.
        if not args.ids:
            print("informe --ids 12,13,14 (ou 'todas' para as PENDENTE).",
                  file=sys.stderr)
            return 2
        if args.ids.strip().lower() == "todas":
            ids = [f["id_fonte"] for f in ctrl.fontes_pendentes()]
            if not ids:
                print("nenhuma fonte PENDENTE.")
                return 0
        else:
            try:
                ids = [int(x) for x in args.ids.replace(";", ",").split(",") if x.strip()]
            except ValueError:
                print("--ids deve conter numeros inteiros (ex.: 12,13,14).", file=sys.stderr)
                return 2
        try:
            r = ctrl.aprovar_lote(ids, args.novo_status.upper(),
                                  apenas_pendentes=not args.incluir_nao_pendentes)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"aprovadas {r['aprovados']} de {r['solicitados']} -> {r['status']}")
        if r["ids"]:
            print("  #" + " #".join(str(i) for i in r["ids"][:40])
                  + (" ..." if len(r["ids"]) > 40 else ""))
        for ig in r["ignorados"][:20]:
            print(f"  ignorado #{ig['id_fonte']}: {ig['motivo']}")
        if len(r["ignorados"]) > 20:
            print(f"  ... e mais {len(r['ignorados']) - 20} ignorada(s)")
        return 0
    if acao == "render":
        # M9.13: baixa o portal de RI com render de JS. Sem JS, Chevron/BP/
        # Petrobras/Equinor devolvem pagina em branco e o coletor concluiria
        # (erroneamente) que nao ha documento.
        if not args.empresa:
            print("informe --empresa (ex.: --empresa PETROBRAS) — render por portal")
            return 2
        from workers.ri_collector import fetch_pagina_ri
        import config
        try:
            html, modo = fetch_pagina_ri(args.empresa)
        except (ValueError, RuntimeError) as exc:
            print(f"erro: {exc}")
            return 1
        print(f"empresa: {args.empresa} · modo: {modo} · html {len(html):,} chars")
        destino = Path(config.DATA_DIR) / f"ri_render_{args.empresa.lower()}.html"
        destino.write_text(html, encoding="utf-8")
        print(f"salvo em: {destino}")
        return 0
    if acao == "cache":
        from workers import parse_pdf as pp
        st = pp.cache_stats()
        print(f"cache de PDF: {st['entradas']} entrada(s), {st['mb']} MB em {st['dir']}")
        if args.limpar:
            print(f"removidas: {pp.cache_limpar(tudo=True)}")
            print(pp.cache_stats())
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
    if getattr(args, "visual", False):
        from workers.apresentacao_pptx import construir_visual
        destino = construir_visual(args.saida)
        print(f"Apresentacao VISUAL PPTX: {destino}")
        return 0
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
    if args.publicacao:  # M9.14: alerta automático do trimestre publicado
        from workers.publicacao import enviar as _enviar_pub, ultimo_periodo_com_dados
        info = ultimo_periodo_com_dados()
        if info is None:
            print("sem fatos na base — nada a publicar.")
            return 0
        rota = _enviar_pub(args.para, dry_run=not args.enviar)
        if rota is None:
            print(f"sem comparativo para {info['periodo']}: e-mail não gerado.")
            return 0
        print(f"{'ENVIADO para' if args.enviar else 'e-mail de publicação gerado em'} {rota}")
        print(f"publicado: {info['periodo']} — {info['fatos_no_periodo']} fatos de "
              f"{info['empresas']} empresas")
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
    web.add_argument("--porta", type=int, default=8080,
                     help="porta do servidor (padrao: 8080)")
    web.add_argument("--sem-abrir", action="store_true",
                     help="nao abre o navegador (uso em script/screenshot)")
    gui = sub.add_parser("gui")
    gui.add_argument("--periodo", default="2026Q2")
    sec = sub.add_parser("sec")
    sec.add_argument("--periodos", nargs="*", default=None,
                     help="periodos extras p/ historico (ex.: 2023Q1 2024Q4)")
    sec.add_argument("--empresa", nargs="*", default=None,
                     help="restringe a empresas do catalogo de CIK (ex.: PETROBRAS BP)")
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
    descoberta.add_argument("--etl", action="store_true",
                            help="baixa o que falta e roda o ETL incremental em seguida "
                                 "(descobrir -> baixar -> fato; requer registro no catálogo)")
    descoberta.add_argument("--jobs", type=int, default=None,
                            help="processos do parse no --etl (padrao: automatico)")
    descoberta.add_argument("--sem-registrar", action="store_true",
                            help="apenas relata: nao grava no catalogo de fontes")
    descoberta.add_argument("--json", action="store_true", help="saida em JSON")
    pdf = sub.add_parser("pdf", help="deck executivo (PDF) ou apresentacao (PPTX)")
    pdf.add_argument("--periodo", default="2026Q2")
    pdf.add_argument("--saida", default=None)
    pdf.add_argument("--pptx", action="store_true",
                     help="deck de conteudo em PPTX (padrao: deck em PDF)")
    pdf.add_argument("--visual", action="store_true",
                     help="deck VISUAL: uma tela real do painel por slide")
    email = sub.add_parser("email")
    email.add_argument("--para", required=True)
    email.add_argument("--alerta", action="store_true",
                       help="M7.25: envia o e-mail de ALERTAS P1 da fila de qualidade")
    email.add_argument("--publicacao", action="store_true",
                       help="M9.14: e-mail automático do último trimestre publicado")
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
                                        "check", "urls", "metrica", "cache", "aprovar", "render"])
    fontes.add_argument("--jobs", type=int, default=None,
                        help="processos para medir (metrica); padrao: automatico")
    fontes.add_argument("--limpar", action="store_true",
                        help="cache: limpa todas as entradas")
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
    fontes.add_argument("--ids", default=None,
                        help="aprovar: lista de id_fonte separados por virgula "
                             "(ou 'todas' para as PENDENTE)")
    fontes.add_argument("--novo-status", dest="novo_status", default="PROCESSADO",
                        help="aprovar: status de destino (padrao: PROCESSADO)")
    fontes.add_argument("--incluir-nao-pendentes", action="store_true",
                        help="aprovar: tambem mexe em fontes que nao estao PENDENTE")
    qa = sub.add_parser("qualidade", help="gestao e controle de qualidade (M7)")
    qa.add_argument("acao", choices=["rodar", "resumo", "fila", "regras", "historico",
                                        "limiar", "proveniencia"])
    qa.add_argument("--limite", type=int, default=25)
    qa.add_argument("--empresa", default=None, help="filtra o historico por empresa")
    qa.add_argument("--rubrica", default=None, help="rubrica do limiar calibrado")
    qa.add_argument("--codigo", default=None, help="regra a calibrar (ex.: DRIFT_ZSCORE)")
    qa.add_argument("--limiar", type=float, default=None,
                    help="novo limiar (com --codigo): so para essa empresa/rubrica")
    qa.add_argument("--periodo", default=None, help="trimestre da trilha de proveniencia")
    qa.add_argument("--reanotar", action="store_true",
                    help="proveniencia: reclassifica a base sem reprocessar documentos")
    fc = sub.add_parser("projecao", help="projecao estatistica (M3) ate 3 trimestres")
    fc.add_argument("--horizonte", type=int, default=3)
    fc.add_argument("--empresa", default=None)
    fc.add_argument("--rubrica", default=None)
    fc.add_argument("--cenarios", action="store_true",
                    help="M3.13/M10.8: mostra cenarios Brent/FX com intervalo covariancia-sensivel")
    fc.add_argument("--avaliar", action="store_true",
                    help="M3.14/M10.9: erro real das projecoes e rolling-origin (metodo x MSE)")
    cik = sub.add_parser("cik", help="gestao das chaves CIK da SEC EDGAR (M9.15)")
    cik.add_argument("acao", choices=["list", "set", "testar", "del"])
    cik.add_argument("--empresa", default=None, help="empresa da chave")
    cik.add_argument("--cik", default=None, help="chave CIK (10 digitos)")
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
            "projecao": cmd_forecast, "auditoria": cmd_auditoria, "cik": cmd_cik,
            "qualidade": cmd_qualidade}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
