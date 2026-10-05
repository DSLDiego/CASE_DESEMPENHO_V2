"""View Desktop: PySide6 + pyqtgraph (QSplitter 25/75, QToolBox, QTabWidget, temas)."""
from __future__ import annotations

DARK_QSS = """
QMainWindow, QWidget { background:#12151c; color:#e2e8f0; font-size:11px; }
QToolBox::tab { background:#1a1e28; border:1px solid #2d3748; padding:4px; }
QTabBar::tab { background:#1a1e28; padding:6px 14px; }
QTabBar::tab:selected { border-bottom:2px solid #00a86b; color:#00a86b; }
QPushButton { background:#00a86b; color:white; border:none; padding:4px 8px; border-radius:3px; }
QTableWidget { gridline-color:#2d3748; }
QSplitter::handle:horizontal { background:#2d3748; border-left:1px solid #00a86b; border-right:1px solid #00a86b; }
"""
LIGHT_QSS = """
QMainWindow, QWidget { background:#f4f6f8; color:#0f172a; font-size:11px; }
QToolBox::tab { background:#ffffff; border:1px solid #e2e8f0; padding:4px; }
QTabBar::tab { background:#ffffff; padding:6px 14px; }
QTabBar::tab:selected { border-bottom:2px solid #007a4d; color:#007a4d; }
QPushButton { background:#007a4d; color:white; border:none; padding:4px 8px; border-radius:3px; }
QSplitter::handle:horizontal { background:#cbd5e1; border-left:1px solid #007a4d; border-right:1px solid #007a4d; }
"""


class BenchmarkGUI:
    CORES = {"PETROBRAS": "#00a86b", "SHELL": "#4a90d9", "BP": "#5b8ff9", "CHEVRON": "#3aa6c9",
             "EXXONMOBIL": "#2f7fd0", "TOTALENERGIES": "#6a9fd8", "EQUINOR": "#41b8a6"}

    def __init__(self, periodo: str = "2026Q2") -> None:
        from PySide6.QtWidgets import QApplication
        self._app = QApplication.instance() or QApplication([])
        self.periodo = periodo
        self.moeda = "USD"  # USD bi ou BRL bi (PTAX de fechamento)
        self.dark = False  # tema claro como padrao
        self.window = None
        self._plots: list = []

    def build(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGridLayout, QGroupBox,
                                       QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
                                       QScrollArea, QSplitter, QTabWidget, QTableWidget,
                                       QTableWidgetItem, QToolBox, QVBoxLayout, QWidget)
        import pyqtgraph as pg
        from controllers import AnalyticsController, SourceController

        pg.setConfigOptions(antialias=True, background="#ffffff", foreground="#0f172a")

        def _polilar(w, titulo: str = "Gráfico") -> None:
            """Acabamento visual: grade, clipping, eixos e foco em tela cheia.

            `setClipToView` (metodo do PlotItem no pyqtgraph >= 0.13) garante que
            nada seja desenhado fora da area do plot, evitando vazamento de um
            grafico sobre o vizinho; os nomes das empresas ficam sobre as barras,
            entao os rotulos do eixo X sao ocultados para nao duplicar/recortar
            texto em celulas estreitas. `enableAutoRange(False)` impede que o
            range "pule" ao redimensionar (o range fitted e reaplicado manualmente).
            """
            try:
                w.setClipToView(True)            # anti-vazamento entre graficos
                w.getViewBox().setMenuEnabled(False)
                w.enableAutoRange(enable=False)   # range estavel ao redimensionar
                w.showGrid(x=False, y=True, alpha=0.18)
                w.getAxis("bottom").setStyle(showValues=False, tickLength=0)
                w.getAxis("left").setTextPen(pg.mkPen("#64748b"))
                w.getAxis("left").setWidth(62)
                w.setTitle(titulo)
            except Exception as exc:              # nunca quebrar a GUI por cosmético
                print(f"[gui] polimento parcial: {exc}")
            # PlotWidget nasce com 640x480 e o sizeHint IMPOE isso: sem minimo
            # pequeno a grade 2x2 estourava a janela e os graficos eram cortados.
            try:
                from PySide6.QtWidgets import QSizePolicy
                w.setMinimumSize(200, 170)
                w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            except Exception:
                pass
            w._clip_to_view = True
            w._titulo = titulo                     # pyqtgraph 0.14 nao tem getter de titulo
            w._fit_range = None

        def _reajustar(w) -> None:
            """Reaplica o range ajustado (chamado em resize/colapso/redesenho)."""
            r = getattr(w, "_fit_range", None)
            if r:
                try:
                    w.setYRange(r[0], r[1], padding=0)
                except Exception:
                    pass
            xr = getattr(w, "_fit_x", None)
            if xr:
                try:
                    w.setXRange(xr[0], xr[1], padding=0)
                except Exception:
                    pass

        self._reajustar_todos = lambda: [_reajustar(w) for w in self._plots]  # noqa: E731

        from PySide6.QtCore import QEvent, QObject

        class _PlotEvents(QObject):
            """Duplo clique = foco em tela cheia (fecha com Esc)."""

            def __init__(self, fn):
                super().__init__()
                self.fn = fn

            def eventFilter(self, obj, ev):
                if ev.type() == QEvent.Type.MouseButtonDblClick:
                    self.fn(obj)
                return False

        self._plot_events = _PlotEvents(lambda w: self._focar(w) if self._focar_plot else None)

        def _aplicar_fundo_graficos():
            cor = "#12151c" if self.dark else "#ffffff"
            for _p in self._plots:
                try:
                    _p.setBackground(cor)
                except Exception:
                    pass

        def _polir_tabela(tbl, alternating: bool = True) -> None:
            """UX de tabela: somente leitura, selecao por linha, ordenacao, zebra."""
            from PySide6.QtCore import Qt as _Qt
            from PySide6.QtWidgets import QAbstractItemView
            try:
                tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
                tbl.setSortingEnabled(True)
                tbl.setAlternatingRowColors(alternating)
                tbl.setWordWrap(False)
                tbl.verticalHeader().setVisible(False)
            except Exception:
                pass

        def _paginar(layout_pai, tabela):
            estado = {"page": 0, "per": 25}
            barra = QHBoxLayout()
            btn_prev, btn_next = QPushButton("◀"), QPushButton("▶")
            rotulo, combo = QLabel(), QComboBox()
            combo.addItems(["10", "25", "50", "100"])
            combo.setCurrentText("25")
            barra.addWidget(btn_prev)
            barra.addWidget(rotulo)
            barra.addWidget(btn_next)
            barra.addWidget(combo)
            layout_pai.addLayout(barra)

            def desenhar():
                total = tabela.rowCount()
                n = max(1, (total + estado["per"] - 1) // estado["per"])
                estado["page"] = min(max(estado["page"], 0), n - 1)
                for _i in range(total):
                    vis = estado["page"] * estado["per"] <= _i < (estado["page"] + 1) * estado["per"]
                    tabela.setRowHidden(_i, not vis)
                rotulo.setText(f"Página {estado['page'] + 1} de {n} · {total} linhas")
                btn_prev.setEnabled(estado["page"] > 0)
                btn_next.setEnabled(estado["page"] < n - 1)

            def anterior():
                estado["page"] -= 1
                desenhar()

            def proxima():
                estado["page"] += 1
                desenhar()

            def trocar(texto):
                estado["per"] = int(texto)
                estado["page"] = 0
                desenhar()

            btn_prev.clicked.connect(anterior)
            btn_next.clicked.connect(proxima)
            combo.currentTextChanged.connect(trocar)
            desenhar()

        analytics = AnalyticsController()
        sources = SourceController()
        win = QMainWindow()
        win.setWindowTitle(f"PetroAnalytics PoC — Benchmark {self.periodo} (PySide6)")
        win.resize(1280, 800)
        central = QWidget()
        win.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(7)  # separacao visivel sidebar | chart area

        # Sidebar 25%
        side = QWidget()
        side_l = QVBoxLayout(side)
        self.collapse_btn = QPushButton("◀ Colapsar menu")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_host = QWidget()
        scroll_lay = QVBoxLayout(scroll_host)
        scroll_lay.setContentsMargins(0, 0, 0, 0)
        scroll_lay.setAlignment(Qt.AlignmentFlag.AlignTop)  # sessoes sempre no topo
        box = QToolBox()
        filtros = QWidget()
        fl = QVBoxLayout(filtros)
        fl.addWidget(QLabel("Empresas:"))
        grade_emp = QGridLayout()
        for _i, emp in enumerate(["PETROBRAS", "SHELL", "BP", "CHEVRON", "EXXONMOBIL", "TOTALENERGIES", "EQUINOR"]):
            chk = QCheckBox(emp)
            chk.setChecked(True)
            grade_emp.addWidget(chk, _i // 2, _i % 2)
        fl.addLayout(grade_emp)
        form = QFormLayout()
        self.combo = QComboBox()
        with analytics.fatos.db.connect() as _conn:
            _pers = sorted({r["periodo"] for r in _conn.execute(
                "SELECT DISTINCT periodo FROM tb_fato_financeiro").fetchall()})
        self.combo.addItems(_pers or ["2025Q4", "2026Q1", "2026Q2"])
        if self.periodo in _pers:
            self.combo.setCurrentText(self.periodo)
        form.addRow("Período:", self.combo)
        moeda_linha = QHBoxLayout()
        self.btn_usd = QPushButton("USD")
        self.btn_brl = QPushButton("BRL")
        moeda_linha.addWidget(self.btn_usd)
        moeda_linha.addWidget(self.btn_brl)
        form.addRow("Moeda PTAX:", moeda_linha)
        fl.addLayout(form)
        tema_btn = QPushButton("Alternar tema Light/Dark")
        fl.addWidget(tema_btn)
        box.addItem(filtros, "1 · Filtros")
        ajuda = QWidget()
        hl = QVBoxLayout(ajuda)
        hl.addWidget(QLabel("Fonte: RIs + SEC EDGAR.\nMoeda: USD/BRL bi (PTAX).\nUse as abas ao lado."))
        box.addItem(ajuda, "2 · Ajuda")
        scroll_lay.addWidget(box)
        scroll.setWidget(scroll_host)
        side_l.addWidget(self.collapse_btn)
        side_l.addWidget(scroll)

        # WorkArea 75%
        work = QWidget()
        work_l = QVBoxLayout(work)
        barra = QHBoxLayout()
        self.show_btn = QPushButton("▶ Menu")
        self.show_btn.setVisible(False)
        barra.addWidget(self.show_btn)
        barra.addStretch(1)
        barra.addWidget(QLabel("Duplo clique no gráfico = tela cheia · Esc fecha"))
        email_btn = QPushButton("✉ Enviar por e-mail")
        email_btn.setToolTip("Gera .eml com o gráfico (HTML+PNG+CSV) do período atual")
        refit_btn = QPushButton("⤢ Reajustar")
        refit_btn.setToolTip("Recalcula o range dos gráficos (útil após colapsar o menu)")
        barra.addWidget(refit_btn)
        barra.addWidget(email_btn)
        work_l.addLayout(barra)
        tabs = QTabWidget()
        tab1 = QWidget()
        grid = QGridLayout(tab1)
        self._bench_rubs = ("RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO", "DIVIDA_LIQUIDA")
        self._bench_cells: dict[str, object] = {}

        def _desenhar_benchmark():
            from PySide6.QtCore import Qt
            from config import INDICATORS, PTAX_FALLBACK
            from controllers import AnalyticsController as _AC
            nomes = {i["codigo"]: f"{i['nome']} ({i['unidade']})" for i in INDICATORS}
            fator = 1.0 if self.moeda == "USD" else PTAX_FALLBACK.get(self.periodo, 5.20)
            matriz = _AC().fatos.matriz(self.periodo)
            for rub in self._bench_rubs:
                widget = self._bench_cells.get(rub)
                if widget is None:
                    continue
                widget.clear()
                widget.setTitle(f"{nomes.get(rub, rub)} — {self.moeda} bi")
                widget._titulo = f"{nomes.get(rub, rub)} — {self.moeda} bi"
                dados = [(r["nome_empresa"], r["valor"] * fator)
                         for r in matriz if r["rubrica_padronizada"] == rub]
                dados.sort(key=lambda t: t[1], reverse=True)
                if dados:
                    teto = max(v for _, v in dados)
                    base = min(0.0, min(v for _, v in dados))
                    # folga p/ os rotulos das barras + linha da media (25% acima do topo)
                    widget.setYRange(base, teto * 1.25 + (teto - base) * 0.08, padding=0)
                    widget._fit_range = (base, teto * 1.25 + (teto - base) * 0.08)
                if dados:
                    from statistics import mean as _media
                    media = _media(v for _, v in dados)
                    linha = pg.InfiniteLine(pos=media, angle=0,
                                            pen=pg.mkPen("#888888", style=Qt.PenStyle.DashLine))
                    widget.addItem(linha)
                if not dados:
                    continue
                x = list(range(len(dados)))
                vals = [v for _, v in dados]
                # X explicito: com auto-range desligado o padrao (-0.5..0.5) fazia
                # as barras ocuparem a celula inteira em graficos de 2-3 empresas
                widget._fit_x = (-0.7, len(dados) - 0.3)
                widget.setXRange(-0.7, len(dados) - 0.3, padding=0)
                amplitude = (max(vals) - min(vals)) or 1.0
                for xi, (emp, val) in enumerate(dados):
                    barra = pg.BarGraphItem(x=[xi], height=[val], width=0.55,
                                            brush=self.CORES.get(emp, "#4a90d9"))
                    widget.addItem(barra)
                    vizinhos = [abs(val - vals[xj]) for xj in (xi - 1, xi + 1) if 0 <= xj < len(vals)]
                    dy = amplitude * 0.10 if any(g < amplitude * 0.08 for g in vizinhos) and xi % 2 else 0.0
                    # nome abreviado: evita texto largo cortando na celula estreita
                    txt = pg.TextItem(f"{emp[:11]}\n{val:.1f}", anchor=(0.5, 0))
                    txt.setPos(xi, val + dy)
                    widget.addItem(txt)
            win.setWindowTitle(f"PetroAnalytics PoC — Benchmark {self.periodo} ({self.moeda} bi, PySide6)")

        for i, rub in enumerate(self._bench_rubs):
            widget = pg.PlotWidget(title=f"{rub} (USD bi)")
            _polilar(widget, rub)
            widget.installEventFilter(self._plot_events)
            self._plots.append(widget)
            self._bench_cells[rub] = widget
            grid.addWidget(widget, i // 2, i % 2)
        _desenhar_benchmark()
        self._redesenhar = _desenhar_benchmark
        tabs.addTab(tab1, "Benchmark")
        tab2 = QWidget()
        tl = QVBoxLayout(tab2)
        fontes = sources.catalogo()
        form = QGroupBox("CRUD de fonte pública")
        fg = QGridLayout(form)
        campos = {}
        for i, (rot, chave, width) in enumerate([
                ("Empresa", "nome_empresa", 120), ("Documento", "nome_documento", 180),
                ("Tipo", "tipo_arquivo", 70), ("URL de origem", "url_fonte", 260),
                ("Pasta/arquivo", "caminho_local", 200), ("API JSON", "api_json", 160),
                ("Status", "status_processamento", 100)]):
            fg.addWidget(QLabel(rot), i // 4, (i % 4) * 2)
            le = QLineEdit()
            le.setMaximumWidth(width)
            campos[chave] = le
            fg.addWidget(le, i // 4, (i % 4) * 2 + 1)
        id_field = QLineEdit()
        id_field.setPlaceholderText("id_fonte (vazio = novo)")
        id_field.setMaximumWidth(120)
        fg.addWidget(id_field, 1, 6, 1, 2)
        msg = QLabel("pronto")
        fg.addWidget(msg, 1, 0, 1, 6)

        def _carregar(id_fonte: int) -> None:
            f = sources.obter(id_fonte) or {}
            for chave, le in campos.items():
                le.setText(str(f.get(chave) or ""))
            id_field.setText(str(id_fonte))

        def salvar() -> None:
            dados = {k: le.text().strip() for k, le in campos.items()}
            faltando = [k for k in ("nome_empresa", "url_fonte", "tipo_arquivo") if not dados[k]]
            if faltando:
                msg.setText(f"obrigatórios: {', '.join(faltando)}")
                return
            id_fonte = id_field.text().strip()
            if id_fonte.isdigit():
                ok = sources.atualizar(int(id_fonte), **dados)
                msg.setText(f"fonte #{id_fonte} atualizada" if ok else "id_fonte inexistente")
            else:
                novo = sources.registrar_manual(dados["nome_empresa"], dados["url_fonte"],
                                                dados["tipo_arquivo"],
                                                dados["caminho_local"] or None,
                                                dados["nome_documento"] or None,
                                                dados["api_json"] or None)
                msg.setText(f"fonte #{novo} criada")
            recarregar()

        def excluir() -> None:
            if not id_field.text().strip().isdigit():
                msg.setText("informe o id_fonte para excluir")
                return
            ok = sources.excluir(int(id_field.text().strip()))
            msg.setText("excluída" if ok else "id_fonte inexistente")
            recarregar()

        btns = QHBoxLayout()
        for texto, fn in (("💾 Salvar", salvar), ("Excluir", excluir),
                          ("Limpar", lambda: [le.clear() for le in campos.values()])):
            b = QPushButton(texto)
            b.clicked.connect(fn)
            btns.addWidget(b)
        fg.addLayout(btns, 2, 0, 1, 8)
        tl.addWidget(form)
        tabela = QTableWidget()
        rotulo_fontes = QLabel(f"Fontes catalogadas: {len(fontes)}")

        def _montar_tabela() -> None:
            dados = sources.catalogo()
            tabela.setRowCount(min(len(dados), 300))
            tabela.setColumnCount(8)
            tabela.setHorizontalHeaderLabels(["ID", "Empresa", "Documento", "Ext", "Pasta",
                                              "API JSON", "Download", "Status"])
            for i, fnt in enumerate(dados[:300]):
                celulas = (fnt.get("id_fonte"), fnt.get("nome_empresa"), fnt.get("nome_documento"),
                           fnt.get("extensao"), fnt.get("pasta_sistema"), fnt.get("api_json"),
                           fnt.get("data_download"), fnt.get("status_processamento"))
                for j, valor in enumerate(celulas):
                    item = QTableWidgetItem(str(valor or ""))
                    if j == 0:
                        item.setData(Qt.UserRole, int(fnt["id_fonte"]))
                    tabela.setItem(i, j, item)
            tabela.horizontalHeader().setStretchLastSection(True)

        def recarregar() -> None:
            _montar_tabela()
            rotulo_fontes.setText(f"Fontes catalogadas: {len(sources.catalogo())}")

        tabela.cellDoubleClicked.connect(
            lambda r, _c: _carregar(tabela.item(r, 0).data(Qt.UserRole)))
        _montar_tabela()
        tl.addWidget(rotulo_fontes)
        tl.addWidget(tabela)
        _polir_tabela(tabela)
        _paginar(tl, tabela)
        tabs.addTab(tab2, "Fontes (CRUD)")
        tab3 = QWidget()
        el = QVBoxLayout(tab3)
        el.addWidget(QLabel("Efetivo total — âncora anual (RIs trimestrais não publicam headcount)"))
        plot_ef = pg.PlotWidget(title="Efetivo por empresa (pessoas, âncora anual)")
        _polilar(plot_ef, "Efetivo (pessoas)")
        plot_ef.installEventFilter(self._plot_events)
        self._plots.append(plot_ef)
        with analytics.fatos.db.connect() as _conn:
            _rows = _conn.execute(
                "SELECT nome_empresa, periodo, valor FROM tb_fato_operacional"
                " WHERE indicador = 'EFETIVO_TOTAL' ORDER BY nome_empresa, periodo").fetchall()
        _ult = {}
        for _r in _rows:
            _ult[_r["nome_empresa"]] = (float(_r["valor"]), _r["periodo"])
        if _ult:
            _nomes = sorted(_ult)
            _vals_ef = [_ult[n][0] for n in _nomes]
            plot_ef.setYRange(0.0, max(_vals_ef) * 1.25, padding=0)
            plot_ef._fit_range = (0.0, max(_vals_ef) * 1.25)
            plot_ef._fit_x = (-0.7, len(_nomes) - 0.3)
            plot_ef.setXRange(-0.7, len(_nomes) - 0.3, padding=0)
            _bars = pg.BarGraphItem(x=list(range(len(_nomes))),
                                    height=[_ult[n][0] for n in _nomes], width=0.6, brush="#4a90d9")
            plot_ef.addItem(_bars)
            for _xi, _n in enumerate(_nomes):
                _t = pg.TextItem(f"{_n} {_ult[_n][1]}\n{_ult[_n][0]:,.0f}", anchor=(0.5, 0))
                _t.setPos(_xi, _ult[_n][0])
                plot_ef.addItem(_t)
        el.addWidget(plot_ef)
        tabs.addTab(tab3, "Efetivo")
        tab4 = QWidget()
        al = QVBoxLayout(tab4)
        qual = SourceController().qualidade()
        al.addWidget(QLabel(f"Alertas: {len(qual['alertas'])} · Fila de revisão: {len(qual['revisao'])}"))
        tab_alert = QTableWidget()
        _al = qual["alertas"][:200]
        tab_alert.setRowCount(len(_al))
        tab_alert.setColumnCount(3)
        tab_alert.setHorizontalHeaderLabels(["Tipo", "Descrição", "Severidade"])
        for i, a in enumerate(_al):
            tab_alert.setItem(i, 0, QTableWidgetItem(str(a.get("tipo_alerta", ""))))
            tab_alert.setItem(i, 1, QTableWidgetItem(str(a.get("descricao", ""))[:120]))
            tab_alert.setItem(i, 2, QTableWidgetItem(str(a.get("severidade", ""))))
        tab_alert.horizontalHeader().setStretchLastSection(True)
        al.addWidget(tab_alert)
        _polir_tabela(tab_alert)
        _paginar(al, tab_alert)
        tabs.addTab(tab4, "Auditoria")
        tab5 = QWidget()          # --- Gestão do ETL: o que rodou, o que falhou, quanto tempo ---
        et = QVBoxLayout(tab5)
        painel = sources.painel_etl()
        res = painel["resumo"]

        def _ms(v):
            return f"{v / 1000:.2f} s" if v else "—"

        kpi_row = QHBoxLayout()
        for rotulo, valor, cor in (
                ("Fontes", str(res["total"]), ""),
                ("Processadas", str(res["processadas"]), "#046c4e"),
                ("Com erro", str(res["com_erro"]), "#dc2626"),
                ("Sem dados", str(res["sem_dados"]), "#b45309"),
                ("Não processadas", str(res["nao_processadas"]), "#4b5563"),
                ("Não baixadas", str(res["nao_baixados"]), "#4b5563"),
                ("Duração total", _ms(res["duracao_total_ms"]), ""),
                ("Duração média", _ms(res["duracao_media_ms"]), ""),
                ("Execuções", str(res["total_execucoes"]), "")):
            card = QGroupBox(rotulo)
            lay = QVBoxLayout(card)
            lb = QLabel(valor)
            lb.setStyleSheet(f"font-size:15px;font-weight:800;color:{cor or '#0f172a'}")
            lay.addWidget(lb)
            kpi_row.addWidget(card)
        et.addLayout(kpi_row)
        et.addWidget(QLabel(
            f"Última execução: {res['ultima_execucao'] or '—'} · cargas: {res['ultimas_cargas']}"))

        filtros_etl = QHBoxLayout()
        cb_status = QComboBox()
        cb_status.addItems(["(todos)", "PROCESSADO", "SEM_DADOS", "ERRO", "NAO_PROCESSADO",
                            "NAO_BAIXADO", "SEM_PARSER", "PENDENTE"])
        busca = QLineEdit()
        busca.setPlaceholderText("filtrar (empresa, documento, erro)")
        filtros_etl.addWidget(QLabel("Status:"))
        filtros_etl.addWidget(cb_status)
        filtros_etl.addWidget(busca, 1)
        et.addLayout(filtros_etl)

        tab_etl = QTableWidget()
        cols_etl = ["ID", "Empresa", "Documento", "Ext", "Status", "Extr.", "Duração",
                    "Download", "Processado em", "Erro"]

        def _montar_etl():
            dados = painel["fontes"]
            tab_etl.setRowCount(len(dados))
            tab_etl.setColumnCount(len(cols_etl))
            tab_etl.setHorizontalHeaderLabels(cols_etl)
            for i, f in enumerate(dados):
                dur = f.get("duracao_ms")
                cel = [f.get("id_fonte"), f.get("nome_empresa"),
                       (f.get("nome_documento") or "")[:40], f.get("extensao"),
                       f.get("status_processamento"), f.get("n_extracoes"),
                       f"{dur / 1000:.2f}s" if dur else "",
                       (f.get("data_download") or "")[:19],
                       (f.get("data_processamento") or "")[:19],
                       (f.get("erro") or "")[:120]]
                for j, v in enumerate(cel):
                    item = QTableWidgetItem(str(v if v is not None else ""))
                    if j == 4:
                        item.setForeground(QtGui_color(str(v)))
                    tab_etl.setItem(i, j, item)
            tab_etl.horizontalHeader().setStretchLastSection(True)

        def QtGui_color(status: str):
            from PySide6.QtGui import QColor
            return QColor({"PROCESSADO": "#046c4e", "ERRO": "#dc2626",
                           "SEM_DADOS": "#b45309", "NAO_PROCESSADO": "#4b5563",
                           "NAO_BAIXADO": "#6b7280"}.get(status, "#0f172a"))

        def _filtrar_etl():
            st = cb_status.currentText()
            termo = busca.text().lower().strip()
            for i in range(tab_etl.rowCount()):
                itens = [tab_etl.item(i, j).text() if tab_etl.item(i, j) else "" for j in range(5)]
                ok_st = st == "(todos)" or itens[4] == st
                ok_t = not termo or termo in " ".join(itens).lower() or termo in (
                    tab_etl.item(i, 9).text().lower() if tab_etl.item(i, 9) else "")
                tab_etl.setRowHidden(i, not (ok_st and ok_t))

        cb_status.currentTextChanged.connect(lambda _t: _filtrar_etl())
        busca.textChanged.connect(lambda _t: _filtrar_etl())
        _montar_etl()
        _polir_tabela(tab_etl)
        et.addWidget(tab_etl, 1)          # tabela principal ocupa o espaco livre
        _paginar(et, tab_etl)

        hist = QTableWidget()
        _ex = painel["execucoes"][:25]
        hist.setRowCount(len(_ex))
        hist.setColumnCount(9)
        hist.setHorizontalHeaderLabels(["Início", "Fim", "Duração", "Arquivos", "Extrações",
                                        "Cargas", "PDFs pulados", "Revisão", "Erros"])
        for i, e in enumerate(_ex):
            vals = [e["inicio_em"], e["fim_em"],
                    f"{e['duracao_ms'] / 1000:.2f}s" if e.get("duracao_ms") else "",
                    e["arquivos_processados"], e["extracoes"], e["cargas"],
                    e["pulados_pdf"], e["revisao"], e["erros"]]
            for j, v in enumerate(vals):
                hist.setItem(i, j, QTableWidgetItem(str(v if v is not None else "")))
        _polir_tabela(hist)
        hist.setMaximumHeight(190)        # historico em painel compacto
        et.addWidget(QLabel("Histórico de execuções do pipeline"))
        et.addWidget(hist)
        _paginar(et, hist)
        tabs.addTab(tab5, "Gestão ETL")
        work_l.addWidget(tabs)

        # --- UX: foco em tela cheia (reparenta o plot e devolve ao fechar) ---
        from PySide6.QtWidgets import QDialog, QInputDialog

        def _focar(w) -> None:
            lay_orig = w.parentWidget().layout()
            idx = lay_orig.indexOf(w)
            pos = None                       # QGridLayout exige (row, col, rowSpan, colSpan)
            if hasattr(lay_orig, "getItemPosition"):
                try:
                    pos = lay_orig.getItemPosition(idx)
                except Exception:
                    pos = None
            dlg = QDialog(win)
            dl = QVBoxLayout(dlg)
            dl.setContentsMargins(4, 4, 4, 4)
            dl.addWidget(w)
            dlg.setWindowTitle(f"{getattr(w, '_titulo', 'Gráfico')} — {self.periodo} ({self.moeda} bi)")
            dlg.resize(1100, 680)

            def _voltar(result: int) -> None:
                if hasattr(lay_orig, "insertWidget"):
                    lay_orig.insertWidget(idx, w)
                elif pos:
                    lay_orig.addWidget(w, *pos)
                else:
                    lay_orig.addWidget(w)
                _reajustar(w)
                self._focar_plot = None

            dlg.finished.connect(_voltar)
            self._focar_plot = _voltar
            dlg.show()
            _reajustar(w)

        self._focar = _focar

        def _email() -> None:
            from PySide6.QtWidgets import QInputDialog
            dest, ok = QInputDialog.getText(win, "Enviar benchmark por e-mail", "Destinatário:")
            if not ok or not dest.strip():
                return
            try:
                from controllers import MailController
                r = MailController().enviar(dest.strip(), "RECEITA_LIQUIDA", self.periodo)
                win.statusBar().showMessage(
                    f"E-mail gerado: {Path(r['resultado']).name} · anexos: {', '.join(r['anexos'])}")
            except Exception as exc:
                win.statusBar().showMessage(f"Falha ao gerar e-mail: {exc}")

        def _refit() -> None:
            self._reajustar_todos()
            redesenhar = getattr(self, "_redesenhar", None)
            if redesenhar:
                redesenhar()

        email_btn.clicked.connect(_email)
        refit_btn.clicked.connect(_refit)
        tabs.currentChanged.connect(lambda _i: self._reajustar_todos())
        splitter.splitterMoved.connect(lambda *_a: self._reajustar_todos())

        splitter.addWidget(side)
        splitter.addWidget(work)
        splitter.setSizes([300, 980])
        layout.addWidget(splitter)

        def alternar_tema():
            self.dark = not self.dark
            self._app.setStyleSheet(DARK_QSS if self.dark else LIGHT_QSS)
            _aplicar_fundo_graficos()

        def colapsar():
            if side.isVisible():
                side.setVisible(False)  # colapsado: some por completo
                self.collapse_btn.setText("◀ Colapsar menu")
                self.show_btn.setVisible(True)
            else:
                side.setVisible(True)
                self.show_btn.setVisible(False)
                splitter.setSizes([300, 980])

        tema_btn.clicked.connect(alternar_tema)
        self.collapse_btn.clicked.connect(colapsar)
        self.show_btn.clicked.connect(colapsar)
        self.btn_usd.clicked.connect(lambda: self._trocar_moeda("USD"))
        self.btn_brl.clicked.connect(lambda: self._trocar_moeda("BRL"))
        self.combo.currentTextChanged.connect(self._trocar_periodo)
        try:
            _cont = analytics.fatos.contar()
            self.window.statusBar().showMessage(
                f"{_cont['fontes']} fontes · {_cont['fatos']} fatos · período {self.periodo}")
        except Exception:
            pass
        self._app.setStyleSheet(LIGHT_QSS)
        _aplicar_fundo_graficos()
        self.window = win
        return win

    def _trocar_moeda(self, moeda: str) -> None:
        self.moeda = moeda
        redesenhar = getattr(self, "_redesenhar", None)
        if redesenhar:
            redesenhar()

    def _trocar_periodo(self, periodo: str) -> None:
        from controllers import AnalyticsController
        self.periodo = periodo
        redesenhar = getattr(self, "_redesenhar", None)
        if redesenhar:
            redesenhar()
        try:
            _cont = AnalyticsController().fatos.contar()
            self.window.statusBar().showMessage(
                f"{_cont['fontes']} fontes · {_cont['fatos']} fatos · período {self.periodo}")
        except Exception:
            pass

    def run(self) -> int:
        self.build()
        assert self.window is not None
        self.window.show()
        return int(self._app.exec())
