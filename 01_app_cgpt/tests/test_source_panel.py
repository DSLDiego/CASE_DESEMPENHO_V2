"""Painel de fontes (1.1) + sonda de APIs JSON (1.2)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.source_registry import SourceRegistry


def _reg(tmp_path: Path) -> SourceRegistry:
    r = SourceRegistry(tmp_path / "reg.json", tmp_path / "dl.csv")
    r.add("S1", "SHELL", "RI Shell", "https://www.shell.com/investors/x", ["shell.com"])
    return r


def test_documents_panel_columns(tmp_path):
    from src.repositories.sqlite_repo import SQLiteRepository
    from src.services.source_panel import build_documents_panel
    r = _reg(tmp_path)
    r.log_download("SHELL", "S1", "RI Shell", "https://www.shell.com/f/q2.xlsx",
                   "/raw/SHELL/q2.xlsx", "aa", 10, "x", "OK", "OFFICIAL")
    repo = SQLiteRepository(tmp_path / "t.sqlite")
    repo.init_schema()
    docs = build_documents_panel(repo, r)
    real = [d for d in docs if d["documento"] == "q2.xlsx"][0]
    assert real["extensao"] == ".xlsx" and "SHELL" in real["pasta"]
    assert real["data_download"] and real["site"].startswith("https://")
    assert all({"site", "documento", "extensao", "pasta", "data_download"} <= set(d) for d in docs)


def test_api_candidates_from_html():
    from src.etl.api_probe import candidate_api_urls
    urls = candidate_api_urls("https://www.shell.com/investors/r.html",
                              '<script src="/data/info.json"></script>')
    assert urls[0].endswith(".model.json")
    assert any(u.endswith("info.json") for u in urls)


def test_probe_source_records_registry(monkeypatch, tmp_path):
    import requests
    from src.etl import api_probe as P
    r = _reg(tmp_path)

    class FakeResp:
        status_code = 200
        content = b'{"results": [], "meta": {}}'
        headers = {"Content-Type": "application/json"}

    monkeypatch.setattr("src.etl.acquisition.fetch_url", lambda url, timeout=30: '<a href="x">y</a>')
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp())
    out = P.probe_source(r.get("S1"), r)
    assert out["ok"] and out["api_url"].endswith(".model.json")
    assert r.get("S1")["api_status"] == "OK"


def test_probe_source_no_json(monkeypatch, tmp_path):
    import requests
    from src.etl import api_probe as P
    r = _reg(tmp_path)

    class FakeResp:
        status_code = 200
        content = b"<html>nao json</html>"
        headers = {"Content-Type": "text/html"}

    monkeypatch.setattr("src.etl.acquisition.fetch_url", lambda url, timeout=30: "")
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp())
    out = P.probe_source(r.get("S1"), r)
    assert not out["ok"] and r.get("S1")["api_status"] == "NONE"
