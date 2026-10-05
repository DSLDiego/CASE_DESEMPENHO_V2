"""Discovery (RI/sitemap/links) + Download concorrente com retry/backoff, ETag,
streaming, .part + rename atomico, SHA-256 e idempotencia por hash."""
from __future__ import annotations
import hashlib
import json
import re
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

AUTHORITY_SCORE = {"OFFICIAL": 40, "OFFICIAL_SUBDOMAIN": 25, "UNKNOWN": 5, "UNTRUSTED": -50}


@dataclass
class DocumentCandidate:
    company: str
    url: str
    title: str = ""
    period: str = ""
    document_type: str = "EARNINGS_RELEASE"
    score: int = 0
    authority: str = "UNKNOWN"
    discovered_by: str = "SEED"


def classify_authority(url: str, official_domains: list[str]) -> str:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return "UNKNOWN"
    for d in official_domains:
        d = d.lower()
        if host == d:
            return "OFFICIAL"
        if host.endswith("." + d):
            return "OFFICIAL_SUBDOMAIN"
    if not host:
        return "UNKNOWN"
    return "UNTRUSTED" if "." in host else "UNKNOWN"


def score_candidate(title: str, url: str, period: str, authority: str) -> int:
    s = AUTHORITY_SCORE.get(authority, 0)
    if period:
        s += 15
    low = f"{title} {url}".lower()
    if any(k in low for k in ("result", "earning", "quarterly", "release", "databook", "report", "resultado")):
        s += 15
    if any(k in low for k in ("q2", "2t", "2q", "segundo")):
        s += 5
    if url.lower().endswith(".pdf"):
        s += 5
    return max(0, min(100, s))


def discover_from_html(html: str, base_url: str, company: str,
                       official_domains: list[str]) -> list[DocumentCandidate]:
    links = re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
    titles = re.findall(r'<a[^>]*>(.*?)</a>', html, re.S | re.I)
    out: list[DocumentCandidate] = []
    seen: set[str] = set()
    for i, href in enumerate(links):
        url = urllib.parse.urljoin(base_url, href.strip())
        if url in seen or not url.startswith("http"):
            continue
        seen.add(url)
        low = url.lower()
        if not any(low.endswith(e) for e in (".pdf", ".xlsx", ".xls", ".xlsm", ".csv", ".doc", ".docx", ".html")) \
                and "result" not in low and "quarter" not in low:
            continue
        title = re.sub(r"<[^>]+>", "", titles[i] if i < len(titles) else "").strip()[:200]
        auth = classify_authority(url, official_domains)
        out.append(DocumentCandidate(company, url, title, "", "EARNINGS_RELEASE",
                                     score_candidate(title, url, "", auth), auth, "HTML_LINK"))
    return sorted(out, key=lambda c: -c.score)


def fetch_url(url: str, timeout: int = 30) -> str:
    import requests
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "BenchmarkPoC/1.0"})
    r.raise_for_status()
    return r.text


@dataclass
class DownloadResult:
    url: str
    local_path: str
    sha256: str
    size: int
    content_type: str
    etag: str
    last_modified: str
    from_cache: bool = False
    status: int = 200


def _manifest_path(raw_dir: Path) -> Path:
    return raw_dir / "_manifest.jsonl"


def _read_manifest(raw_dir: Path) -> dict[str, dict]:
    mp = _manifest_path(raw_dir)
    out: dict[str, dict] = {}
    if mp.exists():
        for line in mp.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                rec = json.loads(line)
                out[rec.get("url", "")] = rec
            except Exception:
                continue
    return out


def download_one(url: str, dest_dir: Path, retries: int = 4,
                 per_host_limiter=None) -> DownloadResult:
    import requests
    dest_dir.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest(dest_dir)
    prev = manifest.get(url, {})
    headers = {"User-Agent": "BenchmarkPoC/1.0"}
    if prev.get("etag"):
        headers["If-None-Match"] = prev["etag"]
    if prev.get("last_modified"):
        headers["If-Modified-Since"] = prev["last_modified"]
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            if per_host_limiter is not None:
                per_host_limiter.acquire(url)
            try:
                with requests.get(url, stream=True, timeout=30, headers=headers) as r:
                    if r.status_code == 304 and prev:
                        return DownloadResult(url, prev["local_path"], prev["sha256"],
                                              prev.get("size", 0), prev.get("content_type", ""),
                                              prev.get("etag", ""), prev.get("last_modified", ""),
                                              True, 304)
                    r.raise_for_status()
                    fname = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1] or "doc"
                    if "." not in fname:
                        ct = r.headers.get("Content-Type", "")
                        fname += ".pdf" if "pdf" in ct else ".html"
                    final = dest_dir / fname
                    tmp = final.with_suffix(final.suffix + ".part")
                    h = hashlib.sha256()
                    size = 0
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(1 << 16):
                            if not chunk:
                                continue
                            f.write(chunk)
                            h.update(chunk)
                            size += len(chunk)
                    tmp.replace(final)
                    rec = {"url": url, "local_path": str(final), "sha256": h.hexdigest(),
                           "size": size, "content_type": r.headers.get("Content-Type", ""),
                           "etag": r.headers.get("ETag", ""), "last_modified": r.headers.get("Last-Modified", ""),
                           "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                    with open(_manifest_path(dest_dir), "a", encoding="utf-8") as mf:
                        mf.write(json.dumps(rec) + "\n")
                    return DownloadResult(url, str(final), rec["sha256"], size,
                                          rec["content_type"], rec["etag"], rec["last_modified"], False,
                                          r.status_code)
            finally:
                if per_host_limiter is not None:
                    per_host_limiter.release(url)
        except Exception as e:  # noqa: BLE001 - retry intencional
            last_exc = e
            status = getattr(getattr(e, "response", None), "status_code", 0)
            if status in (404, 401, 403):
                break
            time.sleep(delay + 0.1 * attempt)
            delay *= 2
    raise RuntimeError(f"Download falhou {url}: {last_exc}")
