"""Mapeamento de fontes na internet: paginas de RI + sitemap.xml.

Para cada fonte: coleta links de documentos (pdf/planilhas/doc/txt/csv/html),
classifica autoridade, estima periodo e pontua. Gera JSON + CSV + MD.
Falha de rede vira registro de erro, nunca excecao.
"""
from __future__ import annotations
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from src.etl import acquisition as AC
from src.utils.period import resolve_period

BASE = Path(__file__).resolve().parents[2]

DOC_EXTS = (".pdf", ".xls", ".xlsx", ".xlsm", ".csv", ".doc", ".docx", ".txt")
KEYWORDS = ("result", "quarter", "earning", "report", "databook", "presentation",
            "resultado", "trimestre", "release", "financial")
SITEMAP_CAP = 120


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sitemap_docs(origin: str, timeout: int = 20) -> tuple[list[str], str]:
    """Retorna (urls candidatas do sitemap, erro ou '')."""
    try:
        xml = AC.fetch_url(origin.rstrip("/") + "/sitemap.xml", timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return [], f"sitemap: {e}"[:160]
    try:
        root = ET.fromstring(xml)
    except Exception:
        return [], "sitemap: xml invalido"
    locs = [el.text.strip() for el in root.iter() if el.tag.endswith("}loc") and el.text]
    out = [u for u in locs if u.lower().endswith(DOC_EXTS)
           or any(k in u.lower() for k in KEYWORDS)][:SITEMAP_CAP]
    return out, ""


def _doc_record(company: str, source_id: str, url: str, title: str,
                domains: list[str], via: str) -> dict:
    path = urllib.parse.urlparse(url).path
    ext = Path(path).suffix.lower() or "(pagina)"
    ctx = resolve_period(f"{title} {url}", "")
    auth = AC.classify_authority(url, domains)
    score = AC.score_candidate(title, url, ctx.label if ctx else "", auth)
    return {"company": company, "source_id": source_id, "title": title[:160] or "(sem titulo)",
            "url": url, "ext": ext, "periodo": ctx.label if ctx else "—",
            "score": score, "autoridade": auth, "via": via}


def map_source(source: dict) -> dict:
    """Mapeia UMA fonte: pagina de RI + sitemap."""
    company, sid = source["company"], source["id"]
    page = source.get("results_page", "")
    domains = source.get("domains", [])
    docs: dict[str, dict] = {}
    errors: list[str] = []
    checked = _now()
    try:
        html = AC.fetch_url(page)
        for c in AC.discover_from_html(html, page, company, domains):
            docs.setdefault(c.url, _doc_record(company, sid, c.url, c.title, domains, "pagina-RI"))
    except Exception as e:  # noqa: BLE001
        errors.append(f"pagina: {e}"[:160])
    origin = f"{urllib.parse.urlparse(page).scheme}://{urllib.parse.urlparse(page).netloc}"
    if origin and origin != "://":
        urls, err = sitemap_docs(origin)
        if err:
            errors.append(err)
        for u in urls:
            docs.setdefault(u, _doc_record(company, sid, u, "", domains, "sitemap"))
    items = sorted(docs.values(), key=lambda d: -d["score"])
    return {"source_id": sid, "company": company, "site": page,
            "checked_at": checked, "total": len(items), "docs": items, "errors": errors}


def run_mapping(registry, extras: list[dict] | None = None) -> dict:
    out = {"mapped_at": _now(), "sources": []}
    for s in registry.list(only_active=True):
        out["sources"].append(map_source(s))
    for s in extras or []:
        out["sources"].append(map_source(s))
    out["totals"] = {s["source_id"]: s["total"] for s in out["sources"]}
    return out


def save_artifacts(mapping: dict, base: Path | str = "data") -> dict[str, str]:
    import csv as _csv
    import json as _json
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    jp = base / "source_map.json"
    jp.write_text(_json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    cp = base / "source_map.csv"
    with open(cp, "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=["company", "source_id", "site", "title", "url",
                                           "ext", "periodo", "score", "autoridade", "via"])
        w.writeheader()
        for s in mapping["sources"]:
            for d in s["docs"]:
                w.writerow({"company": d["company"], "source_id": d["source_id"],
                            "site": s["site"], **{k: d[k] for k in
                            ("title", "url", "ext", "periodo", "score", "autoridade", "via")}})
    lines = ["# Mapa de fontes públicas (gerado)", "", f"_Mapeado em {mapping['mapped_at']}_", ""]
    for s in mapping["sources"]:
        lines += [f"## {s['company']} — {s['source_id']}",
                  f"Site: {s['site']} · documentos: **{s['total']}**", ""]
        if s["errors"]:
            lines += ["Erros: " + "; ".join(s["errors"]), ""]
        lines += ["| Documento | Ext | Período | Score | Autoridade | Via |",
                  "|---|---|---|---|---|---|"]
        for d in s["docs"][:30]:
            lines.append(f"| {d['title'][:60]} | {d['ext']} | {d['periodo']} | "
                         f"{d['score']} | {d['autoridade']} | {d['via']} |")
        lines += ["", f"[URL]({s['site']})", ""]
    md = BASE / "docs" / "mapa_fontes.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(jp), "csv": str(cp), "md": str(md)}


# Empresas de expansao (universo do case) — descoberta somente, sem ativar download
EXTRAS = [
    {"id": "BP_RI_MAP", "company": "BP", "name": "BP investors",
     "results_page": "https://www.bp.com/en/global/corporate/investors/results-and-reporting.html",
     "domains": ["bp.com"], "active": True},
    {"id": "CHEVRON_RI_MAP", "company": "CHEVRON", "name": "Chevron investors",
     "results_page": "https://www.chevron.com/investors",
     "domains": ["chevron.com"], "active": True},
    {"id": "EXXON_RI_MAP", "company": "EXXONMOBIL", "name": "ExxonMobil investors",
     "results_page": "https://corporate.exxonmobil.com/investors",
     "domains": ["exxonmobil.com"], "active": True},
]
