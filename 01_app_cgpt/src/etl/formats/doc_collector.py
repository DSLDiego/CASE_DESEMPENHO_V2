"""Subsistema docs (.docx/.doc): valida container, conta paragrafos;
.doc legado sinaliza conversao isolada (nunca COM direto no coletor)."""
from __future__ import annotations
import re
import zipfile
from pathlib import Path
from src.etl.formats.base import BaseFormatHandler

OLE = b"\xD0\xCF\x11\xE0"


class DocHandler(BaseFormatHandler):
    EXTS = (".doc", ".docx")

    def validate(self, path: Path) -> list[str]:
        head = path.read_bytes()[:8]
        if path.suffix.lower() == ".docx" and not head.startswith(b"PK"):
            return [f"{path.name}: esperado ZIP/OOXML (PK)"]
        if path.suffix.lower() == ".doc" and not head.startswith(OLE):
            return [f"{path.name}: esperado OLE (.doc legado)"]
        return []

    def analyze(self, path: Path) -> dict:
        if path.suffix.lower() == ".doc":
            return {"container": "OLE-legado", "needs_conversion": True,
                    "note": "converter em subprocess isolado (antiword/soffice); apos converter, tratar como TXT"}
        try:
            z = zipfile.ZipFile(path)
            try:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            except KeyError:
                return {"container": "OOXML?", "error": "word/document.xml ausente"}
            paras = len(re.findall(r"<w:p[\s>/]", xml))
            tables = len(re.findall(r"<w:tbl[\s>/]", xml))
            return {"container": "DOCX", "paragraphs": paras, "tables": tables,
                    "needs_conversion": False}
        except Exception as e:  # noqa: BLE001
            return {"container": "?", "error": str(e)[:160]}
