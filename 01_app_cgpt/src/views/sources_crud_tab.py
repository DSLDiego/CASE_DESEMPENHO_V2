"""Aba gestao de fontes (View MVC): CRUD + verificacao + download de novidades."""
from __future__ import annotations
import threading
from pathlib import Path
from PySide6.QtCore import Signal, QObject, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
                               QTableWidgetItem, QInputDialog, QMessageBox, QHeaderView, QTextEdit)

from src.etl import source_check as SC
from src.services.source_registry import SourceRegistry

BASE = Path(__file__).resolve().parents[2]


class _Sig(QObject):
    line = Signal(str)
    done = Signal()


class SourcesCrudTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.reg = SourceRegistry()
        self.sig = _Sig()
        self.sig.line.connect(self.log.append)
        self.sig.done.connect(self.reload)
        lay = QVBoxLayout(self)

        row = QHBoxLayout()
        for label, fn in [("＋ Adicionar", self._add), ("✎ Editar URL", self._edit),
                          ("⏻ On/Off", self._toggle), ("🗑 Remover", self._remove),
                          ("⬇ Exportar CSV", self._export)]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)

        self.tbl = QTableWidget()
        lay.addWidget(self.tbl)

        row2 = QHBoxLayout()
        b_check = QPushButton("🔍 Verificar novidades")
        b_check.clicked.connect(lambda: self._bg(self._do_check))
        b_dl = QPushButton("⬇ Baixar novos")
        b_dl.clicked.connect(lambda: self._bg(self._do_download))
        row2.addWidget(b_check)
        row2.addWidget(b_dl)
        row2.addStretch(1)
        lay.addLayout(row2)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(160)
        lay.addWidget(self.log)
        self.reload()

    # ---- grade ----
    def reload(self) -> None:
        self.reg.load()
        srcs = self.reg.list()
        self.tbl.setRowCount(len(srcs))
        self.tbl.setColumnCount(6)
        self.tbl.setHorizontalHeaderLabels(["ID", "Empresa", "Ativa", "Últ. verificação",
                                            "Downloads", "Página RI"])
        for i, s in enumerate(srcs):
            vals = [s["id"], s["company"], "ON" if s["active"] else "OFF",
                    str(s.get("last_check_at") or "-"), str(s.get("downloads_count", 0)),
                    s["results_page"]]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.tbl.setItem(i, j, it)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def _sel(self) -> dict | None:
        r = self.tbl.currentRow()
        srcs = self.reg.list()
        if 0 <= r < len(srcs):
            return srcs[r]
        QMessageBox.information(self, "Fontes", "Selecione uma linha.")
        return None

    # ---- CRUD ----
    def _add(self) -> None:
        sid, ok = QInputDialog.getText(self, "Nova fonte", "ID (ex: BP_RI):")
        if not ok or not sid:
            return
        comp, _ = QInputDialog.getText(self, "Nova fonte", "Empresa:")
        url, _ = QInputDialog.getText(self, "Nova fonte", "Página de resultados (URL):")
        try:
            self.reg.add(sid.strip().upper(), comp.strip().upper(), sid.strip(), url.strip())
        except ValueError as e:
            QMessageBox.warning(self, "Fontes", str(e))
        self.reload()

    def _edit(self) -> None:
        s = self._sel()
        if not s:
            return
        url, ok = QInputDialog.getText(self, "Editar", "Página de resultados:", text=s["results_page"])
        if ok and url:
            self.reg.update(s["id"], results_page=url.strip())
            self.reload()

    def _toggle(self) -> None:
        s = self._sel()
        if s:
            self.reg.set_active(s["id"], not s["active"])
            self.reload()

    def _remove(self) -> None:
        s = self._sel()
        if s and QMessageBox.question(self, "Fontes", f"Remover {s['id']}?") == QMessageBox.Yes:
            self.reg.remove(s["id"])
            self.reload()

    def _export(self) -> None:
        n = self.reg.export_csv(BASE / "data" / "ri_registry.csv")
        self.log.append(f"{n} fontes -> data/ri_registry.csv")

    # ---- verificacao em background ----
    def _bg(self, fn) -> None:
        threading.Thread(target=self._wrap(fn), daemon=True).start()

    def _wrap(self, fn):
        def run():
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                self.sig.line.emit(f"ERRO: {e}")
            finally:
                self.sig.done.emit()
        return run

    def _do_check(self) -> None:
        for s in self.reg.list(only_active=True):
            rep = SC.check_source(s, self.reg)
            if rep["ok"]:
                self.sig.line.emit(f"[{s['id']}] {len(rep['new'])} novos / {rep['known']} conhecidos")
            else:
                self.sig.line.emit(f"[{s['id']}] FALHA: {rep['error']}")

    def _do_download(self) -> None:
        for s in self.reg.list(only_active=True):
            rep = SC.check_source(s, self.reg)
            for r in SC.download_new(rep, self.reg):
                self.sig.line.emit(f"[{'OK' if r['ok'] else 'FAIL'}] {r['url'][:90]}")
