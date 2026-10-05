"""Base dos coletores por formato (SOLID: OCP — novo formato = nova classe;
DIP — o dispatcher depende desta abstracao, nao de cada formato)."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class CollectedFile:
    url: str
    local_path: str
    sha256: str
    size: int
    ext: str
    meta: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class BaseFormatHandler:
    EXTS: tuple[str, ...] = ()
    MAGIC: dict[bytes, str] = {}

    @classmethod
    def matches(cls, url: str) -> bool:
        return Path(urllib_path(url)).suffix.lower() in cls.EXTS

    def validate(self, path: Path) -> list[str]:
        """Checa magic bytes; retorna warnings (vazio = ok)."""
        head = path.read_bytes()[:8]
        if self.MAGIC and not any(head.startswith(m) for m in self.MAGIC):
            return [f"magic bytes inesperados em {path.name}"]
        return []

    def analyze(self, path: Path) -> dict:
        raise NotImplementedError

    def collect(self, url: str, dest_dir: Path, registry=None,
                source_id: str = "", source_name: str = "", company: str = "") -> CollectedFile:
        from src.etl.acquisition import download_one
        dest_dir.mkdir(parents=True, exist_ok=True)
        r = download_one(url, dest_dir)
        path = Path(r.local_path)
        warnings = self.validate(path)
        try:
            meta = self.analyze(path)
        except Exception as e:  # noqa: BLE001 - analise nunca derruba a coleta
            meta, warnings = {"error": str(e)[:200]}, warnings + ["analyze falhou"]
        meta.update({"content_type": r.content_type, "cached": r.from_cache})
        sidecar = path.with_suffix(path.suffix + ".meta.json")
        sidecar.write_text(json.dumps({"url": url, "sha256": r.sha256, "size": r.size,
                                       "ext": path.suffix.lower(), "collected_at": now(),
                                       "meta": meta, "warnings": warnings},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
        if registry is not None:
            registry.log_download(company, source_id, source_name, url, str(path),
                                  r.sha256, r.size, r.content_type,
                                  "OK" if not warnings else f"OK+WARN: {'; '.join(warnings)}"[:200])
        return CollectedFile(url, str(path), r.sha256, r.size, path.suffix.lower(), meta, warnings)


def urllib_path(url: str) -> str:
    import urllib.parse
    return urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
