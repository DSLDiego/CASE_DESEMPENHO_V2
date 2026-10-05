"""View PySide6 (MVC): sidebar 25% + ChartArea 75% com tabs, temas light/dark.

Layout: sidebar FORA das tabs (QToolBox = accordions verticais) | botao de
colapso horizontal | QTabWidget na ChartArea. Botoes/fontes compactos.
"""
from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit,
    QProgressBar, QFileDialog, QSpinBox, QGroupBox, QFormLayout, QMessageBox,
    QHeaderView, QToolBox, QScrollArea, QGridLayout, QFrame,
)

from src.controllers.app_controllers import DashboardController, ETLJobManager
from src.etl.scheduler import ALGORITHMS
from src.repositories.sqlite_repo import SQLiteRepository
from src.utils.hardware import detect_hardware, auto_batch
from src.views.themes import apply_theme

INDICATORS = ["REVENUE", "EBITDA_ADJ", "NET_INCOME", "NET_INCOME_ADJ", "OCF", "EMPLOYEES"]
COMPANIES = ["PETROBRAS", "EQUINOR", "SHELL", "TOTALENERGIES"]


class _Signals(QObject):
    progress = Signal(object, int, int)
    done = Signal(object)


class LineChart(QWidget):
    def __init__(self, series: dict[str, list[tuple[str, float]]] | None = None) -> None:
        super().__init__()
        self.series = series or {}
        self.setMinimumHeight(220)

    def set_series(self, series: dict) -> None:
        self.series = series
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        dark = self.palette().window().color().lightness() < 128
        bg, fg, grid = (QColor("#2b2b2b"), QColor("#e0e0e0"), QColor("#555")) if dark else \
                       (QColor("white"), QColor("#222"), QColor("#ddd"))
        p.fillRect(self.rect(), bg)
        colors = [QColor("#1f77b4"), QColor("#ff7f0e"), QColor("#2ca02c"), QColor("#d62728")]
        vals = [v for s in self.series.values() for _, v in s if v is not None]
        if not vals:
            p.drawText(self.rect(), Qt.AlignCenter, "Sem dados")
            return
        lo, hi = min(vals), max(vals)
        if hi == lo:
            hi = lo + 1
        W, H, pad, leg_w = self.width(), self.height(), 40, 110
        p.setPen(QPen(QColor("#999")))
        p.drawLine(pad, 8, pad, H - pad)
        p.drawLine(pad, H - pad, W - leg_w, H - pad)
        # grade quadricular
        p.setPen(QPen(grid))
        for k in range(1, 5):
            y = 8 + k * (H - pad - 16) / 5
            p.drawLine(pad, int(y), W - leg_w, int(y))
        # titulos dos eixos
        p.setPen(QPen(fg))
        p.drawText(pad, H - 22, "Trimestre")
        p.save()
        p.translate(12, H / 2 + 40)
        p.rotate(-90)
        p.drawText(0, 0, "USD milhões")
        p.restore()
        labels: list[str] = []
        for s in self.series.values():
            for per, _ in s:
                if per not in labels:
                    labels.append(per)
        for vline in range(len(labels)):
            x = pad + (vline + 0.5) * ((W - pad - leg_w - 8) / max(len(labels), 1))
            p.setPen(QPen(grid))
            p.drawLine(int(x), 8, int(x), H - pad)
        for i, (name, pts) in enumerate(self.series.items()):
            col = colors[i % len(colors)]
            p.setPen(QPen(col, 2))
            prev = None
            m = {per: v for per, v in pts}
            for j, lab in enumerate(labels):
                x = pad + (j + 0.5) * ((W - pad - leg_w - 8) / max(len(labels), 1))
                v = m.get(lab)
                if v is None:
                    prev = None
                    continue
                y = 8 + (1 - (v - lo) / (hi - lo)) * (H - pad - 16)
                p.setBrush(col)
                p.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)
                if prev:
                    p.drawLine(int(prev[0]), int(prev[1]), int(x), int(y))
                prev = (x, y)
                if i == 0:
                    p.setPen(QPen(QColor("#888")))
                    p.drawText(int(x) - 18, H - pad + 12, lab)
                    p.setPen(QPen(col, 2))
        # legenda a direita
        lx = W - leg_w + 8
        p.setPen(QPen(fg))
        p.drawText(lx, 20, "Empresa")
        for i, name in enumerate(self.series):
            y = 34 + i * 18
            p.setBrush(colors[i % len(colors)])
            p.setPen(QPen(colors[i % len(colors)]))
            p.drawRect(lx, y - 9, 12, 9)
            p.setPen(QPen(fg))
            p.drawText(lx + 16, y, name)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Benchmarking Financeiro Trimestral — PoC (v0)")
        self.resize(1240, 780)
        self.ctrl = DashboardController()
        self.jobs = ETLJobManager()
        self.signals = _Signals()
        self.signals.progress.connect(self._on_progress)
        self.signals.done.connect(self._on_done)
        self._files: list[str] = []
        self._theme = "light"
        self._period = "2T2026"
        self._indicator = "REVENUE"

        root = QWidget()
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(4, 4, 4, 4)

        # ---- sidebar 25% (fora das tabs) ----
        self.sidebar = self._build_sidebar()
        shell.addWidget(self.sidebar, 1)

        # ---- botao colapso horizontal (fora do sidebar) ----
        strip = QFrame()
        strip.setFixedWidth(20)
        sl = QVBoxLayout(strip)
        sl.setContentsMargins(0, 0, 0, 0)
        self.btn_collapse = QPushButton("❮")
        self.btn_collapse.setFixedWidth(18)
        self.btn_collapse.clicked.connect(self._toggle_sidebar)
        sl.addStretch(1)
        sl.addWidget(self.btn_collapse)
        sl.addStretch(1)
        shell.addWidget(strip, 0)

        # ---- ChartArea 75% com as tabs dentro ----
        self.tabs = QTabWidget()
        shell.addWidget(self.tabs, 3)
        self.tabs.addTab(self._tab_executive(), "Visão Executiva")
        self.tabs.addTab(self._tab_benchmark(), "Benchmark")
        self.tabs.addTab(self._tab_history(), "Evolução Histórica")
        self.tabs.addTab(self._tab_productivity(), "Produtividade")
        self.tabs.addTab(self._tab_data(), "Dados")
        self.tabs.addTab(self._tab_quality(), "Qualidade")
        self.tabs.addTab(self._tab_sources(), "Fontes")
        self.tabs.addTab(self._tab_etl(), "ETL / Batch")
        self.tabs.addTab(self._tab_hardware(), "Hardware & Paralelismo")
        try:
            from src.views.charts_qt import QtChartsTab
            self.charts_tab = QtChartsTab(self.ctrl)
            self.tabs.addTab(self.charts_tab, "Gráficos Qt")
        except Exception as e:
            from PySide6.QtWidgets import QLabel as _L
            self.charts_tab = None
            self.tabs.addTab(_L(f"Gráficos Qt indisponíveis ({e})"), "Gráficos Qt")
        try:
            from src.views.sources_crud_tab import SourcesCrudTab
            self.tabs.addTab(SourcesCrudTab(), "Fontes Web (CRUD)")
        except Exception as e:
            from PySide6.QtWidgets import QLabel as _L2
            self.tabs.addTab(_L2(f"Gestão de fontes indisponível ({e})"), "Fontes Web (CRUD)")
        try:
            from src.views.sources_panel_tab import SourcesPanelTab
            self.tabs.addTab(SourcesPanelTab(), "Fontes (Painel)")
        except Exception as e:
            from PySide6.QtWidgets import QLabel as _L3
            self.tabs.addTab(_L3(f"Painel de fontes indisponível ({e})"), "Fontes (Painel)")

        periods = self.ctrl.periods()
        if periods:
            self._period = "2T2026" if "2T2026" in periods else periods[-1]
            self.cb_side_period.setCurrentText(self._period)
        apply_theme(self, "light")
        self.refresh_all()

    # ---- sidebar ----
    def _build_sidebar(self) -> QWidget:
        box = QToolBox()
        # Filtros
        f = QWidget()
        fl = QFormLayout(f)
        self.cb_side_period = QComboBox()
        self.cb_side_period.addItems(self.ctrl.periods())
        self.cb_side_period.currentTextChanged.connect(self._side_filter)
        self.cb_side_indicator = QComboBox()
        self.cb_side_indicator.addItems(INDICATORS)
        self.cb_side_indicator.currentTextChanged.connect(self._side_filter)
        fl.addRow("Período:", self.cb_side_period)
        fl.addRow("Indicador:", self.cb_side_indicator)
        box.addItem(f, "Filtros")
        # Exibicao
        v = QWidget()
        vl = QFormLayout(v)
        self.cb_theme = QComboBox()
        self.cb_theme.addItems(["light", "dark"])
        self.cb_theme.currentTextChanged.connect(self._change_theme)
        vl.addRow("Tema:", self.cb_theme)
        box.addItem(v, "Exibição")
        # Atalhos
        a = QWidget()
        al = QVBoxLayout(a)
        for label, idx in [("Ir p/ ETL / Batch", 7), ("Ir p/ Gráficos Qt", 9),
                           ("Ir p/ Fontes Web", 10), ("Ir p/ Qualidade", 5)]:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, i=idx: self.tabs.setCurrentIndex(i))
            al.addWidget(b)
        al.addStretch(1)
        box.addItem(a, "Atalhos")
        # Sobre
        s = QWidget()
        sl = QVBoxLayout(s)
        sl.addWidget(QLabel("PoC v0 — Python + SQLite\nFiltros valem p/ abas 1–4."))
        sl.addStretch(1)
        box.addItem(s, "Sobre")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(QLabel("<b>Configuração</b>"))
        wl.addWidget(scroll)
        return wrap

    def _toggle_sidebar(self) -> None:
        hidden = not self.sidebar.isVisible()
        self.sidebar.setVisible(hidden)
        self.btn_collapse.setText("❮" if hidden else "❯")

    def _side_filter(self) -> None:
        self._period = self.cb_side_period.currentText() or self._period
        self._indicator = self.cb_side_indicator.currentText() or self._indicator
        self.refresh_views()

    def _change_theme(self, name: str) -> None:
        self._theme = apply_theme(self, name)
        if self.charts_tab is not None and hasattr(self.charts_tab, "set_theme"):
            self.charts_tab.set_theme(self._theme)
        self.refresh_views()

    # ---- helpers ----
    def _fill_table(self, tbl: QTableWidget, headers: list[str], rows: list[list]) -> None:
        tbl.clear()
        tbl.setRowCount(len(rows))
        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                item = QTableWidgetItem("" if v is None else str(v))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                tbl.setItem(i, j, item)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    # ---- abas (grid NxM, preenchem o espaco) ----
    def _tab_executive(self) -> QWidget:
        w = QWidget()
        lay = QGridLayout(w)
        kpi_row = QHBoxLayout()
        self.kpi_cards: list[QLabel] = []
        for _ in range(5):
            card = QLabel()
            card.setFrameStyle(QFrame.Box)
            card.setStyleSheet("QLabel { border-left: 3px solid #1f77b4; padding: 3px; }")
            card.setAlignment(Qt.AlignCenter)
            self.kpi_cards.append(card)
            kpi_row.addWidget(card, 1)
        lay.addLayout(kpi_row, 0, 0)
        self.tbl_exec = QTableWidget()
        self.txt_narr = QTextEdit()
        self.txt_narr.setReadOnly(True)
        self.txt_narr.setMaximumHeight(90)
        lay.addWidget(self.tbl_exec, 1, 0)
        lay.addWidget(QLabel("Análise executiva (gerada):"), 2, 0)
        lay.addWidget(self.txt_narr, 3, 0)
        lay.setRowStretch(0, 0)
        lay.setRowStretch(1, 3)
        lay.setRowStretch(3, 1)
        return w

    def _tab_benchmark(self) -> QWidget:
        w = QWidget()
        lay = QGridLayout(w)
        self.tbl_bench = QTableWidget()
        lay.addWidget(self.tbl_bench, 0, 0)
        lay.setRowStretch(0, 1)
        return w

    def _tab_history(self) -> QWidget:
        w = QWidget()
        lay = QGridLayout(w)
        self.chart = LineChart()
        lay.addWidget(self.chart, 0, 0)
        lay.setRowStretch(0, 1)
        return w

    def _tab_productivity(self) -> QWidget:
        w = QWidget()
        lay = QGridLayout(w)
        self.tbl_prod = QTableWidget()
        lay.addWidget(self.tbl_prod, 0, 0)
        lay.addWidget(QLabel("Receita/empregado = RECEITA / EFETIVO · EBITDA/empregado = EBITDA_ADJ / EFETIVO"), 1, 0)
        lay.setRowStretch(0, 1)
        return w

    def _tab_data(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        btn_csv = QPushButton("Importar CSV…")
        btn_csv.clicked.connect(self._import_csv)
        btn_exp = QPushButton("Exportar CSV")
        btn_exp.clicked.connect(self._export_csv)
        row.addWidget(btn_csv)
        row.addWidget(btn_exp)
        row.addStretch(1)
        lay.addLayout(row)
        self.tbl_data = QTableWidget()
        lay.addWidget(self.tbl_data, 1)
        return w

    def _tab_quality(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        btn = QPushButton("↻ Atualizar")
        btn.clicked.connect(self.refresh_quality)
        lay.addWidget(btn)
        self.tbl_q = QTableWidget()
        lay.addWidget(self.tbl_q, 1)
        return w

    def _tab_sources(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.tbl_src = QTableWidget()
        lay.addWidget(self.tbl_src, 1)
        return w

    def _tab_etl(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        cfg = QGroupBox("Coleta / Batch ETL")
        form = QFormLayout(cfg)
        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["PROCESS", "THREAD", "SUBPROCESS"])
        self.cb_sched = QComboBox()
        self.cb_sched.addItems(ALGORITHMS)
        self.cb_batch = QComboBox()
        self.cb_batch.addItems(["5", "10", "15", "20", "50", "100", "Auto"])
        self.cb_batch.setCurrentText("10")
        self.sp_workers = QSpinBox()
        self.sp_workers.setRange(1, 128)
        self.sp_workers.setValue(8)
        form.addRow("Mecanismo:", self.cb_mode)
        form.addRow("Scheduler:", self.cb_sched)
        form.addRow("Lote:", self.cb_batch)
        form.addRow("Workers:", self.sp_workers)
        lay.addWidget(cfg)
        row = QHBoxLayout()
        b_add = QPushButton("＋ Arquivos…")
        b_add.clicked.connect(self._pick_files)
        b_run = QPushButton("▶ Executar")
        b_run.clicked.connect(self._run_etl)
        b_stop = QPushButton("■ Cancelar")
        b_stop.clicked.connect(lambda: self.jobs.cancel_job())
        row.addWidget(b_add)
        row.addWidget(b_run)
        row.addWidget(b_stop)
        row.addStretch(1)
        lay.addLayout(row)
        self.lbl_queue = QLabel("Fila: 0 arquivo(s)")
        lay.addWidget(self.lbl_queue)
        self.bar = QProgressBar()
        lay.addWidget(self.bar)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        lay.addWidget(self.log, 1)
        return w

    def _tab_hardware(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.txt_hw = QTextEdit()
        self.txt_hw.setReadOnly(True)
        lay.addWidget(self.txt_hw, 1)
        b = QPushButton("↻ Atualizar")
        b.clicked.connect(self.refresh_hardware)
        lay.addWidget(b)
        return w

    # ---- refresh ----
    def refresh_all(self) -> None:
        self.refresh_views()
        self.refresh_data()
        self.refresh_quality()
        self.refresh_sources()
        self.refresh_hardware()

    def refresh_views(self) -> None:
        self.refresh_executive()
        self.refresh_benchmark()
        self.refresh_history()
        self.refresh_productivity()

    def refresh_executive(self) -> None:
        data = self.ctrl.executive(self._period)
        t = data["table"]
        rows = [[c] + [t.get(c, {}).get(i) for i in INDICATORS] for c in COMPANIES if c in t]
        self._fill_table(self.tbl_exec, ["Empresa"] + INDICATORS, rows)
        demo = " (base DEMO)" if data.get("is_demo") else ""
        self.txt_narr.setText(f"[{self._period}] " + data["narrative"] + demo)
        # KPIs: Petrobras vs T/T + media dos pares
        periods = self.ctrl.periods()
        prev = periods[periods.index(self._period) - 1] if self._period in periods and len(periods) > 1 else None
        prv = self.ctrl.executive(prev)["table"] if prev else {}
        peers = [c for c in COMPANIES if c != "PETROBRAS"]
        for card, (label, ind, unit) in zip(self.kpi_cards,
                [("Receita", "REVENUE", "USD M"), ("EBITDA aj.", "EBITDA_ADJ", "USD M"),
                 ("Lucro líq.", "NET_INCOME", "USD M"), ("Caixa oper.", "OCF", "USD M"),
                 ("Efetivo", "EMPLOYEES", "pess.")]):
            v = t.get("PETROBRAS", {}).get(ind)
            q = prv.get("PETROBRAS", {}).get(ind)
            dq = "" if v in (None, 0) or q in (None, 0) else f"{(v - q) / abs(q):+.1%}"
            pa = [x for x in (t.get(c, {}).get(ind) for c in peers) if x is not None]
            avg = sum(pa) / len(pa) if pa else None
            vs = "▲" if v is not None and avg and v > avg else ("▼" if avg else "")
            val = "—" if v is None else (f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.1f}")
            card.setText(f"{label}\n{val} {unit}\n{dq} {vs}")

    def refresh_benchmark(self) -> None:
        data = self.ctrl.executive(self._period)["table"]
        rows = [[c, data.get(c, {}).get(self._indicator)] for c in COMPANIES]
        rows.sort(key=lambda r: (-(r[1] or 0)))
        self._fill_table(self.tbl_bench, ["Empresa", f"{self._indicator} ({self._period})"], rows)

    def refresh_history(self) -> None:
        hist = self.ctrl.history(self._indicator)
        self.chart.set_series({c: [(r["period_id"], r["value"]) for r in rows] for c, rows in hist.items()})

    def refresh_productivity(self) -> None:
        prod = self.ctrl.productivity(self._period)
        self._fill_table(self.tbl_prod, ["Métrica", "Valor (USD)"],
                         [[k, f"{v:,.0f}"] for k, v in sorted(prod.items())])

    def refresh_data(self) -> None:
        repo = SQLiteRepository()
        rows = repo.query("""SELECT company_id, period_id, indicator_id, value, unit, confidence,
                             substr(evidence,1,80) ev FROM metric_current ORDER BY 2,1,3 LIMIT 500""")
        self._fill_table(self.tbl_data, ["Empresa", "Período", "Indicador", "Valor", "Unidade", "Conf", "Evidência"],
                         [[r["company_id"], r["period_id"], r["indicator_id"], r["value"],
                           r["unit"], r["confidence"], r["ev"]] for r in rows])

    def refresh_quality(self) -> None:
        repo = SQLiteRepository()
        rows = repo.quality_issues()
        self._fill_table(self.tbl_q, ["Regra", "Sev", "Mensagem", "Empresa", "Período", "Indicador"],
                         [[r["rule"], r["severity"], r["message"], r["company_id"],
                           r["period_id"], r["indicator_id"]] for r in rows])
        if not rows:
            self._fill_table(self.tbl_q, ["Status"], [["Nenhum alerta — base íntegra"]])

    def refresh_sources(self) -> None:
        repo = SQLiteRepository()
        rows = repo.query("SELECT company_id, document, url, authority, is_demo, version FROM source LIMIT 200")
        self._fill_table(self.tbl_src, ["Empresa", "Documento", "URL", "Autoridade", "Demo", "Versão"],
                         [[r["company_id"], r["document"], (r["url"] or "")[:80], r["authority"],
                           r["is_demo"], r["version"]] for r in rows])

    def refresh_hardware(self) -> None:
        hw = detect_hardware()
        self.txt_hw.setText(
            f"CPUs lógicos: {hw['cpu_logical']} ({hw['cpu_source']}) · físicos: {hw['cpu_physical']}\n"
            f"RAM: {hw['ram_gb']} GB · GPU: {hw['gpu'] or 'não detectada'} ({hw['gpu_src']})\n"
            f"Workers recomendados: {hw['recommended_workers']} (Auto={auto_batch(hw['cpu_logical'])})")
        if hasattr(self, "sp_workers"):
            self.sp_workers.setValue(hw["recommended_workers"])

    # ---- acoes ----
    def _pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Arquivos de RI",
            str(Path("data/raw")), "Documentos (*.pdf *.xlsx *.xlsm *.xls *.csv *.doc *.docx *.txt *.html)")
        if files:
            self._files = files
            self.lbl_queue.setText(f"Fila: {len(files)} arquivo(s) — {self.cb_sched.currentText()}")

    def _run_etl(self) -> None:
        if not self._files:
            QMessageBox.information(self, "ETL", "Adicione arquivos primeiro (ou Importar CSV na aba Dados).")
            return
        self.bar.setMaximum(len(self._files))
        self.bar.setValue(0)
        self.log.clear()
        batch = self.cb_batch.currentText()
        self.jobs.run_async(self._files, self.cb_mode.currentText(),
                            batch if batch == "Auto" else int(batch),
                            self.cb_sched.currentText(), self.sp_workers.value(),
                            lambda r, d, t: self.signals.progress.emit(r, d, t),
                            lambda res: self.signals.done.emit(res))

    def _on_progress(self, res, done: int, total: int) -> None:
        self.bar.setValue(done)
        status = "OK" if res.ok else f"FALHA: {res.error[:120]}"
        self.log.append(f"[{done}/{total}] {Path(res.path).name} — {status} ({res.elapsed_ms} ms)")

    def _on_done(self, res) -> None:
        self.log.append(f"Concluído: {res['ok']}/{res['total']} OK em {res['elapsed_s']}s (run {res['run_id']})")
        self.refresh_all()

    def _import_csv(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "CSV", "data", "CSV (*.csv)")
        if not f:
            return
        from src.services.app_services import BatchETLService
        n = BatchETLService().import_csv(f)
        QMessageBox.information(self, "Importação", f"{n} observações importadas.")
        self.refresh_all()

    def _export_csv(self) -> None:
        f, _ = QFileDialog.getSaveFileName(self, "Exportar", "data/export.csv", "CSV (*.csv)")
        if not f:
            return
        import csv as _csv
        repo = SQLiteRepository()
        rows = repo.query("SELECT * FROM metric_current")
        if rows:
            with open(f, "w", newline="", encoding="utf-8") as fh:
                w = _csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
        QMessageBox.information(self, "Exportação", f"Exportado: {f}")


def run_gui() -> int:
    import sys
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()
