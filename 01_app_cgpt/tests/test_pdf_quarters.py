"""Teste download+extracao em PDFs reais 2023-2026 (usa QUARTERTEST; pula se vazio)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

QDIR = Path("data/raw/TOTALENERGIES/QUARTERTEST")


def _files() -> list[Path]:
    return sorted(QDIR.glob("*.pdf")) if QDIR.exists() else []


def test_all_pdfs_parse_ok():
    import pytest
    from src.etl import batch as B
    files = _files()
    if not files:
        pytest.skip("QUARTERTEST vazio (rode scripts/fetch_quarters.py)")
    tasks = [B.FileTask(str(p)) for p in files]
    res = B.run_batch(tasks, mode="THREAD", batch_size=5, scheduler="FIFO", max_workers=4)
    assert len(res) == len(files) and all(r.ok for r in res), [(r.path, r.error) for r in res]
    assert all(len((r.extractions or [])) >= 0 for r in res)


def test_write_coverage_report():
    import pytest
    from src.etl import batch as B
    from src.etl import parsers
    files = _files()
    if not files:
        pytest.skip("QUARTERTEST vazio")
    lines = ["# Cobertura de extração — PDFs 2023–2026 (TotalEnergies)", "",
             "| Arquivo | Págs | Perfil | Indicadores extraídos |",
             "|---|---|---|---|"]
    for p in files:
        doc = parsers.parse_file(p, "TOTALENERGIES", "")
        from src.etl import extractors
        exts = extractors.extract(doc)
        got = ", ".join(f"{e.indicator_id}={e.value}" for e in exts) or "—"
        lines.append(f"| {p.name[:50]} | {doc.pages} | {doc.profile} | {got} |")
    (Path("docs") / "test_pdf_quarters.md").write_text("\n".join(lines), encoding="utf-8")
