"""Subsistema planilhas (.xls/.xlsx/.xlsm/.csv): valida container, lista sheets,
alerta macro em .xlsm. CSV = texto com checagem de cabecalho."""
from __future__ import annotations
import csv
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from src.etl.formats.base import BaseFormatHandler

OLE = b"\xD0\xCF\x11\xE0"


class SheetHandler(BaseFormatHandler):
    EXTS = (".xls", ".xlsx", ".xlsm", ".csv")

    def validate(self, path: Path) -> list[str]:
        suf = path.suffix.lower()
        head = path.read_bytes()[:8]
        if suf in (".xlsx", ".xlsm") and not head.startswith(b"PK"):
            return [f"{path.name}: esperado ZIP/OOXML (PK), magic diferente"]
        if suf == ".xls" and not head.startswith(OLE):
            return [f"{path.name}: esperado OLE (.xls legado)"]
        return []

    def analyze(self, path: Path) -> dict:
        suf = path.suffix.lower()
        if suf == ".csv":
            return self._csv_info(path)
        if suf == ".xls":
            return {"container": "OLE-legado", "sheets": [],
                    "note": "conversao isolada (subprocess) recomendada p/ leitura total"}
        return self._ooxml_info(path)

    def _csv_info(self, path: Path) -> dict:
        rows, cols, header = 0, 0, []
        with open(path, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            for i, row in enumerate(csv.reader(f)):
                if i == 0:
                    header, cols = row[:20], len(row)
                rows += 1
                if rows > 500_000:
                    break
        return {"container": "CSV", "rows": rows, "cols": cols, "header": header}

    def _ooxml_info(self, path: Path) -> dict:
        info: dict = {"container": "OOXML", "sheets": [], "has_macro": False}
        try:
            z = zipfile.ZipFile(path)
            names = z.namelist()
            info["has_macro"] = "xl/vbaProject.bin" in names
            try:
                wb = z.read("xl/workbook.xml")
                for el in ET.fromstring(wb).iter():
                    if el.tag.endswith("}sheet") and el.get("name"):
                        info["sheets"].append(el.get("name"))
            except KeyError:
                pass
            if not info["sheets"]:
                try:
                    import openpyxl  # type: ignore
                    info["sheets"] = openpyxl.load_workbook(path, read_only=True).sheetnames
                except Exception:
                    pass
        except Exception as e:  # noqa: BLE001
            info["error"] = str(e)[:160]
        if info["has_macro"]:
            info["macro_warning"] = "XLSM com macro: NUNCA executar; ler apenas valores"
        return info
