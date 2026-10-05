"""Aba painel das fontes (View MVC): documentos + APIs JSON, so leitura."""
from __future__ import annotations
import threading
from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
                               QTableWidgetItem, QHeaderView, QLabel)

from src.etl import api_probe as API
from src.repositories.sqlite_repo import SQLiteRepository
from src.services.source_panel import build_api_panel, build_documents_panel
from src.services.source_registry import SourceRegistry


class _Sig(QObject):
    line = Signal(str)
    done = Signal()


class SourcesPanelTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.repo = SQLiteRepository()
        self.reg = SourceRegistry()
        self.sig = _Sig()
        self.sig.line.connect(self._on_line)
        self.sig.done.connect(self.reload)
        lay = QVBoxLayout(self)

        row = QHBoxLayout()
        b_up = QPushButton("↻ Atualizar")
        b_up.clicked.connect(self.reload)
        b_api = QPushButton("🔌 Verificar APIs (JSON)")
        b_api.clicked.connect(self._probe_bg)
        self.lbl = QLabel("")
        row.addWidget(b_up)
        row.addWidget(b_api)
        row.addWidget(self.lbl)
        row.addStretch(1)
        lay.addLayout(row)

        lay.addWidget(QLabel("Documentos — site, documento, extensão, pasta, data do download:"))
        self.tbl_docs = QTableWidget()
        lay.addWidget(self.tbl_docs)
        lay.addWidget(QLabel("APIs/serviços web públicos (JSON):"))
        self.tbl_api = QTableWidget()
        lay.addWidget(self.tbl_api)
        self.reload()

    def _fill(self, tbl: QTableWidget, headers: list[str], rows: list[list]) -> None:
        tbl.setRowCount(len(rows))
        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                tbl.setItem(i, j, QTableWidgetItem("" if v is None else str(v)))
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def reload(self) -> None:
        self.reg.load()
        docs = build_documents_panel(self.repo, self.reg)
        self._fill(self.tbl_docs, ["Site", "Documento", "Extensão", "Pasta", "Data download", "Origem"],
                   [[d["site"], d["documento"], d["extensao"], d["pasta"],
                     d["data_download"], d["origem"]] for d in docs])
        apis = build_api_panel(self.reg)
        self._fill(self.tbl_api, ["Site", "Fonte", "API JSON", "Status", "Verificada em", "Amostra"],
                   [[a["site"], a["fonte"], a["api_url"], a["status"],
                     a["verificada_em"], a["amostra"]] for a in apis])
        self.lbl.setText(f"{len(docs)} documentos · {len(apis)} fontes")

    def _on_line(self, msg: str) -> None:
        self.lbl.setText(msg)

    def _probe_bg(self) -> None:
        threading.Thread(target=self._probe, daemon=True).start()

    def _probe(self) -> None:
        try:
            for s in self.reg.list(only_active=True):
                self.sig.line.emit(f"sondando {s['id']}…")
                r = API.probe_source(s, self.reg)
                self.sig.line.emit(f"{s['id']}: {r.get('api_url') or r.get('error', 'sem JSON')} ")
        except Exception as e:  # noqa: BLE001
            self.sig.line.emit(f"ERRO: {e}")
        finally:
            self.sig.done.emit()
