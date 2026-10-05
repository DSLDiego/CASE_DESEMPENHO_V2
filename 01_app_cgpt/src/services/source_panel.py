"""Monta o painel de gestao de fontes p/ apresentacao (web + GUI).

Colunas: site | documento | extensao | pasta no sistema | data do download.
Junta: CSV de downloads (real) + tabela `source` do SQLite (o que alimenta o painel).
"""
from __future__ import annotations
import csv
import urllib.parse
from pathlib import Path

EXTS = (".pdf", ".xls", ".xlsx", ".xlsm", ".csv", ".doc", ".docx", ".txt", ".html", ".htm")


def _host(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc or url
    except Exception:
        return url


def _doc_name(url: str, local_path: str) -> str:
    if local_path:
        return Path(local_path).name
    name = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
    return name or url


def _ext(name: str) -> str:
    suf = Path(name).suffix.lower()
    return suf if suf in EXTS else (suf or "—")


def build_documents_panel(repo, registry) -> list[dict]:
    rows: list[dict] = []
    seen_urls: set[str] = set()
    by_id = {s["id"]: s for s in registry.list()}

    def site_of(company: str, source_id: str, url: str) -> str:
        s = by_id.get(source_id or "")
        if s:
            return s.get("results_page", _host(url))
        return _host(url)

    # 1) downloads reais (CSV com datetime)
    if registry.csv_log.exists():
        with open(registry.csv_log, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                url = row.get("url", "")
                seen_urls.add(url)
                doc = _doc_name(url, row.get("local_path", ""))
                folder = str(Path(row["local_path"]).parent) if row.get("local_path") else "—"
                rows.append({"site": site_of(row.get("company", ""), row.get("source_id", ""), url),
                             "documento": doc, "extensao": _ext(doc),
                             "pasta": folder, "data_download": row.get("downloaded_at", ""),
                             "origem": row.get("status", "")})
    # 2) fontes que alimentam o painel (SQLite) ainda sem linha no CSV
    for s in repo.query("SELECT company_id, document, url, local_path, downloaded_at, is_demo FROM source"):
        url = s.get("url") or ""
        if url in seen_urls:
            continue
        doc = s.get("document") or _doc_name(url, s.get("local_path") or "")
        folder = str(Path(s["local_path"]).parent) if s.get("local_path") else "—"
        rows.append({"site": site_of(s.get("company_id", ""), "", url) or "base DEMO",
                     "documento": doc, "extensao": _ext(doc), "pasta": folder,
                     "data_download": s.get("downloaded_at") or ("DEMO (sem download)" if s.get("is_demo") else "—"),
                     "origem": "painel"})
    rows.sort(key=lambda r: r["data_download"] or "", reverse=True)
    return rows


def build_api_panel(registry) -> list[dict]:
    out = []
    for s in registry.list():
        out.append({"site": s.get("results_page", ""), "fonte": s["id"],
                    "api_url": s.get("api_url", "") or "—",
                    "status": s.get("api_status", "não verificada"),
                    "verificada_em": s.get("api_checked_at") or "—",
                    "amostra": s.get("api_note", "") or "—"})
    return out
