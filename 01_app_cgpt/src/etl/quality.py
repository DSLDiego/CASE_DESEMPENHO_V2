"""Normalizacao financeira + qualidade + reconciliacao."""
from __future__ import annotations
from dataclasses import dataclass
from src.models.entities import Extraction, QualityIssue

NORMALIZER_VERSION = "norm:v2"
FX_BRLUSD = 0.20  # taxa demonstrativa p/ comparabilidade; producao usa PTAX do periodo

THRESHOLDS = {"REVENUE": 0.30, "EBITDA_ADJ": 0.50, "NET_INCOME": 1.0,
              "NET_INCOME_ADJ": 1.0, "OCF": 0.60, "EMPLOYEES": 0.15}


@dataclass
class NormalizedObservation:
    extraction: Extraction
    value_reported: float | None  # na moeda original
    value_usd_m: float | None     # comparavel


def normalize(ext: Extraction, source_currency: str = "USD") -> NormalizedObservation:
    v = ext.value
    usd = None
    if v is not None:
        if ext.indicator_id == "EMPLOYEES":
            usd = v
        elif (source_currency or "USD").upper() == "BRL":
            usd = v * FX_BRLUSD
        else:
            usd = v
    return NormalizedObservation(ext, v, usd)


def check_completeness(found: set[str], expected: set[str], company: str, period: str) -> list[QualityIssue]:
    out = []
    for ind in sorted(expected - found):
        out.append(QualityIssue("COMPLETENESS", "WARNING",
                                f"{company} {period}: indicador {ind} ausente",
                                company, period, ind))
    return out


def check_invalid(exts: list[Extraction]) -> list[QualityIssue]:
    out = []
    for e in exts:
        if e.value is None:
            out.append(QualityIssue("REQUIRED_VALUE", "ERROR", "Valor nulo extraido",
                                    e.company_id, e.period_id, e.indicator_id))
        elif e.indicator_id == "EMPLOYEES" and e.value < 0:
            out.append(QualityIssue("NEGATIVE_HEADCOUNT", "ERROR", "Efetivo negativo",
                                    e.company_id, e.period_id, e.indicator_id, e.value))
    return out


def check_deviation(current: dict[str, float | None], previous: dict[str, float | None],
                    company: str, period: str) -> list[QualityIssue]:
    out = []
    for ind, val in current.items():
        prev = previous.get(ind)
        if val is None or prev in (None, 0):
            continue
        var = abs(val - prev) / abs(prev)
        thr = THRESHOLDS.get(ind, 0.5)
        if var > thr:
            out.append(QualityIssue("HISTORICAL_DEVIATION", "WARNING",
                                    f"{company} {period} {ind}: variacao {var:.1%} vs trimestre anterior (limite {thr:.0%})",
                                    company, period, ind, val, prev))
    return out


def check_source_change(old_value: float | None, new_value: float | None,
                        company: str, period: str, ind: str) -> QualityIssue | None:
    if old_value in (None, 0) or new_value is None:
        return None
    if abs(old_value - new_value) < 1e-9:
        return None
    pct = abs(new_value - old_value) / abs(old_value)
    return QualityIssue("SOURCE_CHANGE", "WARNING",
                        f"Valor anterior {old_value} substituido por {new_value} ({pct:.1%}). Revisar documento/origem.",
                        company, period, ind, new_value, old_value)


def reconcile(value_a: float | None, src_a: str, value_b: float | None, src_b: str,
              tol: float = 0.02) -> str:
    if value_a is None or value_b is None:
        return "MISSING"
    denom = max(abs(value_a), abs(value_b), 1e-9)
    return "RECONCILED" if abs(value_a - value_b) / denom <= tol else "RECONCILIATION_WARNING"
