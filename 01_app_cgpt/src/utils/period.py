"""Resolucao robusta de periodo PT-BR/EN (Q/T, datas, YTD). SKILL bigstring: streaming."""
from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PeriodContext:
    year: int
    quarter: int
    label: str
    report_type: str = "QUARTER"
    is_ytd: bool = False


_Q_PATTERNS = [
    re.compile(r"([1-4])\s?[TQ]\s?(\d{2,4})", re.I),          # 2T2026, 2Q26
    re.compile(r"[TQ]\s?([1-4])\s?[/\-]?\s?(\d{2,4})", re.I),  # T2/2026 Q2 2026
    re.compile(r"(\d{4})\s*[-/]?\s*[TQ]\s?([1-4])", re.I),     # 2026 Q2
    re.compile(r"([1-4])[oOaA]?\s*trimestre\s*de?\s*(\d{4})", re.I),
    re.compile(r"(first|second|third|fourth)\s+quarter\s+(\d{4})", re.I),
]

_YTD = re.compile(r"(six months|first half|1S|YTD|semestre|acumulado)", re.I)


def _norm_year(y: str) -> int:
    y = y.strip()
    if len(y) == 2:
        v = int(y)
        return 2000 + v if v < 60 else 1900 + v
    return int(y)


def resolve_period(text: str, hint: str = "") -> PeriodContext | None:
    blob = f"{hint} {text[:2000]}"
    is_ytd = bool(_YTD.search(blob))
    for rx in _Q_PATTERNS:
        m = rx.search(blob)
        if not m:
            continue
        a, b = m.group(1), m.group(2)
        try:
            if a.isdigit() and len(a) == 1 and len(b) >= 2:
                q, y = int(a), _norm_year(b)
            elif b.isdigit() and len(b) == 1:
                y, q = _norm_year(a), int(b)
            else:
                continue
            if 1 <= q <= 4 and 1990 <= y <= 2100:
                return PeriodContext(y, q, f"{q}T{y}",
                                     "YTD" if is_ytd else "QUARTER", is_ytd)
        except ValueError:
            continue
    m = re.search(r"\b(1T|2T|3T|4T)\s?(\d{4})\b", hint, re.I)
    if m:
        q = int(m.group(1)[0])
        return PeriodContext(int(m.group(2)), q, f"{q}T{m.group(2)}")
    # Fallback YTD: "six months ended June 30, 2026" -> Q2 YTD (mes -> trimestre)
    if is_ytd:
        year_m = re.search(r"\b(19|20)\d{2}\b", blob)
        if year_m:
            y = int(year_m.group(0))
            month_m = re.search(
                r"(january|february|march|april|may|june|july|august|september|october|november|december"
                r"|janeiro|fevereiro|marco|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)",
                blob, re.I)
            if month_m:
                mo = month_m.group(1).lower()
                order = ["january", "february", "march", "april", "may", "june", "july",
                         "august", "september", "october", "november", "december",
                         "janeiro", "fevereiro", "marco", "março", "abril", "maio", "junho",
                         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
                try:
                    idx = [o for o in order].index(mo) % 12
                    q = idx // 3 + 1
                except ValueError:
                    q = 2
            else:
                q = 2
            if 1990 <= y <= 2100:
                return PeriodContext(y, q, f"{q}T{y}", "YTD", True)
    return None


def period_id(year: int, quarter: int) -> str:
    return f"{quarter}T{year}"
