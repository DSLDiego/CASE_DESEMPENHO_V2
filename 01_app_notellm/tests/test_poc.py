"""Smoke tests da PoC (banco, de-para, parsers, ETL, web)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJETO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJETO))

from config import CONTAINER_DIR  # noqa: E402
from models.database import DatabaseManager  # noqa: E402
from models.depara import resolve  # noqa: E402
from models.repositories import FatoRepository, FonteRepository  # noqa: E402


def _scan_stub(repo=None, *args, **kwargs):
    """Stub do scan: nao toca o Container. Aceita novos_ids/raiz (ver run_etl)."""
    return {"novos": 0, "duplicados": 0, "erros": 0}


def test_schema_cria_tabelas(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    db = DatabaseManager()
    with db.connect() as conn:
        tabelas = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"tb_fonte_dados", "tb_depara_rubrica", "tb_fato_financeiro",
            "tb_fato_operacional", "tb_quality_alerts", "tb_review_queue"} <= tabelas
    DatabaseManager._instance = None


def test_depara_pt_en():
    assert resolve("Receita de vendas")[0] == "RECEITA_LIQUIDA"
    assert resolve("Sales and other operating revenues")[0] == "RECEITA_LIQUIDA"
    assert resolve("EBITDA ajustado")[0] == "EBITDA_AJUSTADO"
    assert resolve("Net income attributable")[0] == "LUCRO_LIQUIDO"
    assert resolve("Total de efetivo")[0] == "EFETIVO_TOTAL"
    assert resolve("xxxxx desconhecido")[0] is None


def test_hash_idempotente(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "CATALOG_JSON", tmp_path / "c.json")
    monkeypatch.setattr(config, "CATALOG_CSV", tmp_path / "c.csv")
    DatabaseManager._instance = None
    repo = FonteRepository()
    alvo = tmp_path / "doc.pdf"
    alvo.write_bytes(b"conteudo-teste")
    id1 = repo.registrar("PETROBRAS", "http://x", "PDF", str(alvo))
    id2 = repo.registrar("PETROBRAS", "http://x", "PDF", str(alvo))
    assert id1 == id2 and id1 > 0
    DatabaseManager._instance = None


def test_parse_tab_petrobras_real():
    excel = CONTAINER_DIR / "PETROBRAS" / "2026_2T" / "Excel 2T26 USD.xlsx"
    if not excel.exists():
        pytest.skip("Container ausente")
    from workers.parse_tab import parse_excel
    exts = parse_excel(excel)
    mapa = {(e.rubrica, e.periodo): e.valor for e in exts}
    assert mapa.get(("RECEITA_LIQUIDA", "2026Q2")) == pytest.approx(33.607, abs=0.01)
    assert mapa.get(("EBITDA_AJUSTADO", "2026Q2")) == pytest.approx(18.615, abs=0.01)
    assert mapa.get(("LUCRO_LIQUIDO", "2026Q2")) == pytest.approx(10.428, abs=0.01)
    assert mapa.get(("DIVIDA_LIQUIDA", "2026Q2")) == pytest.approx(60.388, abs=0.01)


def test_quality_negativo_e_spike(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    db = DatabaseManager()
    fatos = FatoRepository(db)
    fatos.upsert_financeiro("PETROBRAS", "2026Q1", "RECEITA_LIQUIDA", 10.0)
    fatos.upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", -5.0)
    from workers.quality import run_audit
    resumo = run_audit(db)
    assert resumo["negativos"] >= 1
    DatabaseManager._instance = None


def test_web_gera_html(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.repositories import FatoRepository as FR
    fr = FR()
    fr.upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.6)
    fr.upsert_financeiro("SHELL", "2026Q2", "RECEITA_LIQUIDA", 70.0)
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "painel.html")
    from views.web_app import build_dashboard
    destino = build_dashboard("2026Q2", tmp_path / "painel.html")
    html = Path(destino).read_text(encoding="utf-8")
    assert "PETROBRAS" in html and "plotly" in html.lower()
    DatabaseManager._instance = None


def test_sec_frame_e_fy_anual():
    from workers.sec_edgar import extract_facts
    item_q = {"form": "6-K", "frame": "CY2026Q2", "fy": 2026, "fp": "Q2",
              "filed": "2026-07-22", "val": 28000000000}
    item_fy = {"form": "20-F", "frame": "CY2025", "fy": 2025, "fp": "FY",
               "filed": "2026-03-19", "val": 106462000000}
    item_ytd = {"form": "10-Q", "frame": None, "fy": 2026, "fp": "Q2",
                "filed": "2026-08-06", "val": 14282000000}
    payload = {"facts": {"ifrs-full": {"Revenue": {"units": {"USD": [item_q, item_fy, item_ytd]}}}}}
    exts = extract_facts(payload, "EQUINOR", {"2026Q2"})
    assert len(exts) == 1  # anual (FY) jamais vira trimestre
    # desempate pelo filing mais recente (restatement prevalece)
    assert exts[0].valor == pytest.approx(14.282)
    assert exts[0].periodo == "2026Q2"


def test_efetivo_ancoras_validas():
    from models.seed_efetivo import ANCORAS
    from models.repositories import FatoRepository
    assert len(ANCORAS) == 9
    empresas = {a["empresa"] for a in ANCORAS}
    assert {"PETROBRAS", "SHELL", "BP", "CHEVRON", "EXXONMOBIL", "TOTALENERGIES", "EQUINOR"} <= empresas
    for a in ANCORAS:
        assert FatoRepository.split_periodo(str(a["periodo"]))[1] == 0  # ancora anual
        assert a["valor"] > 1000 and a["fonte_url"].startswith("http")


def test_gui_monta_8_abas(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QTabWidget
    from views.gui_app import BenchmarkGUI
    gui = BenchmarkGUI(periodo="2026Q2")
    win = gui.build()
    win.show()  # offscreen: habilita isVisible
    abas = win.findChild(QTabWidget)
    assert abas.count() == 8
    assert [abas.tabText(i) for i in range(8)] == [
        "Benchmark", "Fontes (CRUD)", "Efetivo", "Auditoria", "Projeções",
        "Qualidade", "Gestão ETL", "Glossário"]
    gui.collapse_btn.click()  # colapsa: sidebar some por completo
    assert gui.show_btn.isVisible()
    gui.show_btn.click()  # expande de volta
    assert not gui.show_btn.isVisible()


def test_sidebar_colapso_web(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    from models.database import DatabaseManager
    DatabaseManager._instance = None
    from models.repositories import FatoRepository as FR
    FR().upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.6)
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "p.html")
    from views.web_app import build_dashboard
    html = open(build_dashboard("2026Q2", tmp_path / "p.html"), encoding="utf-8").read()
    assert "menu-off" in html and "toggleMenu" in html and 'id="expand"' in html
    assert "36px" not in html and "width:25%" in html
    DatabaseManager._instance = None


def test_trailing_year_bp():
    from workers.parse_tab import extract_from_matrix
    rows = [
        ["", "", "", "Footnotes", "", "Q1", "Q2", "Q3", "Q4", "2025", "Q1", "Q2", "2026"],
        ["", "Sales and other operating revenues", "", "", "", 40000, 42000, 41000, 43000, "", 50000, 52000, ""],
        ["", "Profit (loss) attributable to bp shareholders", "", "", "", 1000, 1100, 1050, 1200, "", 1300, 1400, ""],
    ]
    exts = extract_from_matrix(rows, "bp-databook#Summary")
    mapa = {(e.rubrica, e.periodo): e.valor for e in exts}
    assert mapa.get(("RECEITA_LIQUIDA", "2026Q2")) == pytest.approx(52.0)
    assert mapa.get(("LUCRO_LIQUIDO", "2025Q4")) == pytest.approx(1.2)
    assert ("RECEITA_LIQUIDA", "2022Q1") not in mapa


def test_sentence2_quarter_trailing():
    from workers.parse_pdf import extract_sentence2_figures
    lines = ["portfolio diversification to post adjusted net income of $6.0 billion "
             "and cash flow of $9.8 billion in the second quarter,"]
    exts = extract_sentence2_figures(lines, "total-PR#frase", "2026")
    mapa = {(e.rubrica, e.periodo): e.valor for e in exts}
    assert mapa.get(("LUCRO_LIQUIDO", "2026Q2")) == pytest.approx(6.0)
    # sem ano (doc ou frase) nao carrega
    assert extract_sentence2_figures(lines, "x", None) == []


def test_keyfigures_multibloco():
    from workers.parse_pdf import extract_key_figures
    lines = ["Q2 2026", "Q1 2026", "Q2 2025",
             "Net income/(loss)", "4,836", "3,105", "1,317",
             "Financial information", "Quarters", "Q2 2026", "Q2 2025",
             "Total revenues and other income", "35,177", "25,145"]
    exts = extract_key_figures(lines, "eq#kf")
    mapa = {(e.rubrica, e.periodo): e.valor for e in exts}
    assert mapa.get(("LUCRO_LIQUIDO", "2026Q2")) == pytest.approx(4.836)
    assert mapa.get(("RECEITA_LIQUIDA", "2026Q2")) == pytest.approx(35.177)


def test_doc_year_hint():
    from pathlib import Path
    from workers.parse_pdf import doc_year_hint
    assert doc_year_hint(Path("x/2026_2T/totalenergies_pr-results-2q26_2026_en.pdf")) == "2026"
    assert doc_year_hint(Path("4Q25 Earnings Press Release Website.pdf")) == "2025"


def test_frase3_quebra_de_linha_e_annual_cue():
    from workers.parse_pdf import extract_sentence3_figures
    lines = ["Cash flow", "from operating activities was $12.7 billion and free cash flow was $5.6 billion.",
             "Generated industry-leading earnings of $28.8 billion and cash flow from operations of $52.0 billion"]
    exts = extract_sentence3_figures(lines, "xom#frase3", ("2025", "Q4"))
    mapa = {(e.rubrica, e.periodo): e.valor for e in exts}
    assert mapa.get(("FCO", "2025Q4")) == pytest.approx(12.7)
    assert mapa.get(("FCL", "2025Q4")) == pytest.approx(5.6)
    assert len(exts) == 2  # linha anual (52.0) excluida pelo annual-cue? verifica abaixo
    lines2 = ["The company generated strong full-year cash flow from operations of $52.0 billion, with growth."]
    assert extract_sentence3_figures(lines2, "x", ("2025", "Q4")) == []


def test_eps_per_share_e_revenue_from_sales():
    from workers.parse_pdf import extract_sentence3_figures
    from models.depara import resolve
    assert resolve("Revenues from sales")[0] == "RECEITA_LIQUIDA"
    # EPS GAAP carrega; EPS ajustado nao
    gaap = ["Fourth-quarter 2025 earnings were $6.5 billion, or $1.53 per share."]
    exts = extract_sentence3_figures(gaap, "xom#eps", ("2025", "Q4"))
    assert {(e.rubrica, e.periodo): e.valor for e in exts}.get(("LUCRO_LIQUIDO", "2025Q4")) == pytest.approx(6.5)
    adj = ["Earnings excluding identified items were $7.3 billion, or $1.71 per share."]
    assert extract_sentence3_figures(adj, "xom#eps", ("2025", "Q4")) == []


def test_data_americana_mmddyyyy():
    from workers.parse_tab import norm_period
    per, tem_ano = norm_period("06/30/2026")
    assert (per, tem_ano) == ("2026Q2", True)
    per, tem_ano = norm_period("03/31/2026")
    assert (per, tem_ano) == ("2026Q1", True)


TRIMESTRES_ESPERADOS = {
    # periodo: (receita_lider_valor, lucro_lider_valor, margem_ebitda_petro_ok)
    "2025Q4": ("64.09", "4.13"),
    "2026Q1": ("85.14", "6.20"),
    "2026Q2": ("114.53", "14.53"),
}


def test_painel_por_trimestre(tmp_path):
    """Constroi o painel real para 2025Q4, 2026Q1 e 2026Q2 e valida a matriz."""
    from views.web_app import build_dashboard
    for per, (receita_top, lucro_top) in TRIMESTRES_ESPERADOS.items():
        destino = build_dashboard(per, tmp_path / f"painel_{per}.html")
        html = open(destino, encoding="utf-8").read()
        assert f">{per}<" in html or per in html  # trimestre selecionado
        assert receita_top in html, f"receita lider {per}"
        assert lucro_top in html, f"lucro lider {per}"
        assert "Matriz comparativa resultante" in html
        assert "RECEITA_LIQUIDA" in html and "LUCRO_LIQUIDO" in html


def test_filtro_contem_3_trimestres(tmp_path):
    from views.web_app import build_dashboard
    destino = build_dashboard("2026Q2", tmp_path / "p.html")
    html = open(destino, encoding="utf-8").read()
    for per in ("2025Q4", "2026Q1", "2026Q2"):
        assert f"value='{per}'" in html


def test_painel_filtros_e_series(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "painel.html")
    from models.database import DatabaseManager
    DatabaseManager._instance = None
    from models.repositories import FatoRepository as FR
    fr = FR()
    fr.upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.6)
    fr.upsert_financeiro("SHELL", "2026Q2", "RECEITA_LIQUIDA", 70.0)
    fr.upsert_financeiro("PETROBRAS", "2026Q1", "RECEITA_LIQUIDA", 23.5)
    from views.web_app import build_dashboard
    destino = build_dashboard("2026Q2", tmp_path / "painel.html")
    html = open(destino, encoding="utf-8").read()
    assert 'id="qsel"' in html and "2026Q1" in html  # filtro de trimestres
    assert html.count("empchk") >= 7  # filtro de empresas
    assert "série temporal" in html and '"ts":' in html  # series + ids p/ filtro
    assert "renderMatrix" in html and "INSIGHTS" in html and "applyQuarter" in html
    DatabaseManager._instance = None


def test_matriz_2024Q2_real():
    from views.web_app import build_dashboard
    import tempfile, os
    destino = os.path.join(tempfile.gettempdir(), "matriz_24Q2_check.html")
    build_dashboard("2024Q2", destino)
    html = open(destino, encoding="utf-8").read()
    assert "47.30" in html  # receita BP 2024Q2 da serie longa
    assert "2024Q2" in html


def test_grid_responsivo(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    from models.database import DatabaseManager
    DatabaseManager._instance = None
    from models.repositories import FatoRepository as FR
    FR().upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.6)
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "p.html")
    from views.web_app import build_dashboard
    html = open(build_dashboard("2026Q2", tmp_path / "p.html"), encoding="utf-8").read()
    assert "gridCols" in html and "gridH(" in html  # grade NxM configuravel
    for gid in ("grid-exec", "grid-comp", "grid-exp", "grid-evo"):
        assert f'id="{gid}"' in html
    assert "--cols" in html and "Plots.resize" in html  # ocupa a tela
    DatabaseManager._instance = None


def test_tema_claro_padrao_web(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    from models.database import DatabaseManager
    DatabaseManager._instance = None
    from models.repositories import FatoRepository as FR
    FR().upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.6)
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "p.html")
    from views.web_app import build_dashboard
    html = open(build_dashboard("2026Q2", tmp_path / "p.html"), encoding="utf-8").read()
    assert '<body data-theme="light">' in html  # claro e o padrao
    assert "setTheme" in html and "initTheme" in html  # graficos seguem o tema
    assert html.count('class="paged"') >= 3  # paginacao nas tabelas grandes
    assert "Página" in html and "/pág" in html
    DatabaseManager._instance = None


def test_gui_tema_claro_e_paginacao(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QPushButton
    from views.gui_app import BenchmarkGUI
    gui = BenchmarkGUI(periodo="2026Q2")
    win = gui.build()
    win.show()
    assert gui.dark is False  # claro como padrao
    assert "#f4f6f8" in gui._app.styleSheet()
    assert len(gui._plots) >= 5  # fundos dos graficos acompanham o tema
    pagers = [b for b in win.findChildren(QPushButton) if b.text() in ("◀", "▶")]
    assert len(pagers) >= 4  # 2 tabelas x prev/next


def test_normalizar_sinal():
    from workers.etl import normalizar_sinal
    assert normalizar_sinal("CAPEX", -4.2) == 4.2
    assert normalizar_sinal("CAPEX", 4.2) == 4.2
    assert normalizar_sinal("DESPESA_OPERACIONAL", 8.7) == -8.7
    assert normalizar_sinal("DESPESA_OPERACIONAL", -5.2) == -5.2
    assert normalizar_sinal("RECEITA_LIQUIDA", 33.6) == 33.6


def test_novos_indicadores_capex():
    from models.depara import resolve
    from workers.parse_tab import extract_from_matrix
    assert resolve("Capital expenditure")[0] == "CAPEX"
    assert resolve("Subtotal")[0] is None  # sozinho nao e CAPEX
    rows = [
        ["US$ milhoes", "2T26", "1T26", "2T25"],
        ["Exploracao & Producao", 4337, 4463, 3722],
        ["Subtotal", 5291, 5107, 4431],
    ]
    exts = extract_from_matrix(rows, "Excel 2T26 USD.xlsx#Investimentos")
    mapa = {(e.rubrica, e.periodo): e.valor for e in exts}
    assert mapa.get(("CAPEX", "2026Q2")) == pytest.approx(5.291)
    exts2 = extract_from_matrix(rows, "Excel 2T26 USD.xlsx#DRE")
    assert ("CAPEX", "2026Q2") not in {(e.rubrica, e.periodo) for e in exts2}


def test_series_sao_linha():
    """Series temporais: sempre graficos de linha (scatter lines), nunca barra."""
    from views.web_app import _fig_serie
    series = {"RECEITA_LIQUIDA": {"PETROBRAS": {"2026Q1": 23.5, "2026Q2": 33.6},
                                  "SHELL": {"2026Q1": 69.0, "2026Q2": 70.0}}}
    div, ordem, pid = _fig_serie("RECEITA_LIQUIDA", "", ["2026Q1", "2026Q2"], series)
    import re as _re
    assert pid and f'id="{pid}"' in div  # div e newPlot partilham o id
    assert _re.search(r'getElementById\("' + pid + r'"\)', div)
    assert '"name":"PETROBRAS"' in div and '"name":"SHELL"' in div  # traces rendidos
    assert div.count('"mode":"lines+markers"') >= 2  # todos em linha
    assert ordem == ["PETROBRAS", "SHELL"]


def test_trimestre_nao_filtra_series(tmp_path, monkeypatch):
    """O filtro de trimestre (applyQuarter) nao toca nos graficos de serie temporal."""
    import config, re
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    from models.database import DatabaseManager
    DatabaseManager._instance = None
    from models.repositories import FatoRepository as FR
    fr = FR()
    fr.upsert_financeiro("PETROBRAS", "2026Q1", "RECEITA_LIQUIDA", 23.5)
    fr.upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.6)
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "p.html")
    from views.web_app import build_dashboard
    html = open(build_dashboard("2026Q2", tmp_path / "p.html"), encoding="utf-8").read()
    m = re.search(r"function applyQuarter\(q\)\{.*?\n\}", html, re.DOTALL)
    assert m and "IDS.ts" not in m.group(0) and "plot-ts-" not in m.group(0)
    assert "23.5" in html and "33.6" in html  # ambos os trimestres na serie
    DatabaseManager._instance = None


def test_ui_paleta_kpi_resize(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    from models.database import DatabaseManager
    DatabaseManager._instance = None
    from models.repositories import FatoRepository as FR
    fr = FR()
    fr.upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.6)
    fr.upsert_financeiro("SHELL", "2026Q2", "RECEITA_LIQUIDA", 70.0)
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "p.html")
    from views.web_app import CORES, build_dashboard
    from config import PALETA
    assert len(CORES) == 7 and CORES == PALETA
    assert CORES["PETROBRAS"] == PALETA["PETROBRAS"] != "#00a86b"  # paleta nova
    assert len({CORES[e] for e in CORES}) == 7  # 1 cor por empresa
    html = open(build_dashboard("2026Q2", tmp_path / "p.html"), encoding="utf-8").read()
    assert "kpi-v" in html and "70.00" in html  # cards KPI
    assert "Plots.resize" in html  # resize ao trocar de aba/janela
    DatabaseManager._instance = None


def test_gui_periodo_reativo(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from views.gui_app import BenchmarkGUI
    gui = BenchmarkGUI(periodo="2026Q2")
    win = gui.build()
    win.show()
    assert gui.window.windowTitle().endswith("2026Q2 (USD bi, PySide6)")
    assert len(gui.CORES) == 7
    gui._trocar_periodo("2026Q1")
    assert gui.periodo == "2026Q1" and gui.window.windowTitle().endswith("2026Q1 (USD bi, PySide6)")
    assert "2026Q1" in gui.window.statusBar().currentMessage()


def test_gui_sem_corte_rotulos(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from views.gui_app import BenchmarkGUI
    gui = BenchmarkGUI(periodo="2026Q2")
    gui.build()
    for rub, widget in gui._bench_cells.items():
        import sqlite3
        dbmax = sqlite3.connect(
            r'C:\Users\diego\Downloads\CASE_DESEMPENHO\01_app_notellm\data\petro_analytics.db'
        ).execute("SELECT MAX(valor) FROM tb_fato_financeiro"
                  " WHERE periodo='2026Q2' AND rubrica_padronizada=?", (rub,)).fetchone()[0] or 0
        _min, _max = widget.viewRange()[1]
        assert _max >= dbmax * 1.15  # headroom de 22% p/ rotulos fora da barra


def test_gui_layout_splitter_grid(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFormLayout, QGridLayout, QSplitter
    from views.gui_app import BenchmarkGUI
    gui = BenchmarkGUI(periodo="2026Q2")
    win = gui.build()
    win.show()
    splitters = win.findChildren(QSplitter)
    assert splitters and splitters[0].handleWidth() >= 4  # separacao visivel
    assert win.findChild(QGridLayout) is not None  # empresas em grade tabular
    assert win.findChild(QFormLayout) is not None  # periodo/moeda em linhas rotulo-campo


def test_coleta_urls_e_links_offline():
    from workers.ri_collector import I10_SITES, RI_SITES, discover_links, trimestre_corrente
    assert len(RI_SITES) == 7 and len(I10_SITES) == 7
    assert I10_SITES["PETROBRAS"].endswith("/stocks/pbr/")
    assert I10_SITES["SHELL"].endswith("/stocks/shel/")
    assert "equinor.com" in RI_SITES["EQUINOR"] and "petrobras" in RI_SITES["PETROBRAS"]
    html = ('<html><body><a href="/results/q2-2026.pdf">Q2 Results</a>'
            '<a href="https://x.com/a.xlsx">Databook</a>'
            '<a href="/results/q2-2026.pdf">Q2 Results</a>'
            '<a href="/home">Home</a></body></html>')
    links = discover_links("https://www.shell.com/investors/", html)
    assert len(links) == 2  # dedup + so documentos
    assert links[0]["url"] == "https://www.shell.com/results/q2-2026.pdf"
    assert links[0]["tipo"] == "PDF"
    assert trimestre_corrente().startswith("2026Q")


def test_investidor10_faq_preciso():
    from workers.ri_collector import parse_investidor10
    html = ('<script type="application/ld+json">{"@type":"FAQPage","mainEntity":[{"@type":"Question",'
            '"name":"PBR vale a pena?",'
            '"acceptedAnswer":{"@type":"Answer","text":"Atualmente, PBR esta cotada a US$ 21,14, '
            'com um P/L de 5,18. No ultimo ano distribuiu US$ 0,60, resultando em um Dividend Yield de 4,12%."'
            '}}]}</script><div>ROE: 22,12% em tabela comparativa e 2026 e variacao 81.56</div>')
    snap = parse_investidor10(html)
    assert snap.get("COTACAO") == 21.14 and snap.get("_MOEDA") == "US$"
    assert snap.get("P/L") == 5.18 and snap.get("DY") == 4.12
    assert "ROE" not in snap and "ROIC" not in snap


def test_cik_map_e_proveniencia(tmp_path, monkeypatch):
    import config
    from config import COMPANIES
    assert len(COMPANIES) == 7
    for emp, meta in COMPANIES.items():
        assert len(meta["cik"]) == 10 and meta["cik"].isdigit()
    assert COMPANIES["BP"]["cik"] == "0000313807"  # 0000313801 retorna 404
    assert "@" in config.USER_AGENT  # SEC exige User-Agent identificado
    # proveniencia: fato carrega id_fonte
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    from models.database import DatabaseManager
    DatabaseManager._instance = None
    from models.repositories import FatoRepository, FonteRepository
    fontes, fatos = FonteRepository(), FatoRepository()
    fid = fontes.registrar("EQUINOR", "https://data.sec.gov/x.json", "JSON", None, "0001140625", "PROCESSADO")
    fatos.upsert_financeiro("EQUINOR", "2026Q2", "LUCRO_LIQUIDO", 4.8, "USD", fid, 0.9)
    rows = fatos.matriz("2026Q2")
    assert rows and rows[0].get("url_fonte") == "https://data.sec.gov/x.json"
    DatabaseManager._instance = None


def test_robustez_coleta_offline(tmp_path):
    from workers.ri_collector import canonical_url, validar_conteudo
    assert canonical_url("HTTPS://Shell.COM/a/b/?utm_source=x&k=2&utm_medium=y") == "https://shell.com/a/b?k=2"
    assert canonical_url("https://x.com/a?utm_source=1&utm_source=2") == "https://x.com/a"
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF-1.7 relatorio")
    assert validar_conteudo(pdf, ".pdf") == "OK"
    fake = tmp_path / "f.pdf"
    fake.write_bytes(b"<!doctype html><html>Login corporativo</html>")
    assert validar_conteudo(fake, ".pdf") == "HTML_REJEITADO"
    xls = tmp_path / "d.xlsx"
    xls.write_bytes(b"PK\x03\x04planilha")
    assert validar_conteudo(xls, ".xlsx") == "OK"


def test_derivados_margens(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    from models.database import DatabaseManager
    DatabaseManager._instance = None
    from models.repositories import FatoRepository
    from workers.derived import compute_derived
    fr = FatoRepository()
    fr.upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.607, "USD", None, 0.95)
    fr.upsert_financeiro("PETROBRAS", "2026Q2", "EBITDA_AJUSTADO", 18.615, "USD", None, 0.95)
    fr.upsert_financeiro("PETROBRAS", "2026Q2", "LUCRO_LIQUIDO", 10.428, "USD", None, 0.95)
    fr.upsert_financeiro("PETROBRAS", "2026Q2", "DIVIDA_LIQUIDA", 60.388, "USD", None, 0.95)
    resumo = compute_derived()
    assert resumo["margens"] == 2 and resumo["alavancagem"] == 1
    import sqlite3
    conn = sqlite3.connect(tmp_path / "t.db")
    vals = {r[0]: r[1] for r in conn.execute(
        "SELECT indicador, valor FROM tb_fato_operacional WHERE nome_empresa='PETROBRAS'")}
    assert vals["MARGEM_EBITDA"] == round(18.615 / 33.607 * 100, 2)
    assert vals["MARGEM_LIQUIDA"] == round(10.428 / 33.607 * 100, 2)
    assert vals["DIVIDA_LIQUIDA_EBITDA"] == round(60.388 / 18.615, 2)
    DatabaseManager._instance = None


def test_js_harness_comportamental(tmp_path):
    """Extrai o JS do painel recem-gerado e roda o harness Node.

    Cobre: troca de aba, matriz por trimestre, conversao BRL/PTAX, tema,
    filtro de series e o fluxo de tela cheia (fAbrir/fSair/fitAll).
    """
    import os, re, shutil, subprocess
    if not shutil.which("node"):
        pytest.skip("node indisponivel")
    from views.web_app import build_dashboard
    destino = build_dashboard("2026Q2", tmp_path / "painel.html")
    html = Path(destino).read_text(encoding="utf-8")
    scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
    custom = max(scripts, key=len)
    js_path = tmp_path / "custom.js"
    js_path.write_text(custom, encoding='utf-8')
    harness = r'C:\Users\diego\AppData\Local\Temp\opencode\harness.js'
    if not os.path.exists(harness):
        pytest.skip("harness Node ausente")
    proc = subprocess.run(["node", harness, str(js_path)], capture_output=True, text=True, timeout=60)
    assert "ALL OK" in proc.stdout, proc.stdout + proc.stderr


def test_moeda_brl_toggle(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    from models.database import DatabaseManager
    DatabaseManager._instance = None
    from models.repositories import FatoRepository as FR
    FR().upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.607)
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "p.html")
    from views.web_app import build_dashboard
    html = open(build_dashboard("2026Q2", tmp_path / "p.html"), encoding="utf-8").read()
    assert 'name="moeda"' in html and "setMoeda" in html and "TAXAS" in html
    assert 'id="ptax"' in html and "renderMatrix" in html
    DatabaseManager._instance = None


def test_sec_frames_4_anos():
    from workers.sec_edgar import extract_facts
    items = [{"form": "10-Q", "frame": f"CY{y}Q2", "fy": y, "fp": "Q2",
              "filed": f"{y}-08-06", "val": 1000000000 * y} for y in (2023, 2024, 2025, 2026)]
    payload = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": items}}}}}
    exts = extract_facts(payload, "CHEVRON", {"2023Q2", "2024Q2", "2025Q2", "2026Q2"})
    mapa = {e.periodo: e.valor for e in exts}
    assert len(mapa) == 4 and mapa["2023Q2"] == 2023.0 and mapa["2026Q2"] == 2026.0


def test_pdf_email_trimestre_cli(tmp_path, monkeypatch):
    import config, os
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    from models.database import DatabaseManager
    DatabaseManager._instance = None
    from models.repositories import FatoRepository as FR
    FR().upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.607, "USD", None, 0.95)
    from workers.deck_pdf import gerar_pdf
    destino = gerar_pdf(tmp_path / "slides.pdf", "2026Q2")
    assert open(destino, "rb").read(5) == b"%PDF-"
    from workers.mailer import enviar, montar_email
    msg = montar_email("a@exemplo.com", "RECEITA_LIQUIDA", "2026Q2")
    corpo = msg.get_body(("plain",)).get_content()
    assert "33,61" in corpo or "33.61" in corpo
    eml = enviar(msg, dry_run=True)
    assert os.path.exists(eml)
    import app_main
    assert {"pdf", "email", "trimestre"} <= set(
        ["full", "etl", "web", "gui", "sec", "efetivo", "coleta", "derivados",
         "powerbi", "pdf", "email", "trimestre", "status", "reset"])
    DatabaseManager._instance = None


def test_grid_preservado_no_filtro(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    from models.database import DatabaseManager
    DatabaseManager._instance = None
    from models.repositories import FatoRepository as FR
    FR().upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.6)
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "p.html")
    from views.web_app import build_dashboard
    html = open(build_dashboard("2026Q2", tmp_path / "p.html"), encoding="utf-8").read()
    assert "GRID_H" in html and "RUB_GRID" in html  # altura por grade
    assert "GRID_H[RUB_GRID[rub]]" in html or "withMean" in html  # filtro usa a altura escolhida
    assert "overflow:hidden" in html  # sem vazamento entre celulas
    assert "automargin" in html  # eixos/rotulos contidos
    assert "twrap" in html  # tabelas largas com scroll horizontal
    import re as _re2
    assert _re2.search(r"function gridCols.*?Plots\.resize", html, _re2.DOTALL)  # cols redimensionam
    DatabaseManager._instance = None


def test_gui_moeda_toggle(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from views.gui_app import BenchmarkGUI
    gui = BenchmarkGUI(periodo="2026Q2")
    win = gui.build()
    win.show()
    assert gui.moeda == "USD"
    gui._trocar_moeda("BRL")
    assert gui.moeda == "BRL" and "(BRL" in gui.window.windowTitle()
    gui._trocar_moeda("USD")
    assert "(USD" in gui.window.windowTitle()


def _fonte_repo(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "CATALOG_JSON", tmp_path / "c.json")
    monkeypatch.setattr(config, "CATALOG_CSV", tmp_path / "c.csv")
    DatabaseManager._instance = None
    return FonteRepository()


def test_crud_fontes_completo(tmp_path, monkeypatch):
    repo = _fonte_repo(tmp_path, monkeypatch)
    arquivo = tmp_path / "release_2t26.pdf"
    arquivo.write_bytes(b"%PDF-1.4 fake")

    novo_id = repo.registrar("PETROBRAS", "https://ri.exemplo/2t26", "PDF", str(arquivo),
                             "0001119639", "CATALOGADO", api_json="https://ri.exemplo/api.json")
    lido = repo.obter(novo_id)
    assert lido["extensao"] == ".pdf" and lido["pasta_sistema"] == str(tmp_path)
    assert lido["nome_documento"] == "release_2t26.pdf" and lido["origem"] == "CONTAINER"

    assert repo.atualizar(novo_id, status_processamento="PROCESSADO",
                          nome_documento="Release 2T26")
    assert repo.obter(novo_id)["status_processamento"] == "PROCESSADO"

    FatoRepository().upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 1.0,
                                       "USD", novo_id)
    assert repo.excluir(novo_id) is True
    assert repo.obter(novo_id) is None
    fato = FatoRepository().obter("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA")
    assert fato["id_fonte"] is None  # auditabilidade: fato preservado, FK zerada
    assert repo.atualizar(novo_id, status_processamento="ERRO") is False
    DatabaseManager._instance = None


def test_backfill_extensao_e_pasta(tmp_path, monkeypatch):
    repo = _fonte_repo(tmp_path, monkeypatch)
    novo_id = repo.registrar("SHELL", "https://exemplo/x.html", "HTML")
    with repo.db.connect() as conn:  # simula banco de versao anterior (sem as colunas)
        conn.execute("UPDATE tb_fonte_dados SET extensao = NULL, pasta_sistema = NULL,"
                     " nome_documento = NULL WHERE id_fonte = ?", (novo_id,))
        conn.commit()
    assert repo.complementar_campos() == 1
    assert repo.obter(novo_id)["extensao"] == ".html"
    DatabaseManager._instance = None


def test_migration_idempotente(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    db = DatabaseManager()
    assert db.migrate() == []  # schema ja atualizado: nada a fazer
    with db.connect() as conn:
        colunas = {r["name"] for r in conn.execute("PRAGMA table_info(tb_fonte_dados)")}
    assert {"nome_documento", "extensao", "pasta_sistema", "api_json", "origem"} <= colunas
    DatabaseManager._instance = None


def test_api_scan_offline(tmp_path, monkeypatch):
    import requests
    from workers import api_scan
    repo = _fonte_repo(tmp_path, monkeypatch)

    def _boom(*_a, **_k):
        raise requests.ConnectionError("sem rede")

    monkeypatch.setattr(api_scan.requests, "get", _boom)
    repo.registrar("PETROBRAS", "https://ri.exemplo", "HTML")
    relatorio = api_scan.escanear(ciks={"PETROBRAS": "0001119639"},
                                  siglas_i10={"PETROBRAS": "PETR4"}, repo=repo)
    assert len(relatorio) == 2
    assert all(r["json_publico"] is False for r in relatorio)
    assert all(r["status"].startswith("ERRO_REDE") for r in relatorio)
    assert repo.obter(repo.listar()[0]["id_fonte"])["api_json"].startswith("SEM (")
    DatabaseManager._instance = None


def test_api_scan_detecta_json_publico(tmp_path, monkeypatch):
    from workers import api_scan
    repo = _fonte_repo(tmp_path, monkeypatch)

    class _Resp:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    monkeypatch.setattr(api_scan.requests, "get", lambda *a, **k: _Resp(
        {"facts": {"us-gaap": {}, "ifrs-full": {}}}))
    relatorio = api_scan.escanear(ciks={"SHELL": "0001306965"}, siglas_i10={}, repo=repo)
    assert relatorio[0]["json_publico"] is True
    assert "us-gaap" in relatorio[0]["detalhe"]
    DatabaseManager._instance = None


def test_api_crud_fontes_http(tmp_path, monkeypatch):
    import json as _json
    from http.server import ThreadingHTTPServer
    import threading
    import urllib.request
    repo = _fonte_repo(tmp_path, monkeypatch)
    from views.web_server import DashboardHandler
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    porta = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{porta}/api/fontes"

    def _req(metodo, corpo=None):
        dados = _json.dumps(corpo).encode() if corpo is not None else None
        req = urllib.request.Request(base, data=dados, method=metodo,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, _json.loads(r.read().decode())

    try:
        status, criado = _req("POST", {"nome_empresa": "BP", "url_fonte": "https://bp.ex/x.pdf",
                                       "tipo_arquivo": "PDF", "nome_documento": "Q2"})
        assert status == 201 and criado["fonte"]["extensao"] == ".pdf"
        id_fonte = criado["id_fonte"]
        assert _req("PUT", {"id_fonte": id_fonte, "status_processamento": "PROCESSADO"})[0] == 200
        assert repo.obter(id_fonte)["status_processamento"] == "PROCESSADO"
        assert _req("DELETE", {"id_fonte": id_fonte})[0] == 200
        assert repo.obter(id_fonte) is None
        with pytest.raises(Exception):
            _req("POST", {"nome_empresa": "BP"})
    finally:
        httpd.shutdown()
        httpd.server_close()
        DatabaseManager._instance = None


@pytest.mark.parametrize("ano", ["2023", "2024", "2025", "2026"])
def test_container_extraction_4_anos(ano):
    """Requisito: download + extracao de PDFs/planilhas de 4 anos (2023-2026).

    Anos sem pasta no Container sao skipped com evidencia explicita (nao ha
    documento publico fornecido); SEC EDGAR cobre o periodo via XBRL frames.
    """
    from workers.parse_pdf import parse_pdf
    from workers.parse_tab import parse_tab
    from config import PDF_PARSE_ALLOW
    pastas = [p for p in CONTAINER_DIR.glob(f"*/{ano}_*T") if p.is_dir()]
    if not pastas:
        pytest.skip(f"Container sem pasta {ano}_*T (anos disponiveis: "
                    f"{sorted({p.name[:4] for p in CONTAINER_DIR.glob('*/*_?T')})})")
    extraidas = 0
    for pasta in pastas:
        for arquivo in sorted(pasta.rglob("*")):
            if not arquivo.is_file():
                continue
            sufixo = arquivo.suffix.lower()
            if sufixo in (".xlsx", ".xlsm", ".xls", ".csv"):
                extraidas += len(parse_tab(arquivo))
            elif sufixo == ".pdf" and any(t in arquivo.name.lower() for t in PDF_PARSE_ALLOW):
                extraidas += len(parse_pdf(arquivo))
    assert extraidas > 0, f"nenhuma extracao em {ano} ({len(pastas)} pastas)"


def test_sec_download_real_4_anos():
    """Download real da SEC cobrindo 4 anos (2023-2026) via XBRL frames."""
    from workers.sec_edgar import extract_facts, fetch_companyfacts
    try:
        payload = fetch_companyfacts("0000093410")
    except Exception as exc:
        pytest.skip(f"SEC EDGAR indisponivel: {exc}")
    periodos = {f"{ano}Q{t}" for ano in (2023, 2024, 2025, 2026) for t in (1, 2, 3, 4)}
    exts = extract_facts(payload, "CHEVRON", periodos)
    anos = {e.periodo[:4] for e in exts}
    assert exts, "nenhum fato trimestral extraido"
    assert {"2023", "2024", "2025", "2026"} <= anos, f"anos cobertos: {sorted(anos)}"


def test_web_anti_sobreposicao_e_ux(tmp_path, monkeypatch):
    """Garantias de layout: nada de um grafico vazar sobre o vizinho + UX nova."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    FatoRepository().upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.607)
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "p.html")
    from views.web_app import build_dashboard
    html = Path(build_dashboard("2026Q2", tmp_path / "p.html")).read_text(encoding="utf-8")
    # 1) anti-vazamento: clipping por celula + hoverlayer/modebar contidos
    assert "contain:layout paint" in html and "isolation:isolate" in html
    assert ".cell .hoverlayer,.cell .modebar" in html
    # 2) sem modebar flutuante (cobria o titulo e vazava na celula vizinha)
    assert '"displayModeBar": false' in html
    # 3) folga para rotulos "outside" das barras + cliponaxis (serializado no JSON)
    assert "cliponaxis" in html and '"range":[0,' in html and '"hovermode":"closest"' in html
    # 4) UX: tela cheia, atalhos, ajuste em lote, sticky tabs, filtro do catalogo
    for token in ("function fAbrir(", "function fSair(", "function fitAll(", "function fFullscreenFirst(",
                  "keydown", "position:sticky;top:0", 'id="f_busca"', "function fAjustar(",
                  "function autoFit(", "function observarCelulas(", "function temaPlot(",
                  "function aplicarUrl(", "aplicarUrl()"):
        assert token in html, token
    # 5) estado vazio explicito em vez de grafico em branco
    assert "sem dados para este indicador" in html
    # 6) autoFit passa width/height explicitos (Plots.resize nao encolhe o svg)
    assert "Plotly.relayout(el,{width:w,height:h})" in html
    # 7) cores do tema aplicadas sem depender de template do Plotly
    assert "plot_bgcolor:c.plot" in html and "template:'none'" in html
    # 8) cabecalhos das series com nome amigavel (nao codigo cru)
    assert "— série temporal</h4>" in html and ">RECEITA_LIQUIDA — série" not in html
    # 9) paginacao das tabelas grandes, inclusive nas preenchidas por JS
    for token in ("function paginate(tbl, minimo)", "function rePaginar(",
                  "rePaginar('#qual_fila', 10)", "rePaginar('#qual_mapa table', 10)",
                  "rePaginar('#qual_regras', 10)", "rePaginar('#pr_proj tbody', 10)",
                  "rePaginar('#etl_body table.paged', 10)", 'id="qual_mapa"',
                  'id="pr_proj"', 'id="qual_fila"', 'id="qual_regras"'):
        assert token in html, token
    assert html.count('class="paged"') >= 8
    DatabaseManager._instance = None


def test_gui_anti_sobreposicao_e_foco(monkeypatch):
    """pyqtgraph clipado, range estavel, foco em tela cheia e botao de e-mail."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from views.gui_app import BenchmarkGUI
    from PySide6.QtWidgets import QDialog, QPushButton
    gui = BenchmarkGUI(periodo="2026Q2")
    win = gui.build()
    win.show()
    plot = gui._plots[0]
    vb = plot.getViewBox()
    assert getattr(plot, "_clip_to_view", False), "clipping nao foi aplicado no plot"
    assert vb.getState()["autoRange"] == [False, False], "auto-range deve ficar desligado"
    assert plot._fit_range is not None and plot._fit_range[1] > 0, "range ajustado memorizado"
    antes = plot._fit_range
    vb.setYRange(0, 1, padding=0)             # simula resize/auto-range
    gui._reajustar_todos()
    assert plot._fit_range == antes and abs(plot.viewRange()[1][1] - antes[1]) < 1e-6
    titulos = [b.text() for b in win.findChildren(QPushButton)]
    assert any("e-mail" in t for t in titulos), "botao de enviar por e-mail ausente"
    assert any("Reajustar" in t for t in titulos)
    parent_original = plot.parentWidget()
    gui._focar(plot)
    dialogs = [w for w in win.findChildren(QDialog)]
    assert dialogs, "dialogo de foco nao abriu"
    dlg = dialogs[-1]
    assert plot.parentWidget() is not parent_original, "plot deve ir para o dialog"
    dlg.close()
    assert plot.parentWidget() is parent_original, "plot nao voltou para a aba"


def test_email_anexa_grafico(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    FatoRepository().upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.607, "USD")
    FatoRepository().upsert_financeiro("SHELL", "2026Q2", "RECEITA_LIQUIDA", 64.09, "USD")
    from workers.mailer import montar_email
    msg = montar_email("a@exemplo.com", "RECEITA_LIQUIDA", "2026Q2")
    tipos = {(p.get_content_type(), p.get_filename()) for p in msg.iter_attachments()}
    assert ("text/html", "RECEITA_LIQUIDA_2026Q2.html") in tipos
    assert ("text/csv", "RECEITA_LIQUIDA_2026Q2.csv") in tipos
    html = next(p.get_content() for p in msg.iter_attachments()
                if p.get_filename().endswith(".html"))
    assert "Plotly.newPlot" in html and "PETROBRAS" in html and "33.61" in html
    DatabaseManager._instance = None


def test_alerta_p1_so_envia_quando_ha_p1(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from workers import mailer
    assert mailer.montar_email_alerta("a@b.com") is None, "sem P1 nao gera e-mail"
    monkeypatch.setattr("workers.quality_score.fila_analise", lambda db=None: [
        {"prioridade": "P1", "codigo": "ATRASO_TRIMESTRE", "empresa": "(todas)",
         "periodo": "2026Q3", "severidade": "HIGH", "motivo": "atraso"}])
    msg = mailer.montar_email_alerta("a@b.com")
    assert msg is not None and "P1" in msg["Subject"]
    corpo = msg.get_body(("plain",)).get_content()
    assert "ATRASO_TRIMESTRE" in corpo and "2026Q3" in corpo
    eml = mailer.alertar_p1("a@b.com", dry_run=True)
    assert eml and __import__("os").path.exists(eml)
    DatabaseManager._instance = None


def test_api_email_gera_eml_com_grafico(tmp_path, monkeypatch):
    """POST /api/email deve devolver .eml com HTML + PNG + CSV (rubrica da GUI e web)."""
    import json as _json
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    FatoRepository().upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.607, "USD")
    FatoRepository().upsert_financeiro("SHELL", "2026Q2", "RECEITA_LIQUIDA", 64.09, "USD")
    from views.web_server import DashboardHandler
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/api/email"
    try:
        with urllib.request.urlopen(base + "?rubrica=RECEITA_LIQUIDA&periodo=2026Q2",
                                    timeout=30) as r:
            prev = _json.loads(r.read().decode())
        assert [d["empresa"] for d in prev["dados"]] == ["SHELL", "PETROBRAS"]  # ordenado
        corpo = _json.dumps({"para": "diego@exemplo.com", "rubrica": "RECEITA_LIQUIDA",
                             "periodo": "2026Q2"}).encode()
        req = urllib.request.Request(base, data=corpo, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            out = _json.loads(r.read().decode())
        assert out["enviado"] is False and out["resultado"].endswith(".eml")
        assert out["anexos"] == ["RECEITA_LIQUIDA_2026Q2.html", "RECEITA_LIQUIDA_2026Q2.png",
                                 "RECEITA_LIQUIDA_2026Q2.csv"]
        import os
        assert os.path.getsize(out["resultado"]) > 5000  # .eml com PNG embutido
        # destinatario invalido -> 400 com mensagem util
        try:
            urllib.request.urlopen(urllib.request.Request(
                base, data=_json.dumps({"para": "invalido"}).encode(), method="POST",
                headers={"Content-Type": "application/json"}), timeout=30)
            raise AssertionError("deveria recusar e-mail invalido")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400 and "destinatario" in _json.loads(exc.read().decode())["erro"]
    finally:
        httpd.shutdown()
        httpd.server_close()
        DatabaseManager._instance = None


def test_mail_controller_preview_e_envio(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    FatoRepository().upsert_financeiro("PETROBRAS", "2026Q2", "LUCRO_LIQUIDO", 10.428, "USD")
    from controllers import MailController
    ctrl = MailController()
    assert ctrl.preview("LUCRO_LIQUIDO", "2026Q2") == [
        {"empresa": "PETROBRAS", "valor": 10.43, "fonte": ""}]
    assert ctrl.preview("EBITDA_AJUSTADO", "2026Q2") == []
    r = ctrl.enviar("a@b.com", "LUCRO_LIQUIDO", "2026Q2")
    assert r["anexos"][0].endswith(".html") and "image/png" in Path(r["resultado"]).read_text(
        encoding="utf-8", errors="ignore")
    with pytest.raises(ValueError):
        ctrl.enviar("sem-arroba", "LUCRO_LIQUIDO", "2026Q2")
    DatabaseManager._instance = None


def test_paleta_distintas_para_series():
    """As 7 empresas precisam de cores bem distintas (Okabe-Ito) + traço/marcador."""
    from config import ESTILO_SERIE, PALETA
    import colorsys
    assert set(PALETA) >= {"PETROBRAS", "SHELL", "BP", "CHEVRON", "EXXONMOBIL",
                           "TOTALENERGIES", "EQUINOR"}
    assert len(set(PALETA.values())) == len(PALETA), "cores repetidas na paleta"
    hsv = [colorsys.rgb_to_hsv(*bytes.fromhex(c.lstrip("#"))) for c in
           (PALETA[e] for e in PALETA)]
    # distancia minima de matiz entre quaisquer duas empresas (evita "azuis parecidos")
    for i in range(len(hsv)):
        for j in range(i + 1, len(hsv)):
            d = abs(hsv[i][0] - hsv[j][0])
            d = min(d, 1 - d)
            assert d >= 0.08, f"matizes muito proximos: {list(PALETA)[i]} x {list(PALETA)[j]}"
    tracos = {v["dash"] for v in ESTILO_SERIE.values()}
    simbolos = {v["symbol"] for v in ESTILO_SERIE.values()}
    assert len(tracos) >= 5 and len(simbolos) >= 5, "series sem variedade de estilo"
    assert ESTILO_SERIE["PETROBRAS"]["width"] > 3, "referencia (Petrobras) deve ser a mais grossa"
    from views.web_app import CORES
    from workers.mailer import CORES as CORES_MAIL
    assert CORES == CORES_MAIL == PALETA, "web e e-mail devem usar a mesma paleta"


def test_etl_registra_status_duracao_e_erro(tmp_path, monkeypatch):
    """Cada arquivo processado grava status, duracao, nº de extracoes e erro."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from workers import etl as etl_mod
    monkeypatch.setattr(etl_mod, "scan_container", _scan_stub)
    from models.repositories import FonteRepository
    repo = FonteRepository()
    bom = tmp_path / "bom.csv"
    bom.write_text("Indicador;2026Q2;2025Q4\n"
                   "Receita de vendas;33607;30000\n"
                   "Lucro liquido;10428;9000\n", encoding="utf-8")
    ruinado = tmp_path / "ruim.xlsx"
    ruinado.write_bytes(b"PK\x03\x04 nao-e-xlsx-de-verdade")
    id_bom = repo.registrar("PETROBRAS", "http://x/bom.csv", "CSV", str(bom))
    id_ruim = repo.registrar("PETROBRAS", "http://x/ruim.xlsx", "XLSX", str(ruinado))
    id_web = repo.registrar("EQUINOR", "http://ri/relatorio", "HTML")

    from workers.etl import run_etl
    resumo = run_etl()
    assert resumo["arquivos_processados"] == 1 and resumo["cargas"] >= 1
    assert resumo["erros"] == 1 and resumo["nao_baixados"] == 1

    bom_row, ruim_row, web_row = repo.obter(id_bom), repo.obter(id_ruim), repo.obter(id_web)
    assert bom_row["status_processamento"] == "PROCESSADO"
    assert bom_row["duracao_ms"] is not None and bom_row["duracao_ms"] >= 0
    assert bom_row["n_extracoes"] >= 1 and bom_row["data_processamento"]
    assert bom_row["erro"] is None
    assert ruim_row["status_processamento"] == "ERRO" and ruim_row["erro"]
    assert web_row["status_processamento"] == "NAO_BAIXADO" and web_row["erro"] is None

    # painel: agregacoes coerentes com os status gravados
    painel = repo.resumo_etl()
    assert painel["total"] == 3 and painel["processadas"] == 1 and painel["com_erro"] == 1
    assert painel["nao_baixados"] == 1 and painel["duracao_total_ms"] > 0
    assert painel["total_execucoes"] == 1 and painel["ultimas_cargas"] >= 1
    ex = repo.execucoes()
    assert len(ex) == 1 and ex[0]["fim_em"] and ex[0]["erros"] == 1
    DatabaseManager._instance = None


def test_api_etl_painel_de_gestao(tmp_path, monkeypatch):
    """GET /api/etl entrega resumo + execucoes + fontes (painel web e GUI)."""
    import json as _json
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from workers import etl as etl_mod
    monkeypatch.setattr(etl_mod, "scan_container", _scan_stub)
    arquivo = tmp_path / "x.csv"
    # planilha com volume e rotulos REAIS: um CSV de 2 linhas leva < 50 microssegundos
    # (duracao gravada 0, o que nao exercita a metrica) e rotulo generico nao resolve
    # para rubrica canonica, logo nao geraria carga nenhuma
    rubricas = [("Receita de vendas", 33607), ("EBITDA ajustado", 18615),
                ("Lucro liquido", 10428), ("Investimentos", 7300),
                ("Divida liquida", 60390)]
    linhas = ["Indicador;2026Q2;2025Q4"]
    for i in range(400):
        for nome, base in rubricas:
            linhas.append(f"{nome};{base + i};{base - 1000 + i}")
    arquivo.write_text("\n".join(linhas), encoding="utf-8")
    from models.repositories import FonteRepository
    FonteRepository().registrar("PETROBRAS", "http://x/x.csv", "CSV", str(arquivo))
    from workers.etl import run_etl
    run_etl()
    from views.web_server import DashboardHandler
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_address[1]}/api/etl",
                                    timeout=30) as r:
            j = _json.loads(r.read().decode())
        assert {"resumo", "execucoes", "fontes"} <= set(j)
        assert j["resumo"]["processadas"] == 1 and j["resumo"]["duracao_media_ms"] > 0
        assert j["execucoes"][0]["cargas"] >= 1
        assert j["fontes"][0]["duracao_ms"] is not None
    finally:
        httpd.shutdown()
        httpd.server_close()
        DatabaseManager._instance = None


def test_web_painel_etl_e_gui(monkeypatch, tmp_path):
    """Painel de gestão do ETL presente no web (aba 6) e na GUI (5ª aba)."""
    import config
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "p.html")
    from views.web_app import build_dashboard
    html = Path(build_dashboard("2026Q2", tmp_path / "p.html")).read_text(encoding="utf-8")
    for token in ('id="etl_kpis"', 'id="etl_tbody"', 'id="etl_hist"', 'id="etl_status"',
                  'id="etl_busca"', "function etlCarregar(", "function etlFiltro(",
                  "if(i===6) etlCarregar()", "Gestão ETL", "NAO_BAIXADO"):
        assert token in html, token
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from views.gui_app import BenchmarkGUI
    from PySide6.QtWidgets import QTabWidget
    gui = BenchmarkGUI(periodo="2026Q2")
    win = gui.build()
    tabs = win.findChildren(QTabWidget)[0]
    assert tabs.tabText(tabs.count() - 2) == "Gestão ETL"
    assert "Qualidade" in [tabs.tabText(i) for i in range(tabs.count())]
    assert tabs.count() == 8
    assert "Projeções" in [tabs.tabText(i) for i in range(tabs.count())]


def test_parse_csv_detecta_delimitador(tmp_path):
    """CSV brasileiro com ';' (e com ',') devem ser extraidos igual."""
    from workers.parse_tab import parse_csv
    corpo = "Indicador;2026Q2;2025Q4\nReceita de vendas;33607;30000\n"
    a = parse_csv(_escrever(tmp_path / "a.csv", corpo))
    b = parse_csv(_escrever(tmp_path / "b.csv", corpo.replace(";", ",")))
    esperado = {("RECEITA_LIQUIDA", "2026Q2"), ("RECEITA_LIQUIDA", "2025Q4")}
    assert {(e.rubrica, e.periodo) for e in a} == esperado
    assert {(e.rubrica, e.periodo) for e in b} == esperado


def _escrever(caminho, texto: str):
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def test_web_filtros_aba_fontes(tmp_path, monkeypatch):
    """Aba Fontes (CRUD): filtros dedicados, contagem, ordenacao e TODAS as linhas."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.repositories import FonteRepository
    repo = FonteRepository()
    for i, (emp, ext, orig) in enumerate([("PETROBRAS", "PDF", "CONTAINER"),
                                         ("SHELL", "XLSX", "CONTAINER"),
                                         ("BP", "HTML", "RI"),
                                         ("CHEVRON", "PDF", "I10")]):
        arq = tmp_path / f"{emp}.{ext.lower()}"
        arq.write_bytes(f"conteudo-{emp}-{ext}".encode())   # bytes distintos: hash unico
        repo.registrar(emp, f"http://ri/{emp}", ext, str(arq), origem=orig,
                       api_json=f"https://api/{emp}" if i == 0 else None)
    repo.registrar("EQUINOR", "http://ri/eqnr.html", "HTML", origem="RI")
    repo.registrar("PETROBRAS", "http://ri/p2.pdf", "PDF", status="ERRO")
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "p.html")
    from views.web_app import build_dashboard
    html = Path(build_dashboard("2026Q2", tmp_path / "p.html")).read_text(encoding="utf-8")
    # filtros dedicados + JS
    for token in ('id="ff_emp"', 'id="ff_st"', 'id="ff_ext"', 'id="ff_org"', 'id="ff_api"',
                  'id="ff_loc"', 'id="ff_count"', 'id="tab_fontes"', "function fFonteLimpar(",
                  "function fOrdenar(", "th.srt"):
        assert token in html, token
    # todas as fontes renderizadas (antes o CRUD cortava em 300)
    assert html.count("data-emp=") == len(repo.listar()) == 6
    # opcoes derivadas dos dados + data-* para filtrar sem varrer o texto
    assert "data-ext='.pdf'" in html and "data-org='RI'" in html
    assert "data-api='1'" in html and "data-api='0'" in html
    assert "value='CONTAINER'" in html and "<option>ERRO</option>" in html
    DatabaseManager._instance = None


def test_projection_regras_poucos_dados():
    """1 dado -> repete ±15% · 2-5 dados -> média ± 2 desvios-padrão."""
    from statistics import mean, stdev
    from workers.forecast import projetar
    um = projetar([42.0], 3)
    assert um["metodo"] == "REPETIR_15"
    assert um["valores"] == [42.0, 42.0, 42.0]
    assert um["inf"] == [pytest.approx(42.0 * 0.85, abs=1e-3)] * 3
    assert um["sup"] == [pytest.approx(42.0 * 1.15, abs=1e-3)] * 3
    assert um["confianca"] <= 0.3

    serie = [10, 20, 14, 22, 18]
    r = projetar(serie, 3)
    assert r["metodo"] == "MEDIA_2DP" and r["n"] == 5
    m, dp = mean(serie), 2 * stdev(serie)
    assert r["valores"] == [pytest.approx(m, abs=1e-3)] * 3
    assert r["inf"] == [pytest.approx(m - dp, abs=1e-3)] * 3
    assert r["sup"] == [pytest.approx(m + dp, abs=1e-3)] * 3
    assert r["mae"] is None, "regra de poucos dados nao faz backtesting"
    # serie suficiente volta para o backtesting
    assert projetar([10, 11, 12, 13, 12, 13, 14, 15], 3)["metodo"] in (
        "ULTIMA_OBSERVACAO", "SAZONAL_NAIVE", "HOLT_WINTERS_DAMPED")


def test_projection_backtest_e_intervalo():
    """Serie seasonal+tendencia: HW-damped vence e o IC alarga com o horizonte."""
    from workers.forecast import projetar, proximos
    serie = [10, 11, 12, 13, 12, 13, 14, 15, 14, 15, 16, 17]
    r = projetar(serie, 3)
    assert r["metodo"] == "HOLT_WINTERS_DAMPED"
    assert r["mae"] < min(a["mae"] for a in r["alternativas"])
    larguras = [s - i for i, s in zip(r["inf"], r["sup"])]
    assert larguras[2] > larguras[0], "IC95 deve alargar com o horizonte"
    assert r["sigma"] > 0 and 0 < r["confianca"] <= 0.95
    assert proximos(["2026Q2"], 3) == ["2026Q3", "2026Q4", "2027Q1"]
    assert proximos(["2026Q4"], 2) == ["2027Q1", "2027Q2"]


def test_projection_nao_sobrescreve_fato(tmp_path, monkeypatch):
    """Projecao vive em tb_projecao; tb_fato_financeiro fica intacto."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.repositories import FatoRepository, ProjectionRepository
    repo = FatoRepository()
    for q, v in (("2025Q4", 30.0), ("2026Q1", 31.0), ("2026Q2", 33.6)):
        repo.upsert_financeiro("PETROBRAS", q, "RECEITA_LIQUIDA", v, "USD")
    from workers.forecast_run import run_forecast
    resumo = run_forecast(rubricas=["RECEITA_LIQUIDA"])
    assert resumo["projecoes"] == 3
    proj = ProjectionRepository().listar()
    assert [p["periodo_projetado"] for p in proj] == ["2026Q3", "2026Q4", "2027Q1"]
    assert [p["intervalo_inf"] <= p["valor"] <= p["intervalo_sup"] for p in proj] == [True] * 3
    assert len(repo.matriz("2026Q3")) == 0, "projecao nao pode virar fato"
    # rerun e idempotente (UNIQUE por empresa/rubrica/periodo)
    run_forecast(rubricas=["RECEITA_LIQUIDA"])
    assert len(ProjectionRepository().listar()) == 3
    DatabaseManager._instance = None


def test_auditoria_triagem_e_trilha(tmp_path, monkeypatch):
    """Aceitar/rejeitar/ignorar grava trilha e muda o status da fila."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.repositories import QualityRepository
    q = QualityRepository()
    q.para_revisao("PETROBRAS", "2026Q2", "CAPEX", 3.1, "fora do limite")
    q.para_revisao("SHELL", "2026Q2", "FCO", 12.0, "confianca baixa", 0.5)
    fila = q.listar_revisao()
    assert len(fila) == 2
    resumo = q.resumo_auditoria()
    assert resumo["fila_aberta"] == 2 and resumo["aging"]["0-7d"] == 2
    assert resumo["fila_por_status"].get("ABERTO") == 2

    q.decidir("tb_review_queue", fila[0]["id_review"], "ACEITO", "valor conferido no release")
    q.decidir("tb_review_queue", fila[1]["id_review"], "IGNORADO")
    assert q.listar_revisao(apenas_abertos=True) == []
    statuses = {r["status"] for r in q.listar_revisao(apenas_abertos=False)}
    assert {"RESOLVIDO", "IGNORADO"} <= statuses
    trilhas = q.decisoes()
    assert {d["decisao"] for d in trilhas} == {"ACEITO", "IGNORADO"}
    aceito = next(d for d in trilhas if d["decisao"] == "ACEITO")
    assert aceito["comentario"] == "valor conferido no release"
    assert aceito["decidido_em"] and aceito["tabela_ref"] == "tb_review_queue"
    resumo2 = q.resumo_auditoria()
    assert resumo2["fila_aberta"] == 0
    # taxa de resolução: 2 decisões que fecharam item sobre 2 decisões = 100%
    assert resumo2["total_decisoes"] == 2 and resumo2["itens_resolvidos"] == 2
    assert resumo2["taxa_resolucao"] == 100.0
    with pytest.raises(ValueError):
        q.decidir("tb_review_queue", fila[0]["id_review"], "QUALQUER")
    DatabaseManager._instance = None


def test_painel_fontes_cobertura_e_lacunas(tmp_path, monkeypatch):
    """M1: cobertura por periodo (da pasta) e lacunas empresa x periodo."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    pasta = tmp_path / "PETROBRAS" / "2026_1T"
    pasta.mkdir(parents=True)
    arq = pasta / "release.xlsx"
    arq.write_bytes(b"x1")
    from models.repositories import FonteRepository
    repo = FonteRepository()
    repo.registrar("PETROBRAS", "http://ri/p.xlsx", "XLSX", str(arq))
    repo.registrar("SHELL", "http://ri/s.html", "HTML", origem="RI")  # sem pasta local
    from controllers import SourceController
    painel = SourceController().painel_fontes()
    assert painel["cobertura"]["PETROBRAS"] == ["2026Q1"]
    assert painel["periodos"] == ["2026Q1"]
    lacunas = {(l["empresa"], l["periodo"]) for l in painel["lacunas"]}
    assert ("SHELL", "2026Q1") in lacunas and ("PETROBRAS", "2026Q1") not in lacunas
    assert painel["integridade"]["arquivos_ausentes"] == 0
    # rodar o ETL classifica a fonte web como NAO_BAIXADO (nao como erro)
    from workers import etl as etl_mod
    # monkeypatch (e nao atribuicao direta): senao o stub vaza para os
    # testes seguintes e mascara regressoes do scan incremental.
    monkeypatch.setattr(etl_mod, "scan_container", _scan_stub)
    etl_mod.run_etl()
    painel2 = SourceController().painel_fontes()
    assert painel2["resumo"]["nao_baixados"] == 1
    # o .xlsx fake realmente falha no openpyxl: 1 erro, e a fonte web NAO e erro
    assert painel2["resumo"]["com_erro"] == 1
    repo2 = FonteRepository()
    por_status = {r["nome_empresa"]: r["status_processamento"] for r in repo2.listar()}
    assert por_status["SHELL"] == "NAO_BAIXADO"
    assert por_status["PETROBRAS"] == "ERRO"
    assert painel2["cobertura"]["PETROBRAS"] == ["2026Q1"]
    DatabaseManager._instance = None


def test_qualidade_scorecard_dimensoes(tmp_path, monkeypatch):
    """DQS por empresa x periodo: completude baixa quando faltam rubricas; rastreabilidade."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.database import DatabaseManager as _DB
    from models.repositories import FatoRepository
    db = _DB()
    idf = FonteRepository().registrar("PETROBRAS", "http://ri/x.pdf", "PDF")
    repo = FatoRepository()
    for rub in ("RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO"):
        repo.upsert_financeiro("PETROBRAS", "2026Q2", rub, 10.0, "USD", idf, 0.9)
    repo.upsert_financeiro("SHELL", "2026Q1", "RECEITA_LIQUIDA", 20.0, "USD", None, 0.5)
    from workers.quality_score import avaliar_periodo, resumo_scorecard
    card = avaliar_periodo(db, "PETROBRAS", "2026Q2")
    assert card["n_fatos"] == 3 and card["n_esperadas"] == 10
    assert 0 < card["completude"] < 100
    assert card["rastreabilidade"] == 100.0
    assert card["plausibilidade"] == 100.0 and card["consistencia"] > 80
    assert card["classificacao"] in ("REVISAR", "NÃO CONFIÁVEL")
    assert "CAPEX" in card["rubricas_ausentes"]
    # fato sem fonte derruba a rastreabilidade e a consistencia
    card2 = avaliar_periodo(db, "SHELL", "2026Q1")
    assert card2["rastreabilidade"] == 0.0 and card2["consistencia"] < 60
    resumo = resumo_scorecard(db)
    assert resumo["cards"] and resumo["dqs_medio"] > 0
    assert set(resumo["por_dimensao"]) == {"completude", "tempestividade", "plausibilidade",
                                           "consistencia", "rastreabilidade"}
    DatabaseManager._instance = None


def test_qualidade_regras_de_desvio(tmp_path, monkeypatch):
    """Detecta queda de volume, trimestre atrasado, z-score e quebra estrutural."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.repositories import FatoRepository, FonteRepository
    FonteRepository().registrar("PETROBRAS", "http://ri/x.pdf", "PDF")
    repo = FatoRepository()
    # serie estavel + um salto final (z-score) e uma mudanca de nivel
    base = {"2024Q1": 10, "2024Q2": 10, "2024Q3": 10, "2024Q4": 10,
            "2025Q1": 30, "2025Q2": 30, "2025Q3": 30}
    for per, v in base.items():
        repo.upsert_financeiro("PETROBRAS", per, "RECEITA_LIQUIDA", v, "USD", None, 0.9)
    # encher o penultimo periodo para nao disparar CONTAGEM_PERIODO
    for per in ("2024Q1", "2024Q2", "2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q3"):
        for rub in ("CAPEX", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO"):
            repo.upsert_financeiro("PETROBRAS", per, rub, 1.0, "USD", None, 0.9)
    # periodo final com 1 fato apenas -> CONTAGEM_PERIODO + ATRASO_TRIMESTRE
    repo.upsert_financeiro("PETROBRAS", "2025Q4", "RECEITA_LIQUIDA", 90.0, "USD", None, 0.9)
    from workers.quality_score import detectar_desvios, fila_analise, run_quality_score
    from models.database import DatabaseManager as _D2
    alertas = detectar_desvios(_D2())
    codigos = {a["codigo"] for a in alertas}
    assert "CONTAGEM_PERIODO" in codigos
    assert "ATRASO_TRIMESTRE" in codigos
    assert "DRIFT_ZSCORE" in codigos or "QUEBRA_ESTRUTURAL" in codigos
    fila = fila_analise(_D2())
    assert fila and fila[0]["prioridade"] in ("P1", "P2")
    assert any(i["codigo"] == "RUBRICA_AUSENTE" for i in fila)
    r = run_quality_score()
    assert r["cards"] >= 1 and r["desvios"] >= 1 and r["p1"] >= 1
    assert r["alertas_novos"] >= 1, "a 1a execucao cria os alertas"
    assert run_quality_score()["alertas_novos"] == 0, "rodar de novo nao duplica alerta"
    with _DB_score(tmp_path) as _:
        pass
    DatabaseManager._instance = None


def _DB_score(tmp_path):
    from models.database import DatabaseManager
    db = DatabaseManager()
    with db.connect() as conn:
        return conn


def test_qualidade_regras_registradas_e_painel(tmp_path, monkeypatch):
    """tb_regra_alerta e populada e o painel traz scorecard + fila + regras."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.repositories import FatoRepository
    FatoRepository().upsert_financeiro("SHELL", "2026Q2", "RECEITA_LIQUIDA", 60.0, "USD", None, 0.9)
    from workers.quality_score import painel_qualidade, run_quality_score
    run_quality_score()
    p = painel_qualidade()
    assert len(p["regras"]) == 9  # M7.24 adicionou OUTLIER_CROSS_SECTIONAL
    assert {d["codigo"] for d in p["dimensoes"]} == {
        "completude", "tempestividade", "plausibilidade", "consistencia", "rastreabilidade"}
    assert p["resumo"]["dqs_medio"] > 0 and p["cards"]
    assert "fila" in p and isinstance(p["fila"], list)
    DatabaseManager._instance = None


def test_anos_tolerados_pelo_etl():
    """Todo periodo discovery (2023-2026) deve ser reconhecido pelo De-Para de datas."""
    from workers.parse_tab import norm_period
    for ano in (2023, 2024, 2025, 2026):
        for tri in (1, 2, 3, 4):
            celulas = [f"{ano} Q{tri}", f"{ano}_{tri}Q", f"{ano}_{tri}T", f"{tri}T{ano}"]
            assert any(norm_period(c)[0] for c in celulas), celulas


def test_descoberta_relevancia_filtra_ruido(tmp_path, monkeypatch):
    """So comunicado de resultado entra; administrativo 6-K e' descartado com motivo."""
    from workers.discovery import (classificar_relevancia, trimestre_alvo,
                                   trimestre_do_report_date)
    # data de referencia define o trimestre
    assert trimestre_do_report_date("2026-09-30") == "2026Q3"
    assert trimestre_do_report_date("2026-06-30") == "2026Q2"
    assert trimestre_do_report_date("") is None
    # trimestre alvo acompanha o calendario (resultado de T sai em T+1)
    from datetime import date
    assert trimestre_alvo(date(2026, 10, 5)) == "2026Q3"
    assert trimestre_alvo(date(2026, 2, 10)) == "2025Q4"
    # 10-Q/10-K sempre entram
    assert classificar_relevancia("10-Q", "FORM 10-Q", "", True)[0] is True
    # item 2.02 = resultados de operacoes
    assert classificar_relevancia("6-K", "6-K", "2.02", False)[0] is True
    # ruido administrativo e' descartado E vem com motivo
    for titulo in ("IAN TYLER APPOINTED BP CHAIR", "BATCH FILING",
                   "TOTAL VOTING RIGHTS", "PAYMENTS TO GOVTS 2025 PART 1 OF 1"):
        ok, motivo = classificar_relevancia("6-K", titulo, "", False, "2026-09-30", "2026-09-30")
        assert ok is False, titulo
        assert motivo, titulo
    # comunicado de resultado: data de referencia no fim do trimestre + protocolado logo depois
    ok, motivo = classificar_relevancia("6-K", "6-K", "", False, "2026-09-30", "2026-10-01")
    assert ok is True and "resultado" in motivo
    # mesmo reportDate, mas protocolado meses depois = administrativo
    ok, _ = classificar_relevancia("6-K", "6-K", "", False, "2026-09-30", "2026-12-20")
    assert ok is False


def test_descoberta_registra_e_nao_duplica(tmp_path, monkeypatch):
    """Achados entram como DESCOBERTO no catalogo e nao duplicam na 2a rodada."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    import workers.discovery as disc
    from models.repositories import FonteRepository

    db = DatabaseManager()
    repo = FonteRepository(db)
    achado = disc.Achado(empresa="PETROBRAS", origem="SEC", periodo="2026Q3",
                         tipo="HTML", titulo="6-K resultados 3T26",
                         url="https://www.sec.gov/Archives/x/pbr6k.htm",
                         publicado_em="2026-10-01", formulario="6-K")
    disc._registrar(repo, achado, True)
    assert achado.id_fonte
    linhas = [r for r in repo.listar() if r["url_fonte"] == achado.url]
    assert len(linhas) == 1 and linhas[0]["status_processamento"] == "DESCOBERTO"

    # 2a vez: dedup por URL (empresa+url) nao cria linha nova
    outro = disc.Achado(empresa="PETROBRAS", origem="SEC", periodo="2026Q3",
                        tipo="HTML", titulo="6-K resultados 3T26",
                        url="https://www.sec.gov/Archives/x/pbr6k.htm",
                        publicado_em="2026-10-01", formulario="6-K")
    disc._registrar(repo, outro, True)
    assert outro.id_fonte == achado.id_fonte
    assert len([r for r in repo.listar() if r["url_fonte"] == achado.url]) == 1
    DatabaseManager._instance = None


def test_periodo_do_texto_em_comunicado_sec(tmp_path):
    """Periodo no corpo do comunicado (o nome do 6-K nao tem trimestre)."""
    from workers.parse_html import html_para_linhas, periodo_do_texto
    casos = {
        "Net income was $4.0 billion in the third quarter of 2026": ("2026", "Q3"),
        "Revenue of $1.2 billion in 3Q26": ("2026", "Q3"),
        "As of June 30, 2026, with the independent auditors": ("2026", "Q2"),
        "Three months ended March 31, 2026": ("2026", "Q1"),
        "Balance at September 30, 2026": ("2026", "Q3"),
    }
    for texto, esperado in casos.items():
        assert periodo_do_texto([texto]) == esperado, texto
    assert periodo_do_texto(["sem data nenhuma aqui"]) is None


def test_parser_html_de_comunicado_sec(tmp_path):
    """Comunicado 6-K em HTML usa a mesma heuristica de frase do PDF."""
    from workers.parse_html import html_para_linhas, parse_html
    html = ("<html><body><table><tr><td>Net income</td><td>was $4.0 billion "
            "in the third quarter of 2026</td></tr>"
            "<tr><td>Revenue</td><td>was $35.1 billion in the third quarter of 2026"
            "</td></tr></table></body></html>")
    arq = tmp_path / "6k.html"
    arq.write_text(html, encoding="utf-8")
    linhas = html_para_linhas(html)
    # celulas viram espaco (o "|" quebraria os rotulos das regex de frase)
    assert not any("|" in ln for ln in linhas), linhas
    assert any("third quarter of 2026" in ln for ln in linhas)
    assert any(ln.strip().startswith("Net income") for ln in linhas)
    res = parse_html(arq)
    assert res, "parser de HTML nao extraiu nada"
    assert {e.periodo for e in res} == {"2026Q3"}, [e.periodo for e in res]


def test_projecao_cobre_toda_rubrica_com_fato(tmp_path, monkeypatch):
    """A aba Projeções projeta TODA rubrica financeira com fato, não uma lista fixa.

    Regressão real: `RUBRICAS_PROJETAveis` era uma lista fixa de 7 rubricas e
    deixava FCL, DIVIDA_BRUTA e DESPESA_OPERACIONAL sem projeção — sem aviso na tela.
    """
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    db = DatabaseManager()
    from models.repositories import FatoRepository
    from workers.forecast_run import RUBRICAS_EXCLUIDAS, rubricas_do_banco, run_forecast
    fatos = FatoRepository(db)
    rubricas = ["RECEITA_LIQUIDA", "FCL", "DIVIDA_BRUTA", "DESPESA_OPERACIONAL"]
    periodos = ["2025Q4", "2026Q1", "2026Q2"]
    for rubrica in rubricas:
        for i, p in enumerate(periodos):
            fatos.upsert_financeiro("PETROBRAS", p, rubrica, 10.0 + i, "USD", None, 0.9)
    assert set(rubricas) <= set(rubricas_do_banco(db))
    resumo = run_forecast(db, horizonte=2, empresas=["PETROBRAS"])
    for rubrica in rubricas:
        assert rubrica in resumo["cobertura"], f"{rubrica} nao foi projetada"
    assert not (set(rubricas) & set(RUBRICAS_EXCLUIDAS))
    # e nada foi gravado para fora da base de fato
    with db.connect() as conn:
        gravadas = {r["rubrica_padronizada"] for r in conn.execute(
            "SELECT DISTINCT rubrica_padronizada FROM tb_projecao")}
    assert gravadas == set(rubricas), gravadas
    DatabaseManager._instance = None


def test_projecao_intervalo_ignora_sinal_negativo():
    """Série negativa (despesa) não pode inverter o IC95 (inf > sup)."""
    from workers.forecast import METODOS, projetar
    r = projetar([-10.0], horizonte=1)          # 1 dado -> REPETIR_15
    assert r["metodo"] == "REPETIR_15"
    assert r["inf"][0] < r["sup"][0], r
    assert r["inf"][0] < r["valores"][0] < r["sup"][0], r
    r2 = projetar([-10.0, -11.0, -12.0, -9.0, -10.5, -11.5], horizonte=1)
    assert r2["inf"][0] <= r2["valores"][0] <= r2["sup"][0], r2


def test_outlier_cross_sectional_detecta_empresa_fora_da_curva(tmp_path, monkeypatch):
    """M7.24: valor fora da curva dos pares no MESMO trimestre."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    db = DatabaseManager()
    from models.repositories import FatoRepository
    from workers.quality_score import PRIORIDADES, REGRAS, detectar_cross_sectional
    fatos = FatoRepository(db)
    valores = {"BP": 4.0, "SHELL": 4.2, "CHEVRON": 3.9, "TOTALENERGIES": 4.1,
               "EQUINOR": 4.0, "EXXONMOBIL": 4.1}
    for emp, v in valores.items():
        fatos.upsert_financeiro(emp, "2026Q2", "CAPEX", v, "USD", None, 0.9)
    assert detectar_cross_sectional(db) == [], "grupo homogeneo nao gera alerta"

    # outlier por COLAGEM no grupo (0.01 contra pares em ~4.0): o caso real
    fatos.upsert_financeiro("PETROBRAS", "2026Q2", "CAPEX", 0.01, "USD", None, 0.85)
    alertas = detectar_cross_sectional(db)
    assert len(alertas) == 1, alertas
    assert alertas[0]["empresa"] == "PETROBRAS"
    assert "σ" in alertas[0]["descricao"]

    # outlier por AFASTAMENTO (12.0) tambem e' sinalizado, e so ele
    fatos.upsert_financeiro("PETROBRAS", "2026Q2", "CAPEX", 12.0, "USD", None, 0.85)
    alertas = detectar_cross_sectional(db)
    assert len(alertas) == 1, alertas
    achado = alertas[0]
    assert achado["codigo"] == "OUTLIER_CROSS_SECTIONAL"
    assert achado["empresa"] == "PETROBRAS" and achado["periodo"] == "2026Q2"
    assert achado["descricao"].startswith("CAPEX 12.00")
    assert PRIORIDADES["OUTLIER_CROSS_SECTIONAL"] == "P1"
    assert REGRAS["OUTLIER_CROSS_SECTIONAL"]["limiar"] >= 1.5

    # amostra pequena demais (<4 pares) nao alerta: com 3 empresas qualquer diferenca vira z
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t2.db")
    DatabaseManager._instance = None
    db2 = DatabaseManager()
    f2 = FatoRepository(db2)
    for emp in ("BP", "SHELL"):
        f2.upsert_financeiro(emp, "2026Q2", "CAPEX", 4.0, "USD", None, 0.9)
    f2.upsert_financeiro("CHEVRON", "2026Q2", "CAPEX", 0.01, "USD", None, 0.9)
    assert detectar_cross_sectional(db2) == [], "amostra de 3 pares nao deve alertar"
    DatabaseManager._instance = None


def test_contrato_de_dados_detecta_violacao(tmp_path, monkeypatch):
    """Contrato aponta numero invalido com a linha exata (M7.26)."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    db = DatabaseManager()
    from models.repositories import FatoRepository
    from workers.data_contract import rodar_contrato
    fatos = FatoRepository(db)
    fatos.upsert_financeiro("PETROBRAS", "2026Q2", "RECEITA_LIQUIDA", 33.6, "USD", None, 0.9)
    assert rodar_contrato(db)["ok"], "base valida nao pode acusar violacao"

    with db.connect() as conn:                      # receita negativa viola o sinal
        conn.execute("UPDATE tb_fato_financeiro SET valor = -33.6 "
                     "WHERE rubrica_padronizada = 'RECEITA_LIQUIDA'")
        conn.commit()
    r = rodar_contrato(db)
    assert not r["ok"] and r["violacoes"] >= 1
    assert any("RECEITA_LIQUIDA" in v["problema"] for v in r["detalhe"]), r["detalhe"]

    with db.connect() as conn:                      # confianca e periodo invalidos
        conn.execute("UPDATE tb_fato_financeiro SET valor = 33.6")
        conn.execute("UPDATE tb_fato_financeiro SET confianca = 1.7")
        conn.execute("UPDATE tb_fato_financeiro SET periodo = '26Q2'")
        conn.commit()
    r2 = rodar_contrato(db)
    problemas = " | ".join(f"{v['coluna']}: {v['problema']}" for v in r2["detalhe"])
    assert "confianca" in problemas and "periodo" in problemas, problemas
    DatabaseManager._instance = None


def test_incremental_reprocessa_fonte_com_erro(tmp_path, monkeypatch):
    """Fila de retry: fonte em ERRO volta no proximo incremental (M6.7)."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "DOWNLOADS_DIR", tmp_path / "dl")
    DatabaseManager._instance = None
    db = DatabaseManager()
    from models.repositories import FonteRepository
    repo = FonteRepository(db)
    arquivo = tmp_path / "bom.csv"
    arquivo.write_text("Indicador;2026Q2\nReceita de vendas;100\n", encoding="utf-8")
    id_ruim = repo.registrar("BP", "http://x/ruim.xlsx", "XLSX", str(arquivo))
    repo.registrar_processamento(id_ruim, "ERRO", 5, erro="parser corrompido")
    from workers import etl as etl_mod
    monkeypatch.setattr(etl_mod, "scan_container", _scan_stub)
    from workers.etl import run_etl
    r = run_etl(db, only_new=True)
    assert r["arquivos_processados"] >= 1
    assert repo.obter(id_ruim)["status_processamento"] != "ERRO", \
        "fonte com erro deveria voltar para a fila de retry"
    DatabaseManager._instance = None


def test_taxa_resolucao_nao_inflada_por_tipo_de_decisao(tmp_path, monkeypatch):
    """Regressão de M2.6: a taxa de resolução usava o nº de TIPOS de decisão.

    `SELECT decisao, COUNT(*) ... GROUP BY decisao` devolve uma linha por tipo.
    Dividir pelo tamanho dessa lista dava 100% sempre que houvesse ao menos uma
    decisão de cada tipo — com 875 itens abertos na fila e 2 ACEITO + 2 REABERTO o
    painel anunciava "taxa de resolução 100%".
    """
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.repositories import QualityRepository
    q = QualityRepository()
    for i in range(5):
        q.para_revisao("PETROBRAS", "2026Q2", f"RUB{i}", 1.0, "revisar")
    fila = q.listar_revisao()
    q.decidir("tb_review_queue", fila[0]["id_review"], "ACEITO")
    q.decidir("tb_review_queue", fila[1]["id_review"], "ACEITO")
    q.reabrir("tb_review_queue", fila[0]["id_review"], "reabri para conferir")
    r = q.resumo_auditoria()
    # 3 decisões no total, 2 fecharam item (REABERTO não fecha) => 66,7%
    assert r["total_decisoes"] == 3 and r["itens_resolvidos"] == 2
    assert r["taxa_resolucao"] == 66.7
    # 5 na fila - 2 ACEITO que fecharam + 1 que voltou por reabertura = 4 abertas
    assert r["fila_aberta"] == 4
    # sem nenhuma decisão não divide por zero (a base é a mesma: zera só a trilha)
    with q.db.connect() as conn:
        conn.execute("DELETE FROM tb_auditoria_decisao")
        conn.commit()
    assert q.resumo_auditoria()["taxa_resolucao"] == 0.0
    assert q.resumo_auditoria()["total_decisoes"] == 0
    DatabaseManager._instance = None


def test_auditoria_reabre_item_decidido(tmp_path, monkeypatch):
    """Reabertura devolve o item para a fila e preserva a trilha (M2.9)."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    db = DatabaseManager()
    from models.repositories import QualityRepository
    q = QualityRepository(db)
    q.para_revisao("BP", "2026Q2", "RECEITA_LIQUIDA", None, "confianca baixa", 0.5)
    item = q.listar_revisao(apenas_abertos=True)[0]
    q.decidir("tb_review_queue", item["id_review"], "ACEITO", "conferido")
    assert q.listar_revisao(apenas_abertos=False)[0]["status"] == "RESOLVIDO"
    assert q.reabrir("tb_review_queue", item["id_review"], "preciso de novo olhar") is True
    assert q.listar_revisao(apenas_abertos=False)[0]["status"] == "ABERTO"
    assert q.reabrir("tb_review_queue", item["id_review"]) is False   # ja aberto
    with db.connect() as conn:
        trilha = [r[0] for r in conn.execute(
            "SELECT decisao FROM tb_auditoria_decisao WHERE registro_id = ? "
            "ORDER BY id_decisao", (item["id_review"],))]
    assert trilha == ["ACEITO", "REABERTO"], trilha
    DatabaseManager._instance = None


def test_prioridade_escala_com_repeticao(tmp_path, monkeypatch):
    """Fila priorizada e montada e o escalonamento por repeticao existe (M2.11)."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    db = DatabaseManager()
    from models.repositories import FatoRepository
    from workers.quality_score import ESCALA_DISPONIVEL, fila_analise
    fatos = FatoRepository(db)
    for p, v in zip(["2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"],
                    [40.0, 41.0, 42.0, 43.0, 44.0, 90.0]):
        fatos.upsert_financeiro("BP", p, "RECEITA_LIQUIDA", v, "USD", None, 0.9)
    itens = fila_analise(db)
    drifts = [i for i in itens if i["codigo"] == "DRIFT_ZSCORE"]
    assert drifts, "esperava DRIFT_ZSCORE na serie com salto"
    assert ESCALA_DISPONIVEL == {"P3": "P2", "P2": "P1"}, ESCALA_DISPONIVEL
    assert all(i["prioridade"] in ("P1", "P2") for i in drifts), drifts
    DatabaseManager._instance = None


def test_parse_paralelo_equivale_ao_serial(tmp_path, monkeypatch):
    """Paralelismo do parse nao pode mudar o resultado do ETL (M6.6).

    O parse vai para processos e a carga continua sequencial no processo
    principal, na ordem de prioridade: senao a regra "fato bom nunca e rebaixado"
    passaria a depender da ordem de conclusao das tarefas.
    """
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "a.db")
    DatabaseManager._instance = None
    db_a = DatabaseManager()
    # 6 CSV iguais em formato, valores diferentes
    from models.repositories import FonteRepository
    repo_a = FonteRepository(db_a)
    entradas = []
    for i in range(6):
        arq = tmp_path / f"serie_{i}.csv"
        arq.write_text(f"Indicador;2026Q1;2025Q4\nReceita de vendas;{100 + i};{90 + i}\n"
                       f"Lucro liquido;{10 + i};{9 + i}\n", encoding="utf-8")
        entradas.append(str(arq))
    from workers.etl import _parse_em_paralelo
    tarefas = [(i + 1, Path(p), None) for i, p in enumerate(entradas)]

    serial = _parse_em_paralelo(tarefas, 1)
    paralelo = _parse_em_paralelo(tarefas, 3)
    assert set(serial) == set(paralelo)
    for id_fonte in serial:
        erro_s, _, ext_s, _mt_s = serial[id_fonte]
        erro_p, _, ext_p, _mt_p = paralelo[id_fonte]
        assert (erro_s is None) == (erro_p is None)
        # mesmas extracoes, na mesma ordem de campos
        chave = lambda ex: [(e.rubrica, e.periodo, round(float(e.valor), 6)) for e in ex]  # noqa: E731
        assert chave(ext_s) == chave(ext_p), id_fonte
    DatabaseManager._instance = None


def test_descoberta_le_anexos_do_arquivamento(monkeypatch):
    """A demonstracao vem como anexo; o documento principal do 6-K e so a capa."""
    import workers.discovery as disc

    class _Resp:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    index = {"directory": {"item": [
        {"name": "doc.htm", "size": 9_000},                       # capa: < 20 KB
        {"name": "0001-26-index.htm", "size": 40_000},            # ignorado
        {"name": "filing.txt", "size": 900_000},                  # ignorado
        {"name": "ex99-1.htm", "size": 2_100_000},               # demonstrativo
        {"name": "ex99-2.xlsx", "size": 320_000},                # planilha
    ]}}

    def _fake_get(url, **kwargs):
        return _Resp(index)

    monkeypatch.setattr(disc.requests, "get", _fake_get)
    anexos, erro = disc.anexos_sec("1119639", "0001292814-26-004760", "doc.htm")
    assert erro is None
    nomes = [a["nome"] for a in anexos]
    assert "doc.htm" not in nomes, "a capa nao e anexo"
    assert "0001-26-index.htm" not in nomes and "filing.txt" not in nomes
    assert "ex99-1.htm" in nomes and "ex99-2.xlsx" in nomes
    grande = next(a for a in anexos if a["nome"] == "ex99-1.htm")
    assert grande["provavel_demonstrativo"] is True
    # a capa nunca entra na lista de provaveis (9 KB)
    assert all(a["provavel_demonstrativo"] for a in anexos if a["nome"].startswith("ex99"))


def test_glossario_de_indicadores():
    """Todo indicador tem definicao; todo derivado tem formula e dependencias."""
    from models.glossario import GLOSSARIO, obter, por_categoria, resumo
    assert len(GLOSSARIO) >= 15
    vistos = set()
    for g in GLOSSARIO:
        assert g["codigo"] not in vistos, f"codigo repetido: {g['codigo']}"
        vistos.add(g["codigo"])
        assert g["nome"] and g["definicao"] and len(g["definicao"]) > 30, g["codigo"]
        assert g["categoria"] in ("Financeiro", "Operacional", "Derivado",
                                  "Mercado", "Nao catalogado"), g
        if g["categoria"] == "Derivado":
            assert g["formula"], f"{g['codigo']} e derivado e precisa de formula"
            assert g["depende"], f"{g['codigo']} sem dependencias declaradas"
            for dep in g["depende"]:
                assert dep in vistos or dep in {x["codigo"] for x in GLOSSARIO}, dep
    # os derivados do painel (workers/derived.py) tem de estar documentados
    for codigo in ("MARGEM_EBITDA", "MARGEM_LIQUIDA", "DIVIDA_LIQUIDA_EBITDA",
                   "RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "PRODUCAO_BOED",
                   "EFETIVO_TOTAL", "FCL", "CAPEX"):
        assert obter(codigo)["definicao"], codigo
    # rubrica fora do glossario precisa de aviso explicito (De-Para automatico)
    fallback = obter("RUBRICA_DESCONHECIDA_XYZ")
    assert fallback["categoria"] == "Nao catalogado" and fallback["formula"] is None
    assert "De-Para" in fallback["fonte"], fallback
    # agrupamento e busca
    cats = {c["categoria"] for c in por_categoria()}
    assert {"Financeiro", "Operacional", "Derivado"} <= cats
    assert len(resumo()["indicadores"]) == len(GLOSSARIO)
    assert {g["codigo"] for g in resumo()["indicadores"]} == vistos


def test_glossario_na_web_e_na_gui():
    """Aba Glossario existe no painel Web (11 abas) e na GUI (8 abas)."""
    from config import WEB_HTML
    html = WEB_HTML.read_text(encoding="utf-8")
    assert 'onclick="tab(10)">Glossário<' in html
    assert 'id="glo_box"' in html and "function gloCarregar()" in html
    assert "/api/glossario" in html
    # 11 abas no painel (o container usa class="tabs", a ativa class="tab on")
    assert html.count('onclick="tab(') == 11, html.count('onclick="tab(')


def test_csv_com_uma_unica_coluna_de_periodo(tmp_path, monkeypatch):
    """Planilha de uma coluna so (so o trimestre atual) precisa extrair.

    Regressao: o cabecalho so era aceito com >= 2 colunas de periodo, entao
    "Indicador;2026Q2" (shape comum de planilha de trimestre) nao gerava fato
    nenhum e a fonte ficava SEM_DADOS sem explicacao.
    """
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from workers.etl import escolher_parser
    uma = tmp_path / "uma_coluna.csv"
    uma.write_text("Indicador;2026Q2\nReceita de vendas;33607\nEBITDA ajustado;18615\n",
                   encoding="utf-8")
    res = escolher_parser(uma)(uma)
    periodos = {e.periodo for e in res}
    assert periodos == {"2026Q2"}, periodos
    rubricas = {e.rubrica for e in res}
    assert "RECEITA_LIQUIDA" in rubricas, rubricas
    # coluna unica de "Q3" SEM ano continua rejeitada (evita numero solto virar trimestre)
    sem_ano = tmp_path / "sem_ano.csv"
    sem_ano.write_text("Indicador;Q3\nReceita de vendas;33607\nTotal de cros\n", encoding="utf-8")
    assert escolher_parser(sem_ano)(sem_ano) == []
    # e as formas com varias colunas seguem igual
    duas = tmp_path / "duas.csv"
    duas.write_text("Indicador;2026Q2;2025Q4\nReceita de vendas;33607;30000\n",
                    encoding="utf-8")
    assert {e.periodo for e in escolher_parser(duas)(duas)} == {"2026Q2", "2025Q4"}
    DatabaseManager._instance = None


def test_scanner_escolhe_o_nome_mais_descritivo(tmp_path, monkeypatch):
    """Arquivos de mesmo conteudo: fica o de nome melhor, nao a copia."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    import workers.scanner as scanner
    from models.repositories import FonteRepository
    raiz = tmp_path / "CONTEINER" / "PETROBRAS"
    raiz.mkdir(parents=True)
    original = raiz / "Demonstracoes Financeiras 1T26 - US$.pdf"
    original.write_bytes(b"%PDF-1.4\nconteudo igual")
    copia = raiz / "copia do demonstrativo.pdf"
    copia.write_bytes(b"%PDF-1.4\nconteudo igual")
    monkeypatch.setattr(scanner, "CONTAINER_DIR", tmp_path / "CONTEINER")

    repo = FonteRepository(DatabaseManager())
    ids: set[int] = set()
    stats = scanner.scan_container(repo, tmp_path / "CONTEINER", ids, incluir_downloads=False)
    assert stats["novos"] == 1 and stats["duplicados"] == 1, stats
    nomes = [r["nome_documento"] for r in repo.listar()]
    assert nomes == ["Demonstracoes Financeiras 1T26 - US$.pdf"], nomes
    DatabaseManager._instance = None


def test_pdf_fallback_oxide_quando_mupdf_falha(tmp_path, monkeypatch):
    """Se o PyMuPDF nao devolve texto, o PDFOxide (Rust) entra como resiliencia.

    O PDFOxide NAO e o extrator principal (benchmark M8.8: 2,8x mais lento e
    0 tabelas nos DFs da Petrobras) — cobre apenas o caso de PDF corrompido.
    """
    from workers import parse_pdf as pp
    pdf_real = next(CONTAINER_DIR.rglob("*Desempenho Financeiro Petrobras 1T25.pdf"))
    destino = tmp_path / "Desempenho Financeiro Petrobras 1T25.pdf"
    destino.write_bytes(pdf_real.read_bytes())

    monkeypatch.setattr(pp, "page_texts", lambda path, max_pages=12: [])
    monkeypatch.setattr(pp, "ENABLE_EXTRATOR_ALTERNATIVO", True)
    try:
        import pdf_oxide  # noqa: F401
    except ImportError:
        return  # opcional: sem a lib o fallback simply nao existe
    fallback = pp.page_texts_alternativo(destino, 6)
    assert fallback and sum(len(t) for t in fallback) > 500, "fallback nao extraiu texto"

    # com o fallback desligado, nao ha texto; e o fallback nunca pode derrubar o parse
    monkeypatch.setattr(pp, "ENABLE_EXTRATOR_ALTERNATIVO", False)
    monkeypatch.setattr(pp, "extract_tables", lambda path, max_pages=8: [])
    assert pp.parse_pdf(destino) == []
    # PDFOxide e Rust/pyo3: um PDF truncado gera panico (BaseException, nao Exception)
    monkeypatch.setattr(pp, "ENABLE_EXTRATOR_ALTERNATIVO", True)
    lixo = tmp_path / "Demonstracoes Financeiras 3T25 - REAIS.pdf"
    lixo.write_bytes(b"%PDF-1.4\n" + b"z" * 512)          # nao e um PDF valido
    assert pp.page_texts_alternativo(lixo, 6) == []
    monkeypatch.setattr(pp, "page_texts", lambda path, max_pages=12: [])
    assert pp.parse_pdf(lixo) == []                        # ETL nao quebra


def test_revisao_entre_execucoes_com_execucao_sem_carga(tmp_path, monkeypatch):
    """Execucao incremental sem trabalho novo grava cargas=0 e nao pode quebrar o painel.

    Regressao real: a guarda checava execucao[0] mas dividia por execucao[1],
    que era 0 depois de um `etl --novos` sem arquivo novo -> ZeroDivisionError
    ao abrir a aba Qualidade (Web e GUI).
    """
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    db = DatabaseManager()
    from models.repositories import FonteRepository
    fontes = FonteRepository(db)
    # execucao 1: com carga | execucao 2: sem carga (incremental no-op)
    id1 = fontes.abrir_execucao()
    fontes.fechar_execucao(id1, arquivos=3, extracoes=9, cargas=5)
    id2 = fontes.abrir_execucao()
    fontes.fechar_execucao(id2, arquivos=0, extracoes=0, cargas=0)

    from workers.quality_score import _revisao_entre_execucoes, painel_qualidade
    assert _revisao_entre_execucoes(db) == []          # nao lanca ZeroDivisionError
    painel_qualidade(db)                               # aba Qualidade abre sem erro
    # com as duas execucoes seguintes tendo carga, o alerta de mudanca volta
    id3 = fontes.abrir_execucao()
    fontes.fechar_execucao(id3, arquivos=1, extracoes=2, cargas=1)
    id4 = fontes.abrir_execucao()          # a anterior (id3) tem carga, entao alerta
    fontes.fechar_execucao(id4, arquivos=1, extracoes=3, cargas=2)
    alertas = _revisao_entre_execucoes(db)
    assert any(a["codigo"] == "REVISAO_ENTRE_EXECUCOES" for a in alertas), alertas
    DatabaseManager._instance = None


# ---------------------------------------------------------------- M8: leitura de PDF
def test_classificacao_pdf_nomes_hostis():
    """Nomes reais do Container: acento, espaco, hifen, cifrao e plural.

    Regressao do bug em que 'Transcricao 1T25.pdf' (com acento) era parseado
    e '_Demonstracoes Financeiras 1T26 - US$.pdf' dependia da grafia exata.
    """
    from workers.naming import classificar_documento, moeda_do_nome, normalizar_nome
    # narrativos (nao tem tabela) -> nunca entram no ETL numerico
    for nome in ("Transcricao 1T25.pdf", "Transcricao Webcast 3T25.pdf",
                 "bp-fourth-quarter-2025-results-presentation-slides.pdf",
                 "bp-first-quarter-2026-results-qa-transcript.pdf",
                 "4Q25 Earnings Press Release Website.pdf".replace("Website", "Presentation"),
                 "2025 4Q Earnings Conference Call Presentation Only.pdf",
                 "4Q25 Prepared Remarks.pdf"):
        ok, motivo = classificar_documento(nome)
        assert not ok, f"{nome} nao devia entrar ({motivo})"
    # numericos (podem entrar mesmo com pontuacao/cifrao)
    for nome in ("_Demonstracoes Financeiras 1T26  - US$.pdf",
                 "Desempenho Financeiro da Petrobras 1T25 (em dolar).pdf",
                 "DFS R$ Portugues.pdf", "ITR Reais Port.pdf",
                 "Relatorio Fiscal 3Q25.pdf", "Demonstracoes Financeiras 2T26 -REAIS.pdf",
                 "bp-second-quarter-2026-results-supplementary-info-rim.pdf"):
        ok, motivo = classificar_documento(nome)
        assert ok, f"{nome} devia entrar, mas foi barrado: {motivo}"
    # normalizacao e moeda
    assert normalizar_nome("Relatório Fiscal 3Q25.pdf") == "relatorio fiscal 3q25 pdf"
    assert moeda_do_nome("_Demonstracoes Financeiras 1T26 - US$.pdf") == "USD"
    assert moeda_do_nome("DFS R$ Portugues.pdf") == "BRL"
    assert moeda_do_nome("Desempenho Financeiro (em dólar).pdf") == "USD"
    # sem sinal linguistico: decide por tamanho
    assert classificar_documento("0000034088-26-000093.pdf", 100)[0] is True
    assert classificar_documento("0000034088-26-000093.pdf", 9_000_000)[0] is False


def test_hints_de_periodo_de_nomes_reais():
    """1T26 / 3Q25 / q2-2026 / 2025 3T: padroes locais eSaga, nao so o formato BP."""
    from workers.naming import periodo_do_nome
    casos = {
        "Desempenho Financeiro da Petrobras 1T25 (em dolar).pdf": ("2025", "Q1"),
        "_Demonstracoes Financeiras 1T26  - US$.pdf": ("2026", "Q1"),
        "Demonstracoes Financeiras 2T26 -REAIS.pdf": ("2026", "Q2"),
        "Relatorio Fiscal 3Q25.pdf": ("2025", "Q3"),
        "bp-fourth-quarter-2025-results.pdf": ("2025", "Q4"),
        "Relatorio Fiscal 2025.pdf": ("2025", ""),
        "ITR Reais Port.pdf": None,
    }
    for nome, esperado in casos.items():
        assert periodo_do_nome(nome) == esperado, nome


def test_etl_incremental_processa_so_novos(tmp_path, monkeypatch):
    """Opcao 3 do .bat (etl --novos): varre o Container e so parseia os novos."""
    import config as cfg
    import workers.scanner as scanner
    from models.repositories import FonteRepository, sha256_file
    from workers.etl import run_etl

    raiz = tmp_path / "CONTEINER"
    (raiz / "BP").mkdir(parents=True)
    monkeypatch.setattr(cfg, "CONTAINER_DIR", raiz)
    monkeypatch.setattr(cfg, "DB_PATH", tmp_path / "incr.db")
    # isola da pasta de downloads real (o ETL tambem a varre)
    monkeypatch.setattr(cfg, "DOWNLOADS_DIR", tmp_path / "downloads_vazio")
    monkeypatch.setattr(scanner, "CONTAINER_DIR", raiz)
    DatabaseManager._instance = None
    db = DatabaseManager()
    repo = FonteRepository(db)
    # arquivo base JA PROCESSADO: nao pode ser reprocessado no modo incremental
    base = raiz / "BP" / "Relatorio Fiscal 1T25.pdf"
    base.write_bytes(b"%PDF-1.4\n" + b"x" * 400)
    id_base = repo.registrar(nome_empresa="BP", url="https://ri.bp.com/x.pdf", tipo="PDF",
                             caminho=str(base), status="CATALOGADO")
    repo.registrar_processamento(id_base, "SEM_DADOS", 10, erro="ja visto")

    # 1) sem nada novo -> nada processado
    r0 = run_etl(db, only_new=True)
    assert r0["scan"]["novos"] == 0 and r0["arquivos_processados"] == 0, r0

    # 1b) arquivo catalogado mas NUNCA processado (ex.: baixado depois pelo
    #     `descoberta --baixar`) tem de entrar: e o que fecha o ciclo
    orfa = raiz / "BP" / "Demonstracoes Financeiras 2T26 - US$.pdf"
    orfa.write_bytes(b"%PDF-1.4\n" + b"z" * 300)
    repo.registrar(nome_empresa="BP", url="https://ri.bp.com/orfa.pdf", tipo="PDF",
                   caminho=str(orfa), status="DESCOBERTO")
    r0b = run_etl(db, only_new=True)
    assert r0b["arquivos_processados"] == 1, r0b

    # 2) arquivo novo (nome hostil: acento + espaco + cifrao) entra e e processado
    novo = raiz / "BP" / "Demonstracoes Financeiras 3T25 - R$ (novo).pdf"
    novo.write_bytes(b"%PDF-1.4\n" + b"y" * 512)
    r1 = run_etl(db, only_new=True)
    assert r1["scan"]["novos"] == 1, r1["scan"]
    assert r1["arquivos_processados"] == 1, r1
    docs = [r["nome_documento"] for r in repo.listar()]
    assert novo.name in docs

    # 3) idempotencia: rodar de novo nao reprocessa nada
    r2 = run_etl(db, only_new=True)
    assert r2["scan"]["novos"] == 0 and r2["arquivos_processados"] == 0

    # 4) duplicata por hash nao vira fonte nova
    dup = raiz / "BP" / "copia do novo.pdf"
    dup.write_bytes(novo.read_bytes())
    r3 = run_etl(db, only_new=True)
    assert r3["scan"]["novos"] == 0 and r3["scan"]["duplicados"] >= 1, r3["scan"]
    assert sha256_file(novo) == sha256_file(dup)
    DatabaseManager._instance = None


# ------------------------------------------------- M8.12: metrica de leitura do PDF
def _pdf_real(nome_parcial: str):
    """PDF real do Container (as metricas so fazem sentido em documento de verdade)."""
    achado = next(CONTAINER_DIR.rglob(nome_parcial), None)
    if achado is None:
        pytest.skip(f"PDF do Container ausente: {nome_parcial}")
    return achado


def test_metrica_pdf_paginas_e_tabelas(tmp_path):
    """M8.12: conta páginas do documento, páginas lidas e tabelas detectadas.

    `paginas` é o total do arquivo e `paginas_lidas` o que o parse percorreu: um DF
    de 37 páginas lido até a 12ª é o caso em que misturar os dois esconderia custo.
    """
    from workers.parse_pdf import metricas, n_paginas
    real = _pdf_real("*Desempenho Financeiro Petrobras 1T25.pdf")
    local = tmp_path / real.name
    local.write_bytes(real.read_bytes())
    total = n_paginas(local)
    assert total > 1, "o Container nao tem um PDF de verdade"
    m = metricas(local, max_pages=12)
    assert m["paginas"] == total
    assert m["paginas_lidas"] == min(total, 12)
    assert m["tabelas"] >= 1, "o DF da Petrobras tem tabelas detectaveis"
    # arquivo que nao e PDF: metrica zerada, sem excecao (o ETL nao pode quebrar)
    lixo = tmp_path / "nao-e-pdf.pdf"
    lixo.write_bytes(b"%PDF-1.4\n" + b"z" * 128)
    assert metricas(lixo) == {"paginas": 0, "paginas_lidas": 0, "tabelas": 0}


def test_etl_grava_paginas_e_tabelas_por_documento(tmp_path, monkeypatch):
    """A métrica do PDF vai para tb_fonte_dados e para a execução, e aparece no painel."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from workers import etl as etl_mod
    monkeypatch.setattr(etl_mod, "scan_container", _scan_stub)
    real = _pdf_real("*Desempenho Financeiro Petrobras 1T25.pdf")
    pdf = tmp_path / real.name
    pdf.write_bytes(real.read_bytes())
    from models.repositories import FonteRepository
    repo = FonteRepository()
    id_pdf = repo.registrar("PETROBRAS", "http://ri/df.pdf", "PDF", str(pdf))
    csv = tmp_path / "b.csv"
    csv.write_text("Indicador;2026Q2\nReceita de vendas;33607\n", encoding="utf-8")
    id_csv = repo.registrar("SHELL", "http://ri/b.csv", "CSV", str(csv))

    from workers.etl import run_etl
    resumo = run_etl()
    assert resumo["pdfs_medidos"] == 1, resumo          # so o PDF tem métrica
    assert resumo["paginas_lidas"] > 0 and resumo["tabelas_detectadas"] >= 1

    linha_pdf = repo.obter(id_pdf)
    assert linha_pdf["n_paginas"] > 1 and linha_pdf["n_tabelas"] >= 1
    # o throughput usa paginas LIDAS (limitadas pela politica de profundidade),
    # nunca o total do arquivo — senao um DF de 37 pags lido ate a 12 contaria 37
    assert linha_pdf["n_paginas_lidas"] == min(linha_pdf["n_paginas"], 12)
    # CSV nao tem pagina: None (nao medido), e nao 0 (medido zero) — a distincao
    # importa para a media do painel nao dividir por documentos sem pagina.
    assert repo.obter(id_csv)["n_paginas"] is None

    painel = repo.resumo_etl()
    assert painel["pdf"]["documentos"] == 1
    assert painel["pdf"]["paginas"] == linha_pdf["n_paginas"]
    assert painel["pdf"]["paginas_lidas"] == linha_pdf["n_paginas_lidas"]
    assert painel["pdf"]["paginas_por_seg"] > 0
    assert painel["ultimas_paginas"] == linha_pdf["n_paginas_lidas"]
    assert painel["ultimas_tabelas"] == linha_pdf["n_tabelas"]
    execucao = repo.execucoes()[0]
    assert execucao["paginas_lidas"] == linha_pdf["n_paginas_lidas"]
    assert execucao["tabelas_detectadas"] == linha_pdf["n_tabelas"]
    DatabaseManager._instance = None


def test_parse_task_devolve_metrica_do_pdf(tmp_path):
    """parse_arquivo devolve (erro, ms, extracoes, metrica); serial e paralelo iguais."""
    from workers.parse_task import parse_arquivo
    real = _pdf_real("*Desempenho Financeiro Petrobras 1T25.pdf")
    pdf = tmp_path / real.name
    pdf.write_bytes(real.read_bytes())
    erro, ms, extrações, metrica = parse_arquivo(str(pdf))
    assert erro is None and ms >= 0 and metrica["paginas"] > 1
    # CSV: metrica vazia, e a tupla continua com 4 posicoes
    csv = tmp_path / "b.csv"
    csv.write_text("Indicador;2026Q2\nReceita de vendas;1\n", encoding="utf-8")
    erro2, _ms2, _ext2, metrica2 = parse_arquivo(str(csv))
    assert erro2 is None and metrica2 == {}


def test_metrica_pdf_no_painel_etl_api(tmp_path, monkeypatch):
    """GET /api/etl entrega o bloco de métrica de PDF usado pela aba Gestão ETL."""
    import json as _json
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from workers import etl as etl_mod
    monkeypatch.setattr(etl_mod, "scan_container", _scan_stub)
    real = _pdf_real("*Desempenho Financeiro Petrobras 1T25.pdf")
    pdf = tmp_path / real.name
    pdf.write_bytes(real.read_bytes())
    from models.repositories import FonteRepository
    FonteRepository().registrar("PETROBRAS", "http://ri/df.pdf", "PDF", str(pdf))
    from workers.etl import run_etl
    run_etl()
    from views.web_server import DashboardHandler
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_address[1]}/api/etl",
                                    timeout=30) as r:
            j = _json.loads(r.read().decode())
        assert j["resumo"]["pdf"]["documentos"] == 1
        assert j["resumo"]["pdf"]["paginas_por_seg"] > 0
        fonte = next(f for f in j["fontes"] if f["extensao"] == ".pdf")
        assert fonte["n_paginas"] > 1 and fonte["n_tabelas"] >= 1
    finally:
        httpd.shutdown()
        httpd.server_close()
    DatabaseManager._instance = None


def test_backfill_metrica_dos_pdfs_ja_processados(tmp_path, monkeypatch):
    """PDF já processado continua sem métrica; o backfill mede e é idempotente."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from workers import etl as etl_mod
    monkeypatch.setattr(etl_mod, "scan_container", _scan_stub)
    real = _pdf_real("*Desempenho Financeiro Petrobras 1T25.pdf")
    pdf = tmp_path / real.name
    pdf.write_bytes(real.read_bytes())
    from models.repositories import FonteRepository
    repo = FonteRepository()
    id_pdf = repo.registrar("PETROBRAS", "http://ri/df.pdf", "PDF", str(pdf))
    # parse normal ja grava a métrica
    from workers.etl import run_etl
    run_etl()
    assert repo.obter(id_pdf)["n_paginas"] is not None
    # arquivo que sumiu do disco: não pode virar "0 páginas" (seria medir e não ter).
    # conteúdo diferente do anterior: hash igual faria o registrar deduplicar e
    # devolver o MESMO id_fonte, e o teste passaria sem exercitar nada.
    sumiu = tmp_path / "Demonstracoes Financeiras 1T25.pdf"
    sumiu.write_bytes(real.read_bytes() + b"\n% registro proprio\n")
    id_sumiu = repo.registrar("BP", "http://bp/x.pdf", "PDF", str(sumiu))
    assert id_sumiu != id_pdf
    sumiu.unlink()
    repo.registrar_processamento(id_sumiu, "NAO_PROCESSADO", 1)

    from workers.pdf_metrics import medir_metricas_pdf
    r = medir_metricas_pdf(jobs=1)
    assert r["sem_arquivo"] == 1                    # pulado, não zerado
    assert repo.obter(id_sumiu)["n_paginas"] is None
    # o que já tem métrica não é re-medido
    assert r["medidos"] == 0
    assert medir_metricas_pdf(jobs=1)["medidos"] == 0
    DatabaseManager._instance = None


def test_backfill_metrica_preenche_pdf_nunca_parsed(tmp_path, monkeypatch):
    """Fonte catalogada e nunca parseada entra no backfill e passa a ter métrica."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    real = _pdf_real("*Desempenho Financeiro Petrobras 1T25.pdf")
    pdf = tmp_path / real.name
    pdf.write_bytes(real.read_bytes())
    from models.repositories import FonteRepository
    repo = FonteRepository()
    id_pdf = repo.registrar("PETROBRAS", "http://ri/df.pdf", "PDF", str(pdf))
    assert repo.obter(id_pdf)["n_paginas"] is None
    from workers.pdf_metrics import medir_metricas_pdf
    r = medir_metricas_pdf(jobs=1)
    assert r["medidos"] == 1 and r["paginas"] > 1 and r["tabelas"] >= 1
    linha = repo.obter(id_pdf)
    assert linha["n_paginas"] == r["paginas"]
    assert linha["n_paginas_lidas"] == min(linha["n_paginas"], 12)
    # rodando de novo não remede nada
    assert medir_metricas_pdf(jobs=1)["medidos"] == 0

    import app_main
    assert app_main.main(["fontes", "metrica"]) == 0
    DatabaseManager._instance = None


# ------------------------------------------------- apresentacao PPTX
def test_pptx_gera_deck_com_numeros_do_banco(tmp_path, monkeypatch):
    """O deck é gerado do banco: 23 slides, cores Petrobras e nenhum número inventado."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.repositories import FatoRepository, FonteRepository
    idf = FonteRepository().registrar("PETROBRAS", "http://ri/x.pdf", "PDF")
    repo = FatoRepository()
    for rub in ("RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO"):
        repo.upsert_financeiro("PETROBRAS", "2026Q2", rub, 10.0, "USD", idf, 0.9)
    repo.upsert_financeiro("SHELL", "2026Q2", "RECEITA_LIQUIDA", 20.0, "USD", idf, 0.9)
    from workers.quality_score import run_quality_score
    run_quality_score()

    from workers.apresentacao_pptx import (AMARELO, VERDE, _numeros, construir)
    destino = tmp_path / "deck.pptx"
    caminho = construir(destino)
    assert Path(caminho) == destino and destino.exists()
    assert destino.read_bytes()[:2] == b"PK"          # container OOXML (zip)

    from pptx import Presentation
    prs = Presentation(str(destino))
    assert len(prs.slides) >= 20, "a apresentação cobre todos os tópicos do projeto"
    # nenhum elemento pode estar fora da área do slide
    for i, slide in enumerate(prs.slides, start=1):
        for forma in slide.shapes:
            assert forma.left >= -9144, f"slide {i}: forma fora do slide"
            assert forma.left + forma.width <= prs.slide_width + 9144, \
                f"slide {i}: forma estoura a largura"
            assert forma.top + forma.height <= prs.slide_height + 9144, \
                f"slide {i}: forma estoura a altura"
    # paleta da Petrobras presente no XML. O .pptx é um zip, então as cores estão
    # no XML COMPRIMIDO do slide — procurar no binário cru não acha (verificado).
    import zipfile
    xml = b"".join(zipfile.ZipFile(destino).read(nome)
                   for nome in zipfile.ZipFile(destino).namelist()
                   if nome.endswith(".xml"))
    for cor in (VERDE, AMARELO):
        assert cor.encode() in xml, cor
    # os números do banco aparecem no deck
    n = _numeros()
    texto = " ".join(f.text_frame.text for s in prs.slides for f in s.shapes
                     if f.has_text_frame)
    for valor in (str(n["fatos"]), str(n["fontes"]), str(n["projecoes"]), str(n["dqs"])):
        assert valor in texto, f"número do banco ausente no deck: {valor}"
    assert str(n["fatos"]) != "0" and n["dqs"] > 0
    DatabaseManager._instance = None


def test_kpis_exige_valor_no_primeiro_lugar(tmp_path, monkeypatch):
    """(rótulo, valor) invertido na _kpis produz slide com legenda no lugar do número.

    Regressão real: numa faixa só, o par invertido mostrava "empresas comparadas / 7".
    A ordem da tupla é conferida na função, não conferida a olho no slide.
    """
    pytest.importorskip("pptx")
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from workers import apresentacao_pptx as ap
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = ap._slide(prs)
    ap._kpis(s, [(42, "quarenta e dois", ap.VERDE)])
    texto = " ".join(f.text_frame.text for f in s.shapes if f.has_text_frame)
    assert "42" in texto and "quarenta e dois" in texto
    with pytest.raises(ValueError):
        ap._kpis(s, [("rotulo-sem-numero", ap.VERDE)])
    DatabaseManager._instance = None


def test_validar_pptx_detecta_forma_fora_do_slide(tmp_path, monkeypatch):
    """O validador só é útil se pegar estouro de caixa — testar o teste."""
    pytest.importorskip("pptx")
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from workers import apresentacao_pptx as ap
    from workers.validar_pptx import validar
    from pptx import Presentation
    from pptx.util import Inches

    destino = tmp_path / "ruim.pptx"
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.shapes.add_textbox(Inches(12.0), Inches(7.0), Inches(4.0), Inches(1.0))
    prs.save(str(destino))
    problemas = validar(destino)
    assert problemas and any("estoura" in p or "fora do slide" in p for p in problemas), problemas

    # deck íntegro: o mesmo validador não acusa nada
    ok = tmp_path / "ok.pptx"
    ap.construir(ok, n=ap._numeros())
    assert validar(ok) == []
    DatabaseManager._instance = None


def test_pptx_pelo_cli(tmp_path, monkeypatch):
    """`app_main.py pdf --pptx` gera o deck no caminho pedido."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    import app_main
    saida = tmp_path / "deck_cli.pptx"
    assert app_main.main(["pdf", "--pptx", "--saida", str(saida)]) == 0
    assert saida.exists() and saida.read_bytes()[:2] == b"PK"
    DatabaseManager._instance = None


# ------------------------------------------------- M7.23: scorecard historico
def test_historico_scorecar_registra_somente_mudanca(tmp_path, monkeypatch):
    """O histórico guarda o DQS ao longo do tempo, mas só quando ele MUDA.

    Gravar a cada execução produziria uma série com repetição — o painel mostra
    evolução da qualidade, não log de execução.
    """
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.database import DatabaseManager as _DB
    from models.repositories import FatoRepository, FonteRepository
    idf = FonteRepository().registrar("PETROBRAS", "http://ri/x.pdf", "PDF")
    repo = FatoRepository()
    for rub in ("RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO"):
        repo.upsert_financeiro("PETROBRAS", "2026Q2", rub, 10.0, "USD", idf, 0.9)
    from workers.quality_score import historico_scorecard, run_quality_score
    db = _DB()
    run_quality_score()
    h1 = historico_scorecard(db)
    assert h1["empresas"] == 1 and h1["periodos"] == ["2026Q2"]
    emp = h1["por_empresa"]["PETROBRAS"]
    assert emp["dqs_atual"] == emp["dqs_inicial"] == h1["dqs_atual"] > 0
    assert emp["variacao_total"] == 0.0 and emp["periodos"] == 1
    assert emp["pontos"][0]["variacao"] is None       # 1o ponto nao tem variacao

    # rodar de novo sem mudar nada nao cria ponto novo
    run_quality_score()
    with db.connect() as conn:
        n1 = conn.execute("SELECT COUNT(*) c FROM tb_qualidade_historico").fetchone()["c"]
    assert n1 == 1, "DQS igual nao pode virar ponto novo"
    assert historico_scorecard(db)["por_empresa"]["PETROBRAS"]["periodos"] == 1

    # dois trimestres a menos: a serie cresce com o score de cada um. A
    # tempestividade cai para 60 em periodo que nao e o mais recente, entao o DQS
    # dos antigos e MENOR que o do ultimo — e exatamente isso que a serie mostra.
    for per in ("2025Q4", "2026Q1"):
        for rub in ("RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO"):
            repo.upsert_financeiro("PETROBRAS", per, rub, 10.0, "USD", idf, 0.9)
    run_quality_score()
    h2 = historico_scorecard(db)
    assert len(h2["periodos"]) == 3
    emp2 = h2["por_empresa"]["PETROBRAS"]
    assert emp2["periodos"] == 3
    assert [p["periodo"] for p in emp2["pontos"]] == ["2025Q4", "2026Q1", "2026Q2"]
    assert emp2["pontos"][0]["variacao"] is None
    assert emp2["dqs_inicial"] < emp2["dqs_atual"]
    assert len(h2["media_por_periodo"]) == 3
    assert h2["variacao_media"] > 0 and h2["melhorou"]["empresa"] == "PETROBRAS"
    DatabaseManager._instance = None


def test_historico_scorecard_caixa_quando_base_vazia(tmp_path, monkeypatch):
    """Base sem scorecard não pode quebrar o painel (divisão por zero / lista vazia)."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.database import DatabaseManager as _DB
    from workers.quality_score import historico_scorecard
    h = historico_scorecard(_DB())
    assert h == {"empresas": 0, "periodos": [], "por_empresa": {}, "serie_empresa": None,
                 "media_por_periodo": [], "melhorou": None, "piorou": None,
                 "dqs_atual": 0.0, "dqs_inicial": 0.0, "variacao_media": 0.0}
    DatabaseManager._instance = None


def test_historico_scorecard_no_painel_e_cli(tmp_path, monkeypatch):
    """painel_qualidade traz o histórico e o CLI mostra a evolução."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.repositories import FatoRepository, FonteRepository
    idf = FonteRepository().registrar("SHELL", "http://ri/y.pdf", "PDF")
    repo = FatoRepository()
    for per in ("2025Q4", "2026Q1"):
        for rub in ("RECEITA_LIQUIDA", "EBITDA_AJUSTADO"):
            repo.upsert_financeiro("SHELL", per, rub, 12.0, "USD", idf, 0.9)
    # 2026Q1 perde o vinculo de fonte dos mesmos dois fatos: a rastreabilidade vai a
    # 0 e derruba o DQS (peso 15%) mais do que a tempestividade do ultimo trimestre
    # (100 contra 60) compensa — e a queda tem de aparecer na serie.
    repo.upsert_financeiro("SHELL", "2026Q1", "RECEITA_LIQUIDA", 12.0, "USD", None, 0.9)
    repo.upsert_financeiro("SHELL", "2026Q1", "EBITDA_AJUSTADO", 4.0, "USD", None, 0.9)
    from workers.quality_score import painel_qualidade, run_quality_score
    r = run_quality_score()
    assert "historico" in r and r["historico"]["periodos"] == 2
    p = painel_qualidade()
    h = p["historico"]
    assert h["empresas"] == 1 and h["periodos"] == ["2025Q4", "2026Q1"]
    # 2026Q1 tem fato sem fonte -> DQS menor que 2025Q4: a queda aparece na serie
    assert h["por_empresa"]["SHELL"]["dqs_atual"] < h["por_empresa"]["SHELL"]["dqs_inicial"]
    assert h["piorou"]["empresa"] == "SHELL" and h["variacao_media"] < 0

    from controllers import SourceController
    ctrl = SourceController()
    assert ctrl.historico_qualidade()["empresas"] == 1
    assert ctrl.historico_qualidade("SHELL")["por_empresa"]["SHELL"]["periodos"] == 2
    assert ctrl.historico_qualidade("BP")["por_empresa"] == {}

    import app_main
    rc = app_main.main(["qualidade", "historico"])
    assert rc == 0
    DatabaseManager._instance = None


def test_historico_no_painel_web_e_gui(tmp_path, monkeypatch):
    """Aba Qualidade mostra a evolução do DQS no web e na GUI."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "WEB_HTML", tmp_path / "p.html")
    DatabaseManager._instance = None
    from models.repositories import FatoRepository, FonteRepository
    idf = FonteRepository().registrar("BP", "http://ri/z.pdf", "PDF")
    repo = FatoRepository()
    for per in ("2025Q4", "2026Q1", "2026Q2"):
        for rub in ("RECEITA_LIQUIDA", "EBITDA_AJUSTADO"):
            repo.upsert_financeiro("BP", per, rub, 8.0, "USD", idf, 0.9)
    from workers.quality_score import run_quality_score
    run_quality_score()
    from views.web_app import build_dashboard
    html = Path(build_dashboard("2026Q2", tmp_path / "p.html")).read_text(encoding="utf-8")
    for token in ('id="qual_hist_graf"', 'id="qual_hist"', 'id="qual_hist_kpis"',
                  'id="hist_empresa"', "function qualHistorico(", "M7.23"):
        assert token in html, token
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from views.gui_app import BenchmarkGUI
    gui = BenchmarkGUI(periodo="2026Q2")
    win = gui.build()
    DatabaseManager._instance = None


# ------------------------------------------------- M2.10: relatorio de auditoria
def test_relatorio_auditoria_pdf(tmp_path, monkeypatch):
    """Relatório em PDF com as decisões do período, com o item auditado resolvido."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.repositories import QualityRepository
    q = QualityRepository()
    q.alertar("tb_fato_financeiro", 1, "INVALID_NEGATIVE", "CAPEX negativo", "HIGH")
    q.para_revisao("PETROBRAS", "2026Q2", "CAPEX", -1.0, "fora do limite")
    q.para_revisao("SHELL", "2026Q2", "FCO", 12.0, "confianca baixa", 0.5)
    fila = q.listar_revisao()
    q.decidir("tb_review_queue", fila[0]["id_review"], "ACEITO", "conferido no release")
    q.decidir("tb_review_queue", fila[1]["id_review"], "REJEITADO")

    from workers.relatorio_auditoria import decisoes_periodo, gerar_relatorio
    decisoes = decisoes_periodo(q.db)
    assert len(decisoes) == 2
    # a decisao tem de vir com o item auditado, senao o PDF mostraria so "#1 ACEITO"
    aceito = next(d for d in decisoes if d["decisao"] == "ACEITO")
    assert aceito["nome_empresa"] == "PETROBRAS" and aceito["periodo"] == "2026Q2"
    assert aceito["rubrica"] == "CAPEX" and aceito["comentario"] == "conferido no release"

    destino = tmp_path / "relatorio.pdf"
    caminho = gerar_relatorio(destino, db=q.db)
    assert Path(caminho) == destino and destino.exists()
    conteudo = destino.read_bytes()
    assert conteudo.startswith(b"%PDF") and len(conteudo) > 2000

    # filtro de periodo: um intervalo que nao contem as decisoes vem vazio
    assert decisoes_periodo(q.db, de="1990-01-01", ate="1990-12-31") == []
    antes = gerar_relatorio(tmp_path / "r2.pdf", de="1990-01-01", ate="1990-12-31", db=q.db)
    assert Path(antes).exists()
    DatabaseManager._instance = None


def test_relatorio_auditoria_escapa_comentario(tmp_path, monkeypatch):
    """Comentário com '<' quebraria o XML do PDF: precisa ser escapado."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.repositories import QualityRepository
    q = QualityRepository()
    q.para_revisao("PETROBRAS", "2026Q2", "CAPEX", -1.0, "limite")
    fila = q.listar_revisao()
    q.decidir("tb_review_queue", fila[0]["id_review"], "REJEITADO",
              "valor < 0 & confianca > 0.5 <invalido>")
    from workers.relatorio_auditoria import gerar_relatorio
    destino = tmp_path / "r.pdf"
    gerar_relatorio(destino, db=q.db)
    assert destino.exists() and destino.read_bytes().startswith(b"%PDF")
    DatabaseManager._instance = None


def test_relatorio_auditoria_base_vazia(tmp_path, monkeypatch):
    """Sem nenhum alerta/fila o relatório ainda é gerado (relatório vazio, não erro)."""
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.database import DatabaseManager as _DB
    from workers.relatorio_auditoria import gerar_relatorio
    destino = tmp_path / "vazio.pdf"
    gerar_relatorio(destino, db=_DB())
    assert destino.exists() and destino.read_bytes().startswith(b"%PDF")
    DatabaseManager._instance = None


def test_relatorio_auditoria_api_e_cli(tmp_path, monkeypatch):
    """POST/GET da API e o CLI produzem o PDF e listam as decisões do período."""
    import json as _json
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    import config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    DatabaseManager._instance = None
    from models.repositories import QualityRepository
    q = QualityRepository()
    q.para_revisao("PETROBRAS", "2026Q2", "CAPEX", -1.0, "limite")
    fila = q.listar_revisao()
    q.decidir("tb_review_queue", fila[0]["id_review"], "ACEITO", "ok")
    from views.web_server import DashboardHandler
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    porta = httpd.server_address[1]
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/auditoria?pdf=1",
                                    timeout=60) as r:
            j = _json.loads(r.read().decode())
        assert j["relatorio"]["arquivo"].endswith(".pdf")
        assert Path(j["relatorio"]["arquivo"]).exists()
        # sem filtro de datas a API nao precisa devolver o bloco de periodo
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/auditoria",
                                    timeout=30) as r:
            sem = _json.loads(r.read().decode())
        assert "periodo" not in sem
        with urllib.request.urlopen(
                f"http://127.0.0.1:{porta}/api/auditoria?de=2000-01-01&ate=2000-12-31",
                timeout=30) as r:
            com = _json.loads(r.read().decode())
        assert com["periodo"]["total"] == 0 and com["periodo"]["decisoes"] == []
    finally:
        httpd.shutdown()
        httpd.server_close()
    import app_main
    assert app_main.main(["auditoria", "decisoes"]) == 0
    saida = tmp_path / "cli.pdf"
    assert app_main.main(["auditoria", "relatorio", "--saida", str(saida)]) == 0
    assert saida.exists()
    # intervalo que nao contem decisao: o relatorio sai vazio, sem quebrar
    assert app_main.main(["auditoria", "decisoes", "--de", "1990-01-01",
                          "--ate", "1990-12-31"]) == 0
    assert app_main.main(["auditoria", "relatorio", "--de", "1990-01-01",
                          "--ate", "1990-12-31", "--saida", str(tmp_path / "vazio.pdf")]) == 0
    assert (tmp_path / "vazio.pdf").exists()
    DatabaseManager._instance = None

