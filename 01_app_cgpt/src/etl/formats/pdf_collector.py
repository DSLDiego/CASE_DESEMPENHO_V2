"""Subsistema PDF: valida %PDF, conta paginas, detecta escaneado (sem OCR)."""
from __future__ import annotations
import re
from pathlib import Path
from src.etl.formats.base import BaseFormatHandler


class PdfHandler(BaseFormatHandler):
    EXTS = (".pdf",)
    MAGIC = {b"%PDF": "pdf"}

    def analyze(self, path: Path) -> dict:
        data = path.read_bytes()[:20_000_000]  # teto 20MB p/ analise
        pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
        sample = b"\n".join(re.findall(rb"[\x20-\x7e]{6,}", data[:2_000_000])[:4000])
        text_chars = len(sample)
        profile = "SCANNED_PDF" if text_chars < 200 else "TEXT_PDF"
        warns = []
        if profile == "SCANNED_PDF":
            warns.append("PDF provavelmente escaneado: extracao textual ~vazia (OCR = evolucao V4)")
        return {"pages_detected": pages, "text_sample_chars": text_chars,
                "profile": profile, "handler_warnings": warns}
