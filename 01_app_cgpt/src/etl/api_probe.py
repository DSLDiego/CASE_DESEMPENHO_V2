"""Sonda de APIs/servicos web publicos (JSON) nos sites de RI.

Estrategia: 1) tenta o padrao AEM `.model.json` (ex.: Shell expoe um);
2) extrai links `.json` do HTML da pagina; 3) faz GET e valida se e JSON.
Nada quebra sem rede: falha vira status, nao excecao.
"""
from __future__ import annotations
import re
import urllib.parse
from datetime import datetime, timezone

CANDIDATE_LIMIT = 8


def candidate_api_urls(page_url: str, html: str = "") -> list[str]:
    out: list[str] = []
    base = (page_url or "").rstrip("/")
    if base and not base.lower().endswith(".json"):
        out.append(base + ".model.json")  # padrao Adobe AEM
    for pat in (r'["\'](https?://[^"\']+\.json(?:\?[^"\']*)?)["\']',
                r'["\']((?:/[^"\']*?|[\w\-./]*?\.json)(?:\?[^"\']*)?)["\']'):
        for m in re.findall(pat, html or "", re.I):
            out.append(m if m.startswith("http") else urllib.parse.urljoin(page_url, m))
    seen, uniq = set(), []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq[:CANDIDATE_LIMIT]


def probe_url(url: str, timeout: int = 15) -> dict:
    import requests
    try:
        r = requests.get(url, timeout=timeout,
                         headers={"User-Agent": "BenchmarkPoC/1.0",
                                  "Accept": "application/json"})
    except Exception as e:  # noqa: BLE001
        return {"url": url, "ok": False, "error": str(e)[:160]}
    body = r.content or b""
    is_json = "json" in (r.headers.get("Content-Type", "").lower())
    sample = ""
    if r.status_code == 200:
        try:
            import json as _json
            data = _json.loads(body[:500_000])
            is_json = True
            if isinstance(data, dict):
                sample = ", ".join(list(data.keys())[:8])
            elif isinstance(data, list):
                sample = f"lista[{len(data)}]"
        except Exception:  # noqa: BLE001
            pass
    return {"url": url, "ok": bool(r.status_code == 200 and is_json),
            "status": r.status_code,
            "content_type": r.headers.get("Content-Type", "")[:80],
            "size": len(body), "sample": sample[:200]}


def probe_source(source: dict, registry=None) -> dict:
    """Sonda APIs da fonte e grava o resultado no registro (api_url/status)."""
    from src.etl import acquisition as AC
    page = source.get("results_page", "")
    result = {"source_id": source.get("id"), "site": page, "ok": False,
              "api_url": "", "probed": [], "checked_at": now()}
    try:
        html = AC.fetch_url(page)
    except Exception as e:  # noqa: BLE001
        result["error"] = str(e)[:200]
        _record(registry, source, result)
        return result
    for url in candidate_api_urls(page, html):
        pr = probe_url(url)
        result["probed"].append(pr)
        if pr["ok"] and not result["api_url"]:
            result.update(ok=True, api_url=url, sample=pr.get("sample", ""))
    _record(registry, source, result)
    return result


def _record(registry, source, result: dict) -> None:
    if registry is None:
        return
    registry.update(source["id"],
                    api_url=result.get("api_url", ""),
                    api_status="OK" if result["ok"] else ("NONE" if "error" not in result else "ERROR"),
                    api_checked_at=result["checked_at"],
                    api_note=(result.get("sample") or result.get("error", ""))[:200])


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
