"""Batch ETL ponta a ponta nos 3 modos (PROCESS/THREAD/SUBPROCESS), lotes 5 e 10."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.etl import batch as B


def _fixtures(tmp_path: Path) -> list[str]:
    files = []
    (tmp_path / "PETROBRAS_2T2026.txt").write_text("Revenue US$ 25.2 billion. Net income US$ 10.4 billion. Total employees 45,500.", encoding="utf-8")
    (tmp_path / "SHELL_2T2026.csv").write_text("label,value\nRevenue,86.3\nAdjusted EBITDA,20.7\n", encoding="utf-8")
    (tmp_path / "EQUINOR_2T2026.html").write_text("<html><body>Net income 4.84 billion. Total employees 22,400</body></html>", encoding="utf-8")
    return [str(tmp_path / f) for f in ("PETROBRAS_2T2026.txt", "SHELL_2T2026.csv", "EQUINOR_2T2026.html")]


def _run_all(files, mode, batch):
    tasks = [B.FileTask(p) for p in files]
    res = B.run_batch(tasks, mode=mode, batch_size=batch, scheduler="SJF", max_workers=4)
    assert len(res) == 3
    assert all(r.ok for r in res), [(r.path, r.error) for r in res]
    assert all(len(r.extractions) >= 1 for r in res)


def test_batch_thread(tmp_path):
    _run_all(_fixtures(tmp_path), "THREAD", 5)
    _run_all(_fixtures(tmp_path), "THREAD", 10)


def test_batch_process(tmp_path):
    _run_all(_fixtures(tmp_path), "PROCESS", 5)


def test_batch_subprocess(tmp_path):
    _run_all(_fixtures(tmp_path), "SUBPROCESS", 5)
