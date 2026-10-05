"""Subsistemas por formato: roteamento, validacao e analise (offline)."""
import sys
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.etl.formats import dispatch as D


def _pdf(p: Path) -> None:
    p.write_bytes(b"%PDF-1.7\n1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
                  b"2 0 obj<</Type /Pages /Count 2 /Kids[3 0 R 4 0 R]>>endobj\n"
                  b"3 0 obj<</Type /Page /Parent 2 0 R>>endobj\n"
                  b"4 0 obj<</Type /Page /Parent 2 0 R>>endobj\n"
                  b"BT /F1 12 Tf (Revenue 86.3 billion dollars total result) Tj ET\n" * 4)


def test_dispatch_routes_each_format():
    assert type(D.handler_for("https://x.com/a.pdf")).__name__ == "PdfHandler"
    assert type(D.handler_for("https://x.com/a.XLSX")).__name__ == "SheetHandler"
    assert type(D.handler_for("https://x.com/a.xls")).__name__ == "SheetHandler"
    assert type(D.handler_for("https://x.com/a.doc")).__name__ == "DocHandler"
    assert type(D.handler_for("https://x.com/a.txt")).__name__ == "TxtHandler"
    assert type(D.handler_for("https://x.com/a.xyz")).__name__ == "GenericHandler"


def test_pdf_analyze_pages_profile(tmp_path):
    from src.etl.formats.pdf_collector import PdfHandler
    _pdf(tmp_path / "a.pdf")
    meta = PdfHandler().analyze(tmp_path / "a.pdf")
    assert meta["pages_detected"] == 8 and meta["profile"] == "TEXT_PDF"  # fixture repete o bloco 4x


def test_sheet_doc_txt_analyze(tmp_path):
    import openpyxl
    from src.etl.formats.sheet_collector import SheetHandler
    from src.etl.formats.doc_collector import DocHandler
    from src.etl.formats.txt_collector import TxtHandler
    wb = openpyxl.Workbook()
    wb.active.title = "Results"
    wb.save(tmp_path / "b.xlsx")
    meta = SheetHandler().analyze(tmp_path / "b.xlsx")
    assert meta["sheets"] == ["Results"] and not meta["has_macro"]
    with zipfile.ZipFile(tmp_path / "c.docx", "w") as z:
        z.writestr("word/document.xml", "<w:doc><w:p><w:t>oi</w:t></w:p><w:tbl/></w:doc>")
    meta = DocHandler().analyze(tmp_path / "c.docx")
    assert meta["paragraphs"] == 1 and meta["tables"] == 1
    (tmp_path / "d.txt").write_text("linha1\nlinha2\n", encoding="latin1")
    meta = TxtHandler().analyze(tmp_path / "d.txt")
    assert meta["lines"] == 2 and meta["encoding"] in ("utf-8", "latin1")


def test_collect_writes_sidecar_and_logs(monkeypatch, tmp_path):
    from src.etl.acquisition import DownloadResult
    from src.etl import acquisition as AC
    from src.services.source_registry import SourceRegistry
    _pdf(tmp_path / "src.pdf")
    import shutil
    dest = tmp_path / "raw"
    dest.mkdir()
    monkeypatch.setattr(AC, "download_one",
                        lambda url, d, **k: DownloadResult(url, str(shutil.copy(tmp_path / "src.pdf", d / "a.pdf")),
                                                           "shax", 100, "application/pdf", "", "", False, 200))
    reg = SourceRegistry(tmp_path / "reg.json", tmp_path / "dl.csv")
    cf = D.collect_one("https://x.com/a.pdf", dest, reg, "S1", "S", "SHELL")
    assert (dest / "a.pdf.meta.json").exists()
    assert (tmp_path / "dl.csv").exists() and "a.pdf" in (tmp_path / "dl.csv").read_text()
    assert cf.meta["pages_detected"] == 8
