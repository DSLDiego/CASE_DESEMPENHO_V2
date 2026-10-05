"""Verificacao de documentos novos + download do que for possivel.

Reusa discovery/download de acquisition.py; o estado do que ja foi baixado
vem do CSV de downloads (SourceRegistry.known_urls) + manifest local.
"""
from __future__ import annotations
from pathlib import Path

from src.etl import acquisition as AC
from src.services.source_registry import SourceRegistry

BASE = Path(__file__).resolve().parents[2]


def check_source(source: dict, registry: SourceRegistry,
                 raw_base: Path | str = BASE / "data" / "raw") -> dict:
    """Consulta a pagina de RI e separa links em novos vs ja baixados."""
    known = registry.known_urls()
    try:
        html = AC.fetch_url(source["results_page"])
    except Exception as e:  # noqa: BLE001 - rede instavel e esperada
        registry.record_check(source["id"], f"CHECK_FAILED: {e}"[:200])
        return {"source_id": source["id"], "ok": False, "error": str(e)[:200],
                "new": [], "known": 0}
    cands = AC.discover_from_html(html, source["results_page"],
                                  source["company"], source.get("domains", []))
    new = [c for c in cands if c.url not in known]
    new.sort(key=lambda c: -c.score)
    registry.record_check(source["id"], f"OK: {len(new)} novos de {len(cands)} links")
    return {"source_id": source["id"], "ok": True,
            "new": [{"url": c.url, "title": c.title, "score": c.score,
                     "authority": c.authority} for c in new[:50]],
            "known": len(cands) - len(new), "total": len(cands)}


def check_all(registry: SourceRegistry | None = None) -> list[dict]:
    registry = registry or SourceRegistry()
    return [check_source(s, registry) for s in registry.list(only_active=True)]


def download_new(report: dict, registry: SourceRegistry,
                 raw_base: Path | str = BASE / "data" / "raw",
                 min_score: int = 50) -> list[dict]:
    """Baixa candidatos novos (score>=minimo) e registra cada arquivo no CSV."""
    from src.etl.acquisition import download_one
    source = registry.get(report["source_id"])
    out: list[dict] = []
    for cand in report.get("new", []):
        if cand["score"] < min_score:
            out.append({"url": cand["url"], "ok": False, "skipped": "score baixo"})
            continue
        dest = Path(raw_base) / source["company"] / "INBOX"
        try:
            r = download_one(cand["url"], dest)
            registry.log_download(source["company"], source["id"], source["name"],
                                  cand["url"], r.local_path, r.sha256, r.size,
                                  r.content_type, "OK", cand["authority"])
            registry.record_download(source["id"])
            out.append({"url": cand["url"], "ok": True, "path": r.local_path,
                        "sha": r.sha256, "cached": r.from_cache})
        except Exception as e:  # noqa: BLE001
            registry.log_download(source["company"], source["id"], source["name"],
                                  cand["url"], status=f"FAILED: {e}"[:200])
            out.append({"url": cand["url"], "ok": False, "error": str(e)[:200]})
    return out
