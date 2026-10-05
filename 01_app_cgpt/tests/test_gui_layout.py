"""Layout GUI: sidebar 25/75 fora das tabs, accordions, colapso, temas."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _win():
    from PySide6.QtWidgets import QApplication
    from src.views.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.show()  # offscreen: necessario p/ isVisible()
    return w


def test_sidebar_outside_tabs_ratio():
    w = _win()
    assert w.tabs.count() == 12
    assert w.sidebar.isVisible()
    lay = w.centralWidget().layout()
    assert lay.stretch(0) == 1 and lay.stretch(2) == 3  # 25% / 75%


def test_accordions_and_collapse():
    w = _win()
    box = w.sidebar.findChild(__import__("PySide6.QtWidgets", fromlist=["QToolBox"]).QToolBox)
    assert box.count() == 4  # Filtros, Exibição, Atalhos, Sobre
    w.btn_collapse.click()
    assert not w.sidebar.isVisible()
    w.btn_collapse.click()
    assert w.sidebar.isVisible()


def test_theme_switch_and_shared_filters():
    w = _win()
    w.cb_theme.setCurrentText("dark")
    assert w._theme == "dark"
    assert "background: #2b2b2b" in w.styleSheet() or "#2b2b2b" in w.styleSheet()
    w.cb_theme.setCurrentText("light")
    w.cb_side_period.setCurrentText("1T2026")
    assert w._period == "1T2026" and w.tbl_exec.rowCount() == 4


def test_executive_kpis_and_chart_dressing():
    w = _win()
    assert len(w.kpi_cards) == 5
    assert "18,600" in w.kpi_cards[1].text()  # EBITDA Petrobras 2T2026
    tab = w.charts_tab
    for plot in (tab.bench, tab.evol, tab.prod):
        assert plot.plotItem.ctrl.xGridCheck.isChecked() or plot.plotItem.ctrl.yGridCheck.isChecked()
    assert tab.evol.plotItem.legend is not None  # legenda a direita
    assert tab.bench.getAxis("left").labelText == "USD milhões"
    assert tab.evol.getAxis("bottom").labelText == "Trimestre"
