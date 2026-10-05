"""Worker parse_txt: txt/csv-texto/docx -> extracoes via regex + De-Para."""
from __future__ import annotations

import re
from pathlib import Path

from models.depara import resolve
from workers.parse_tab import RawExtraction, norm_period, to_number

LINE_PAT = re.compile(r"^(.{4,70}?)\s*[:;|]\s*\(?\$?\s?\d[\d.,\s]*\)?\s*$")


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        try:
            import docx
            doc = docx.Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return ""
    with open(path, encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def parse_txt(path: Path) -> list[RawExtraction]:
    text = read_text(path)
    if not text.strip():
        return []
    periodo = None
    for cand in re.findall(r"[1-4]T\d{2}|Q[1-4]\s*20\d{2}|20\d{2}Q[1-4]|20\d{2}S[12]", text):
        periodo, _ = norm_period(cand)
        if periodo:
            break
    if not periodo:
        return []
    out: list[RawExtraction] = []
    for line in text.splitlines():
        m = LINE_PAT.match(line.strip())
        if not m:
            continue
        canon, _, _ = resolve(m.group(1))
        if not canon:
            continue
        num = to_number(line.rsplit(":", 1)[-1].rsplit(";", 1)[-1])
        if num is None:
            continue
        out.append(RawExtraction(canon, periodo, round(num, 4), "USD bi", 0.60,
                                 f"{path.name}#txt", {"rotulo_origem": m.group(1).strip()}))
    return out
