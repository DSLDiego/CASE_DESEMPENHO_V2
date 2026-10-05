"""Aba de graficos Qt (pyqtgraph): benchmark em barras, evolucao e produtividade.

View pura (MVC): le via DashboardController, sem SQL aqui.
"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox

from src.controllers.app_controllers import DashboardController
from src.views.themes import CHART_THEMES

COMPANIES = ["PETROBRAS", "EQUINOR", "SHELL", "TOTALENERGIES"]
INDICATORS = ["REVENUE", "EBITDA_ADJ", "NET_INCOME", "NET_INCOME_ADJ", "OCF", "EMPLOYEES"]


class QtChartsTab(QWidget):
    def __init__(self, ctrl: DashboardController | None = None) -> None:
        super().__init__()
        import pyqtgraph as pg
        self._pg = pg
        self.ctrl = ctrl or DashboardController()
        self.palette = CHART_THEMES["light"][2]
        self.set_theme("light")

        lay = QVBoxLayout(self)
        filt = QHBoxLayout()
        self.cb_period = QComboBox()
        self.cb_period.addItems(self.ctrl.periods())
        self.cb_period.setCurrentText("2T2026" if "2T2026" in self.ctrl.periods() else self.cb_period.itemText(0))
        self.cb_period.currentTextChanged.connect(self.refresh)
        self.cb_ind = QComboBox()
        self.cb_ind.addItems(INDICATORS)
        self.cb_ind.currentTextChanged.connect(self.refresh)
        filt.addWidget(QLabel("Período (barras):"))
        filt.addWidget(self.cb_period)
        filt.addWidget(QLabel("Indicador (evolução):"))
        filt.addWidget(self.cb_ind)
        filt.addStretch(1)
        lay.addLayout(filt)

        self.bench = pg.PlotWidget(title="Benchmark por empresa")
        self.bench.setLabel("bottom", "Empresa")
        self.bench.setLabel("left", "USD milhões")
        self.bench.showGrid(x=False, y=True, alpha=0.3)
        self.evol = pg.PlotWidget(title="Evolução histórica")
        self.evol.setLabel("bottom", "Trimestre")
        self.evol.setLabel("left", "USD milhões")
        self.evol.showGrid(x=True, y=True, alpha=0.3)
        self.prod = pg.PlotWidget(title="Receita por empregado (USD)")
        self.prod.setLabel("bottom", "Empresa")
        self.prod.setLabel("left", "USD por empregado")
        self.prod.showGrid(x=False, y=True, alpha=0.3)
        lay.addWidget(self.bench)
        lay.addWidget(self.evol)
        lay.addWidget(self.prod)
        self.refresh()

    def set_theme(self, name: str) -> None:
        bg, fg, pal = CHART_THEMES.get(name, CHART_THEMES["light"])
        self._pg.setConfigOptions(antialias=True, background=bg, foreground=fg)
        self.palette = pal
        for w in ("bench", "evol", "prod"):
            if hasattr(self, w):
                getattr(self, w).setBackground(bg)
        if hasattr(self, "bench"):
            self.refresh()

    def refresh(self) -> None:
        pg = self._pg
        pal = self.palette
        per = self.cb_period.currentText()
        ind = self.cb_ind.currentText()
        table = self.ctrl.executive(per)["table"]

        # benchmark: barras do indicador selecionado na evolucao? usa financ. fixos p/ comparacao
        self.bench.clear()
        vals = [(table.get(c, {}).get(ind)) or 0 for c in COMPANIES]
        bars = pg.BarGraphItem(x=list(range(len(COMPANIES))), height=vals, width=0.6,
                               brushes=pal)
        self.bench.addItem(bars)
        self.bench.getAxis("bottom").setTicks([[(i, c) for i, c in enumerate(COMPANIES)]])
        self.bench.setTitle(f"Benchmark — {ind} — {per}")

        # evolucao do indicador
        self.evol.clear()
        if self.evol.plotItem.legend is None:
            try:
                self.evol.addLegend().anchor((1, 0), (1, 0))  # legenda a direita
            except Exception:
                self.evol.addLegend()
        hist = self.ctrl.history(ind)
        for i, comp in enumerate(COMPANIES):
            pts = hist.get(comp, [])
            xs = list(range(len(pts)))
            ys = [p["value"] or 0 for p in pts]
            self.evol.plot(xs, ys, pen=pg.mkPen(pal[i % 4], width=2),
                           symbol="o", symbolBrush=pal[i % 4], name=comp)
        if pts:
            self.evol.getAxis("bottom").setTicks([[(i, p["period_id"]) for i, p in enumerate(pts)]])
        self.evol.setTitle(f"Evolução — {ind}")

        # produtividade
        self.prod.clear()
        prod = self.ctrl.productivity(per)
        keys = sorted(k for k in prod if "receita" in k)
        self.prod.addItem(pg.BarGraphItem(x=list(range(len(keys))),
                                          height=[prod[k] for k in keys], width=0.6,
                                          brush="#2ca02c"))
        self.prod.getAxis("bottom").setTicks([[(i, k.split()[0]) for i, k in enumerate(keys)]])
        self.prod.setTitle(f"Receita por empregado — {per}")
