"""Mapeamento de fontes: pagina RI + sitemap, com e sem rede."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HTML = ('<a href="https://riSHELL.example.com/q2.pdf">Q2 2026 Results</a>'
        '<a href="https://riSHELL.example.com/xlsx">Databook</a>')
SITEMAP = ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           '<url><loc>https://riSHELL.example.com/q2.pdf</loc></url>'
           '<url><loc>https://riSHELL.example.com/home</loc></url></urlset>')


def _src():
    return {"id": "S1", "company": "SHELL", "results_page": "https://riSHELL.example.com/q",
            "domains": ["riSHELL.example.com"]}


def test_map_source_dedup_page_sitemap(monkeypatch):
    from src.etl import mapping as M
    def fake_fetch(url, timeout=30):
        return SITEMAP if url.endswith("sitemap.xml") else HTML
    monkeypatch.setattr(M.AC, "fetch_url", fake_fetch)
    out = M.map_source(_src())
    urls = [d["url"] for d in out["docs"]]
    assert urls.count("https://riSHELL.example.com/q2.pdf") == 1  # dedup pagina+sitemap
    assert out["docs"][0]["periodo"] == "2T2026"
    assert all(d["autoridade"] == "OFFICIAL" for d in out["docs"])


def test_map_source_offline_graceful(monkeypatch):
    from src.etl import mapping as M
    monkeypatch.setattr(M.AC, "fetch_url", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("dns")))
    out = M.map_source(_src())
    assert out["total"] == 0 and len(out["errors"]) >= 1


def test_save_artifacts(tmp_path, monkeypatch):
    from src.etl import mapping as M
    monkeypatch.setattr(M.AC, "fetch_url", lambda *a, **k: HTML if "sitemap" not in a[0] else (_ for _ in ()).throw(RuntimeError("x")))
    mp = {"mapped_at": "t", "sources": [M.map_source(_src())], "totals": {"S1": 2}}
    arts = M.save_artifacts(mp, tmp_path)
    assert Path(arts["json"]).exists() and Path(arts["csv"]).exists()
