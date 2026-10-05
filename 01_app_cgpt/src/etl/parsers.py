"""Parsers por formato -> CanonicalDocument. Streaming + fallbacks silenciosos.

Formatos: PDF, XLS, XLSX, XLSM, CSV, DOC, DOCX, TXT, HTML.
Regra BigString: nunca carregar 2x; hash sobre os mesmos bytes do disco.
"""
from __future__ import annotations
import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from src.models.entities import CanonicalDocument


def _read_bytes_head(path: Path, n: int = 2_000_000) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


def parse_pdf(path: Path, doc_id: str, company: str, period: str) -> CanonicalDocument:
    text_parts: list[str] = []
    pages = 1
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(path))
        pages = len(reader.pages)
        for pg in reader.pages:
            try:
                text_parts.append(pg.extract_text() or "")
            except Exception:
                text_parts.append("")
    except Exception:
        try:  # fallback 1: descomprime streams FlateDecode (stdlib) e extrai (texto) Tj
            raw = _read_bytes_head(path)
            parts = [f"BT-stream fallback ({path.name})"]
            for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
                try:
                    import zlib
                    dec = zlib.decompress(m.group(1).strip())
                except Exception:
                    continue
                parts.extend(t.decode("latin1") for t in re.findall(rb"\((?:[^()\\]|\\.)*\)", dec))
                parts.extend(h.decode("latin1") for h in re.findall(rb"<([0-9A-Fa-f]{4,})>", dec))
                if len(parts) > 20000:
                    break
            text_parts.append("\n".join(parts[:20000]))
        except Exception:
            pass
        try:  # fallback 2: varre strings ASCII do binario
            raw = _read_bytes_head(path)
            ascii_runs = re.findall(rb"[\x20-\x7e]{6,}", raw)
            text_parts.append("\n".join(r.decode("ascii", "ignore") for r in ascii_runs[:5000]))
        except Exception:
            pass
    text = "\n".join(text_parts)
    profile = "SCANNED_PDF" if len(text.strip()) < 100 else ("HYBRID_PDF" if pages > 1 and len(text) < 2000 else "TEXT_PDF")
    return CanonicalDocument(doc_id, company, period, text=text, pages=pages, profile=profile, source_path=str(path))


def _parse_excel_xml(path: Path, doc_id: str, company: str, period: str) -> CanonicalDocument:
    """Le xlsx/xlsm via XML interno (sem depender de openpyxl se ausente)."""
    texts: list[str] = []
    tables: list = []
    try:
        z = zipfile.ZipFile(path)
        # shared strings
        shared: list[str] = []
        try:
            ss = z.read("xl/sharedStrings.xml")
            root = ET.fromstring(ss)
            for el in root.iter():
                if el.tag.endswith("}t") and el.text:
                    shared.append(el.text)
        except KeyError:
            pass
        for name in z.namelist():
            if name.startswith("xl/worksheets/sheet"):
                try:
                    data = z.read(name)
                    root = ET.fromstring(data)
                    rows: list[list[str]] = []
                    for row in root.iter():
                        if row.tag.endswith("}row"):
                            cells: list[str] = []
                            for c in row:
                                if not c.tag.endswith("}c"):
                                    continue
                                t = c.get("t")
                                v = ""
                                for v_el in c:
                                    if v_el.tag.endswith("}v") and v_el.text:
                                        v = v_el.text
                                if t == "s" and v.isdigit() and int(v) < len(shared):
                                    v = shared[int(v)]
                                cells.append(v)
                            if any(cells):
                                rows.append(cells)
                    if rows:
                        tables.append({"sheet": name, "rows": rows[:200]})
                        texts.append("\n".join(" | ".join(r) for r in rows[:200]))
                except Exception:
                    continue
    except Exception as e:
        texts.append(f"[excel-fallback] {e}")
    return CanonicalDocument(doc_id, company, period, text="\n".join(texts),
                             tables=tables, pages=max(len(tables), 1), profile="SPREADSHEET",
                             source_path=str(path))


def parse_excel(path: Path, doc_id: str, company: str, period: str) -> CanonicalDocument:
    suf = path.suffix.lower()
    if suf in (".xlsx", ".xlsm"):
        # tenta openpyxl (melhor p/ valores calculados), senao XML interno
        try:
            import openpyxl  # type: ignore
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            texts: list[str] = []
            tables: list = []
            for ws in wb.worksheets:
                rows = []
                for row in ws.iter_rows(values_only=True):
                    vals = [(str(v) if v is not None else "") for v in row]
                    if any(vals):
                        rows.append(vals)
                    if len(rows) >= 200:
                        break
                if rows:
                    tables.append({"sheet": ws.title, "rows": rows})
                    texts.append(f"[{ws.title}]\n" + "\n".join(" | ".join(r) for r in rows))
            wb.close()
            return CanonicalDocument(doc_id, company, period, text="\n".join(texts),
                                     tables=tables, pages=max(len(tables), 1),
                                     profile="SPREADSHEET", source_path=str(path))
        except Exception:
            return _parse_excel_xml(path, doc_id, company, period)
    # .xls legado: tenta xlrd, senao varredura textual
    try:
        import xlrd  # type: ignore
        wb = xlrd.open_workbook(str(path))
        texts, tables = [], []
        for si in range(wb.nsheets):
            sh = wb.sheet_by_index(si)
            rows = [[str(sh.cell_value(r, c)) for c in range(sh.ncols)] for r in range(min(sh.nrows, 200))]
            tables.append({"sheet": sh.name, "rows": rows})
            texts.append(f"[{sh.name}]\n" + "\n".join(" | ".join(r) for r in rows if any(r)))
        return CanonicalDocument(doc_id, company, period, text="\n".join(texts),
                                 tables=tables, pages=max(len(tables), 1),
                                 profile="SPREADSHEET", source_path=str(path))
    except Exception:
        raw = _read_bytes_head(path)
        runs = re.findall(rb"[\x20-\x7e]{5,}", raw)
        text = "\n".join(r.decode("ascii", "ignore") for r in runs[:3000])
        return CanonicalDocument(doc_id, company, period, text=text, profile="LEGACY_XLS",
                                 source_path=str(path))


def parse_csv(path: Path, doc_id: str, company: str, period: str) -> CanonicalDocument:
    rows: list[list[str]] = []
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            for i, row in enumerate(csv.reader(f)):
                rows.append(row)
                if i >= 2000:
                    break
    except Exception:
        pass
    text = "\n".join(" | ".join(r) for r in rows[:200])
    return CanonicalDocument(doc_id, company, period, text=text,
                             tables=[{"sheet": "csv", "rows": rows[:200]}],
                             pages=1, profile="CSV", source_path=str(path))


def parse_docx(path: Path, doc_id: str, company: str, period: str) -> CanonicalDocument:
    texts: list[str] = []
    try:
        z = zipfile.ZipFile(path)
        xml = z.read("word/document.xml")
        root = ET.fromstring(xml)
        for el in root.iter():
            if el.tag.endswith("}t") and el.text:
                texts.append(el.text)
    except Exception as e:
        texts.append(f"[docx-fallback] {e}")
    return CanonicalDocument(doc_id, company, period, text="\n".join(texts),
                             pages=1, profile="DOCX", source_path=str(path))


def parse_doc(path: Path, doc_id: str, company: str, period: str) -> CanonicalDocument:
    # .doc legado: tenta antiword/libreoffice via subprocess isolado; senao varredura
    import subprocess, shutil
    text = ""
    try:
        if shutil.which("antiword"):
            out = subprocess.run(["antiword", str(path)], capture_output=True, timeout=30)
            if out.returncode == 0:
                text = out.stdout.decode("utf-8", "ignore")
    except Exception:
        pass
    if not text:
        try:
            so = shutil.which("soffice") or shutil.which("libreoffice")
            if so:
                import tempfile, os
                with tempfile.TemporaryDirectory() as td:
                    subprocess.run([so, "--headless", "--convert-to", "txt:Text (encoded):UTF8",
                                    str(path), "--outdir", td], capture_output=True, timeout=60)
                    outs = list(Path(td).glob("*.txt"))
                    if outs:
                        text = outs[0].read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass
    if not text:
        raw = _read_bytes_head(path)
        runs = re.findall(rb"[\x20-\x7e]{5,}", raw)
        text = "\n".join(r.decode("ascii", "ignore") for r in runs[:3000])
    return CanonicalDocument(doc_id, company, period, text=text, profile="LEGACY_DOC",
                             source_path=str(path))


def parse_txt(path: Path, doc_id: str, company: str, period: str) -> CanonicalDocument:
    text = ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            parts = []
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                parts.append(chunk)
                if sum(len(p) for p in parts) > 5_000_000:
                    break
            text = "".join(parts)
    except Exception:
        pass
    return CanonicalDocument(doc_id, company, period, text=text, profile="TXT",
                             source_path=str(path))


def parse_html(path: Path, doc_id: str, company: str, period: str) -> CanonicalDocument:
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        raw = ""
    try:
        from html.parser import HTMLParser

        class _P(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts: list[str] = []
            def handle_data(self, data):
                if data.strip():
                    self.parts.append(data.strip())
        p = _P()
        p.feed(raw[:2_000_000])
        text = "\n".join(p.parts)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", raw)
    tables = []
    for m in re.finditer(r"<table.*?>(.*?)</table>", raw, re.S | re.I):
        cells = re.findall(r"<t[dh].*?>(.*?)</t[dh]>", m.group(1), re.S | re.I)
        clean = [re.sub(r"<[^>]+>", "", c).strip() for c in cells][:100]
        if clean:
            tables.append({"sheet": "html", "rows": [clean]})
    return CanonicalDocument(doc_id, company, period, text=text[:500_000],
                             tables=tables, pages=1, profile="HTML", source_path=str(path))


def parse_file(path: str | Path, company: str = "", period: str = "") -> CanonicalDocument:
    p = Path(path)
    doc_id = p.stem
    suf = p.suffix.lower()
    if suf == ".pdf":
        return parse_pdf(p, doc_id, company, period)
    if suf in (".xlsx", ".xlsm", ".xls"):
        return parse_excel(p, doc_id, company, period)
    if suf == ".csv":
        return parse_csv(p, doc_id, company, period)
    if suf == ".docx":
        return parse_docx(p, doc_id, company, period)
    if suf == ".doc":
        return parse_doc(p, doc_id, company, period)
    if suf in (".txt", ".log", ".md"):
        return parse_txt(p, doc_id, company, period)
    if suf in (".html", ".htm", ".xhtml"):
        return parse_html(p, doc_id, company, period)
    # fallback generico: tenta texto
    return parse_txt(p, doc_id, company, period)


SUPPORTED = {".pdf", ".xls", ".xlsx", ".xlsm", ".csv", ".doc", ".docx", ".txt", ".html", ".htm"}
