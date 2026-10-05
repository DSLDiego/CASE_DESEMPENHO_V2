"""CRUD do registro de fontes publicas (JSON) + log de downloads (CSV).

SOLID/SRP: esta classe so gerencia o catalogo. Download e verificacao
vivem em src/etl/source_check.py; a fachada em src/services/source_services.py.
"""
from __future__ import annotations
import csv
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REGISTRY_DEFAULT = Path(__file__).resolve().parents[2] / "config" / "ri_registry.json"
DOWNLOADS_CSV_DEFAULT = Path(__file__).resolve().parents[2] / "data" / "source_downloads.csv"

CSV_FIELDS = ["downloaded_at", "company", "source_id", "source_name", "url",
              "local_path", "sha256", "size_bytes", "content_type", "status", "authority"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SourceRegistry:
    """CRUD persistido em JSON (escrita atomica tmp+replace)."""

    def __init__(self, path: Path | str = REGISTRY_DEFAULT,
                 csv_log: Path | str = DOWNLOADS_CSV_DEFAULT) -> None:
        self.path = Path(path)
        self.csv_log = Path(csv_log)
        self._data: dict = {"sources": []}
        self.load()

    # ---- persistencia ----
    def load(self) -> None:
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        self._data.setdefault("sources", [])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        Path(tmp).replace(self.path)

    # ---- CRUD ----
    def list(self, only_active: bool = False) -> list[dict]:
        srcs = self._data["sources"]
        return [s for s in srcs if s.get("active", True)] if only_active else list(srcs)

    def get(self, source_id: str) -> dict | None:
        return next((s for s in self._data["sources"] if s["id"] == source_id), None)

    def add(self, source_id: str, company: str, name: str, results_page: str,
            domains: list[str] | None = None, doc_types: list[str] | None = None) -> dict:
        if self.get(source_id):
            raise ValueError(f"fonte {source_id} ja existe")
        rec = {"id": source_id, "company": company.upper(), "name": name,
               "results_page": results_page, "domains": domains or [],
               "doc_types": doc_types or ["EARNINGS_RELEASE"],
               "active": True, "added_at": _now(), "updated_at": _now(),
               "last_check_at": None, "last_check_result": None,
               "last_download_at": None, "downloads_count": 0}
        self._data["sources"].append(rec)
        self.save()
        return rec

    def update(self, source_id: str, **fields) -> dict:
        rec = self.get(source_id)
        if rec is None:
            raise KeyError(f"fonte {source_id} nao encontrada")
        for k, v in fields.items():
            if k in ("id", "added_at"):
                continue
            rec[k] = v
        rec["updated_at"] = _now()
        self.save()
        return rec

    def set_active(self, source_id: str, active: bool) -> dict:
        return self.update(source_id, active=active)

    def remove(self, source_id: str) -> None:
        before = len(self._data["sources"])
        self._data["sources"] = [s for s in self._data["sources"] if s["id"] != source_id]
        if len(self._data["sources"]) == before:
            raise KeyError(f"fonte {source_id} nao encontrada")
        self.save()

    # ---- eventos (verificacao / download) ----
    def record_check(self, source_id: str, result: str) -> None:
        rec = self.get(source_id)
        if rec:
            rec["last_check_at"] = _now()
            rec["last_check_result"] = result
            rec["updated_at"] = rec["last_check_at"]
            self.save()

    def record_download(self, source_id: str) -> None:
        rec = self.get(source_id)
        if rec:
            rec["last_download_at"] = _now()
            rec["downloads_count"] = int(rec.get("downloads_count", 0)) + 1
            rec["updated_at"] = rec["last_download_at"]
            self.save()

    # ---- CSV ----
    def export_csv(self, dest: Path | str) -> int:
        dest = Path(dest)
        srcs = self.list()
        with open(dest, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["id", "company", "name", "results_page",
                                              "active", "added_at", "last_check_at",
                                              "last_download_at", "downloads_count"])
            w.writeheader()
            for s in srcs:
                w.writerow({k: s.get(k) for k in w.fieldnames})
        return len(srcs)

    def log_download(self, company: str, source_id: str, source_name: str, url: str,
                     local_path: str = "", sha256: str = "", size: int = 0,
                     content_type: str = "", status: str = "OK",
                     authority: str = "UNKNOWN") -> None:
        """Controle do que ja foi baixado (anti-repeticao auditavel)."""
        self.csv_log.parent.mkdir(parents=True, exist_ok=True)
        new = not self.csv_log.exists()
        with open(self.csv_log, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if new:
                w.writeheader()
            w.writerow({"downloaded_at": _now(), "company": company, "source_id": source_id,
                        "source_name": source_name, "url": url, "local_path": local_path,
                        "sha256": sha256, "size_bytes": size, "content_type": content_type,
                        "status": status, "authority": authority})

    def known_urls(self) -> set[str]:
        """URLs ja baixadas (para nao repetir download)."""
        urls: set[str] = set()
        if self.csv_log.exists():
            with open(self.csv_log, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("status") == "OK" and row.get("url"):
                        urls.add(row["url"])
        return urls
