"""Extratores: hierarquia tabela-estruturada > especifico > secao > semantico > regex.
Cada extracao carrega evidencia + confidence (review se < 0.70).
"""
from __future__ import annotations
import re
from src.models.entities import CanonicalDocument, Extraction

EXTRACTOR_VERSION = "heuristic:v3"

# valor + escala: "20.7 billion", "US$ 4.8 bn", "R$ 52,4 bilhões", "103,000"
_NUM = r"(?P<num>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
_SCALE = r"(?P<scale>billions?|bilh[õo]es|bn|millions?|milh[õo]es|mm|m\b|thousands?|k\b)?"

_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "REVENUE": [(r"reven(?:ue|ue)s?|receita\s*(?:l[ií]quida|operacional)?|sales", 0.8)],
    "EBITDA_ADJ": [(r"adjusted\s+ebitda|ebitda\s+(?:ajustad|adjusted)|ebitda", 0.75)],
    "NET_INCOME": [(r"net\s+income(?:\s+attributable)?|lucro\s+l[ií]quido|net\s+earnings", 0.8)],
    "NET_INCOME_ADJ": [(r"adjusted\s+(?:net\s+income|earnings)|lucro\s+l[ií]quido\s+ajustado", 0.85)],
    "OCF": [(r"(?:operating\s+cash\s+flow|cash\s+flow\s+from\s+operations|fluxo\s+de\s+caixa\s+operacional|\bOCF\b)", 0.8)],
    "EMPLOYEES": [(r"total\s+(?:de\s+)?efetivo|total\s+employees|headcount|workforce|n[úu]mero\s+de\s+empregados|employees", 0.8)],
}

_SCALE_MULT = {"billion": 1e9, "billions": 1e9, "bn": 1e9, "bilhões": 1e9, "bilhoes": 1e9,
               "million": 1e6, "millions": 1e6, "mm": 1e6, "milhões": 1e6, "milhoes": 1e6,
               "m": 1e6, "thousand": 1e3, "thousands": 1e3, "k": 1e3}


def _to_float(num: str) -> float | None:
    s = num.strip()
    # 1.234,56 (BR) vs 1,234.56 (US)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".") if re.search(r",\d{2}$", s) else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _extract_from_tables(doc: CanonicalDocument) -> list[Extraction]:
    out: list[Extraction] = []
    for tab in doc.tables or []:
        rows = tab.get("rows", [])
        if not rows:
            continue
        header = [str(c).lower() for c in rows[0]]
        for ri, row in enumerate(rows[1:], start=1):
            label = " ".join(str(c) for c in row[:3]).lower()
            for ind, pats in _PATTERNS.items():
                for pat, _ in pats:
                    if re.search(pat, label, re.I):
                        for ci, cell in enumerate(row):
                            m = re.match(rf"^\s*\$?\s*{_NUM}\s*{_SCALE}", str(cell), re.I)
                            if m:
                                val = _to_float(m.group("num"))
                                if val is None:
                                    continue
                                scale_raw = (m.group("scale") or "").lower()
                                mult = _SCALE_MULT.get(scale_raw, 1.0)
                                out.append(Extraction(doc.company_id, doc.period_id, ind,
                                                      val * mult / 1e6, "USD", "USD_M" if ind != "EMPLOYEES" else "HEADCOUNT",
                                                      1.0 if ind != "EMPLOYEES" else 0.95,
                                                      f"tabela {tab.get('sheet')} linha {ri}: {' | '.join(map(str,row))}"[:300],
                                                      None, tab.get("sheet"), "TABLE"))
                                break
    return out


def _extract_from_text(doc: CanonicalDocument) -> list[Extraction]:
    out: list[Extraction] = []
    text = doc.text or ""
    for ind, pats in _PATTERNS.items():
        for pat, base_conf in pats:
            rx = re.compile(rf"(?:{pat})\D{{0,120}}?(?:US\$|R\$|\$)?\s*{_NUM}\s*{_SCALE}", re.I)
            for m in list(rx.finditer(text))[:5]:
                val = _to_float(m.group("num"))
                if val is None:
                    continue
                scale_raw = (m.group("scale") or "").lower()
                mult = _SCALE_MULT.get(scale_raw, 1.0)
                # headcount nao tem escala monetaria
                if ind == "EMPLOYEES":
                    value = val
                    unit, conf = "HEADCOUNT", 0.8
                else:
                    value = val * mult / 1e6 if mult > 1 else val
                    unit, conf = "USD_M", 0.6
                    if mult > 1:
                        conf = 0.8
                start = max(0, m.start() - 80)
                out.append(Extraction(doc.company_id, doc.period_id, ind, value, "USD", unit,
                                      conf, text[start:m.end() + 40].strip()[:300],
                                      None, None, "REGEX"))
                break
    return out


def extract(doc: CanonicalDocument) -> list[Extraction]:
    """1) tabelas 2) texto/regex fallback. Retorna melhor por indicador."""
    cands = _extract_from_tables(doc) + _extract_from_text(doc)
    best: dict[str, Extraction] = {}
    for e in cands:
        if e.value is None:
            continue
        cur = best.get(e.indicator_id)
        if cur is None or e.confidence > cur.confidence:
            best[e.indicator_id] = e
    for e in best.values():
        e.method = f"{e.method}+{EXTRACTOR_VERSION}"
    return list(best.values())


def needs_review(extractions: list[Extraction]) -> list[Extraction]:
    return [e for e in extractions if e.confidence < 0.70]
