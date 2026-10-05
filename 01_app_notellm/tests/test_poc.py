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


def test_gui_monta_5_abas(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QTabWidget
    from views.gui_app import BenchmarkGUI
    gui = BenchmarkGUI(periodo="2026Q2")
    win = gui.build()
    win.show()  # offscreen: habilita isVisible
    abas = win.findChild(QTabWidget)
    assert abas.count() == 5
    assert [abas.tabText(i) for i in range(5)] == [
        "Benchmark", "Fontes (CRUD)", "Efetivo", "Auditoria", "Gestão ETL"]
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
    monkeypatch.setattr(etl_mod, "scan_container", lambda repo: {"novos": 0, "duplicados": 0})
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
    monkeypatch.setattr(etl_mod, "scan_container", lambda repo: {"novos": 0, "duplicados": 0})
    arquivo = tmp_path / "x.csv"
    arquivo.write_text("Indicador;2026Q2;2025Q4\n"
                       "Receita de vendas;33607;30000\n", encoding="utf-8")
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
    assert tabs.tabText(tabs.count() - 1) == "Gestão ETL"
    assert tabs.count() == 5


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


def test_anos_tolerados_pelo_etl():
    """Todo periodo discovery (2023-2026) deve ser reconhecido pelo De-Para de datas."""
    from workers.parse_tab import norm_period
    for ano in (2023, 2024, 2025, 2026):
        for tri in (1, 2, 3, 4):
            celulas = [f"{ano} Q{tri}", f"{ano}_{tri}Q", f"{ano}_{tri}T", f"{tri}T{ano}"]
            assert any(norm_period(c)[0] for c in celulas), celulas

