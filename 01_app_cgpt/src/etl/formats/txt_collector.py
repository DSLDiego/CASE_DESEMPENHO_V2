"""Subsistema TXT (.txt/.log/.md): deteccao de encoding em streaming
(BigString: nunca carrega tudo), contagem de linhas/caracteres."""
from __future__ import annotations
from pathlib import Path
from src.etl.formats.base import BaseFormatHandler


class TxtHandler(BaseFormatHandler):
    EXTS = (".txt", ".log", ".md")

    def analyze(self, path: Path) -> dict:
        with open(path, "rb") as f:
            head = f.read(65536)
        encoding = "utf-8"
        try:
            head.decode("utf-8")
        except UnicodeDecodeError:
            encoding = "latin1"
        lines, chars = 0, 0
        with open(path, "r", encoding=encoding, errors="ignore") as f:
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                chars += len(chunk)
                lines += chunk.count("\n")
                if chars > 50_000_000:
                    break
        return {"container": "TEXT", "encoding": encoding, "lines": lines,
                "chars": chars, "truncated": chars >= 50_000_000}
