"""Web Plotly + graficos Qt (pyqtgraph)."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_build_dashboard_contains_expected():
    from scripts.web_dashboard import build_dashboard
    h = build_dashboard()
    assert "PETROBRAS" in h and "plotly" in h.lower()
    assert "Benchmark" in h and "Qualidade" in h


def test_web_layout_sidebar_tabs_theme():
    from scripts.web_dashboard import build_dashboard
    h = build_dashboard()
    for token in ('id="sidebar"', 'id="chartarea"', 'class="acc"', 'id="tabbar"',
                  'openTab', 'toggleSide', 'setTheme', 'id="collapse"'):
        assert token in h, token
    for token in ("{{TITLE}}", "{{FIG_BENCH}}", "{{FIG_EVOL}}", "{{FIG_PROD}}",
                  "{{NARRATIVE}}", "{{KPI_CARDS}}", "{{RANK_ROWS}}",
                  "{{DATA_ROWS}}", "{{QUALITY_ROWS}}",
                  "{{DOCS_ROWS}}", "{{API_ROWS}}", "{{PERIODS_OPTIONS}}"):
        assert token not in h, token  # nenhum placeholder sem preencher


def test_executive_dashboard_elements():
    from scripts.web_dashboard import build_dashboard
    h = build_dashboard()
    assert "kpis" in h and "Ranking EBITDA" in h  # cartoes KPI + ranking
    assert "USD milh" in h and "Trimestre" in h  # titulos de eixos
    assert '"x": 1.0' in h or "x:1" in h or "orientation" in h  # legenda configurada


def test_qt_charts_tab_offscreen():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
        from src.views.charts_qt import QtChartsTab
    except ImportError as e:
        import pytest
        pytest.skip(f"Qt/pyqtgraph indisponivel: {e}")
    app = QApplication.instance() or QApplication([])
    tab = QtChartsTab()
    assert tab.bench is not None and tab.evol is not None and tab.prod is not None
    tab.cb_ind.setCurrentText("OCF")
    tab.cb_period.setCurrentText("1T2026")
