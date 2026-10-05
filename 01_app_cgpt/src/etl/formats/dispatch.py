"""Dispatcher: escolhe o subsistema pela extensao; coleta avulsa ou via mapa."""
from __future__ import annotations
import csv
import urllib.parse
from pathlib import Path
from src.etl.formats.base import BaseFormatHandler, CollectedFile
from src.etl.formats.pdf_collector import PdfHandler
from src.etl.formats.sheet_collector import SheetHandler
from src.etl.formats.doc_collector import DocHandler
from src.etl.formats.txt_collector import TxtHandler

HANDLERS: list[BaseFormatHandler] = [PdfHandler(), SheetHandler(), DocHandler(), TxtHandler()]


class GenericHandler(BaseFormatHandler):
    EXTS = ()
    @classmethod
    def matches(cls, url: str) -> bool:
        return True
    def analyze(self, path: Path) -> dict:
        return {"container": "generico", "note": "sem analisador especifico"}


def handler_for(url: str) -> BaseFormatHandler:
    for h in HANDLERS:
        if h.matches(url):
            return h
    return GenericHandler()


def collect_one(url: str, dest_dir: Path, registry=None, source_id: str = "",
                source_name: str = "", company: str = "") -> CollectedFile:
    return handler_for(url).collect(url, Path(dest_dir), registry,
                                    source_id, source_name, company)


def collect_from_map(map_csv: Path | str, raw_base: Path | str, registry=None,
                     ext_filter: str = "", company: str = "",
                     min_score: int = 50, limit: int = 20) -> list[dict]:
    """Baixa documentos do mapa (source_map.csv) pelo subsistema de cada formato."""
    raw_base, out = Path(raw_base), []
    with open(map_csv, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if (not ext_filter or r["ext"] == ext_filter)
                and (not company or r["company"] == company)
                and int(r.get("score") or 0) >= min_score][:limit]
    for r in rows:
        dest = raw_base / r["company"] / "INBOX"
        try:
            cf = collect_one(r["url"], dest, registry, r["source_id"], "", r["company"])
            out.append({"url": r["url"], "ok": True, "path": cf.local_path,
                        "handler": type(handler_for(r["url"])).__name__,
                        "warnings": cf.warnings, "meta": cf.meta})
        except Exception as e:  # noqa: BLE001
            out.append({"url": r["url"], "ok": False, "error": str(e)[:200]})
    return out
