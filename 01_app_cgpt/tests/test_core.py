"""Nucleo: periodo, scheduler, parsers/extractors, repo demo."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.period import resolve_period
from src.etl.scheduler import make_jobs, order_jobs
from src.etl import parsers, extractors
from src.models.entities import CanonicalDocument


def test_period_resolver():
    assert resolve_period("Results 2Q26", "").label == "2T2026"
    assert resolve_period("2T2026 release", "").year == 2026
    assert resolve_period("Six months ended June 30, 2026", "").is_ytd


def test_schedulers_cover_all():
    jobs = make_jobs([f"f{i}.pdf" for i in range(6)], {f"f{i}.pdf": 1000 * (i + 1) for i in range(6)})
    for algo in ["FIFO", "FILO", "SJF", "SRTF", "RR", "PRIORITY", "MLQ", "MLFQ", "HRRN", "FAIR-SHARE"]:
        ordered = order_jobs(jobs, algo)
        assert len(ordered) == 6, algo


def test_extract_revenue_and_employees():
    doc = CanonicalDocument("d", "SHELL", "2T2026",
                            text="Revenue was US$ 86.3 billion. Total employees 101,000.")
    exts = {e.indicator_id: e for e in extractors.extract(doc)}
    assert abs(exts["REVENUE"].value - 86300) < 1
    assert exts["EMPLOYEES"].value == 101000


def test_parse_all_formats(tmp_path):
    (tmp_path / "a.txt").write_text("Revenue US$ 10 billion", encoding="utf-8")
    (tmp_path / "b.csv").write_text("label,value\nRevenue,86.3\n", encoding="utf-8")
    (tmp_path / "c.html").write_text("<html><body>Revenue 86.3</body></html>", encoding="utf-8")
    (tmp_path / "d.docx").write_bytes(b"PK fake")  # fallback nao pode quebrar
    for f in ["a.txt", "b.csv", "c.html", "d.docx"]:
        doc = parsers.parse_file(tmp_path / f, "SHELL", "2T2026")
        assert isinstance(doc.text, str)
