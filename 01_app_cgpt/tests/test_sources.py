"""Subsistema de fontes: CRUD, novidades, log anti-repeticao."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.source_registry import SourceRegistry


def _reg(tmp_path: Path) -> SourceRegistry:
    return SourceRegistry(tmp_path / "reg.json", tmp_path / "dl.csv")


def test_crud_roundtrip(tmp_path):
    r = _reg(tmp_path)
    r.add("TST_RI", "PETROBRAS", "Teste", "https://exemplo.com/ri", ["exemplo.com"])
    assert r.get("TST_RI")["company"] == "PETROBRAS"
    r.update("TST_RI", results_page="https://exemplo.com/novo")
    assert r.get("TST_RI")["results_page"].endswith("/novo")
    r.set_active("TST_RI", False)
    assert r.list(only_active=True) == []
    r.set_active("TST_RI", True)
    assert r.export_csv(tmp_path / "reg.csv") == 1
    r.remove("TST_RI")
    assert r.get("TST_RI") is None


def test_download_log_avoids_redownload(tmp_path):
    r = _reg(tmp_path)
    assert r.known_urls() == set()
    r.log_download("SHELL", "SHELL_RI", "RI Shell", "https://x.com/a.pdf",
                   "/raw/a.pdf", "abc123", 100, "application/pdf", "OK", "OFFICIAL")
    assert "https://x.com/a.pdf" in r.known_urls()


def test_check_new_separates_known(monkeypatch, tmp_path):
    from src.etl import source_check as SC
    r = _reg(tmp_path)
    r.add("S1", "SHELL", "S", "https://riSHELL.example.com", ["riSHELL.example.com"])
    r.log_download("SHELL", "S1", "S", "https://riSHELL.example.com/old.pdf", status="OK")
    html = ('<a href="https://riSHELL.example.com/old.pdf">Q2 2026 Results</a>'
            '<a href="https://riSHELL.example.com/new.pdf">Q3 2026 Results</a>')
    monkeypatch.setattr(SC.AC, "fetch_url", lambda url, timeout=30: html)
    rep = SC.check_source(r.get("S1"), r)
    assert rep["ok"] and rep["known"] == 1
    assert len(rep["new"]) == 1 and rep["new"][0]["url"].endswith("new.pdf")
