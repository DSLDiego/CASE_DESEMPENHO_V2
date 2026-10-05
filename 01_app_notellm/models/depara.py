"""Model: dicionario De-Para (rubrica origem -> indicador canonico).

Normalizacao: remove acentos/caixa para casar PT/EN e variacoes entre RIs.
Cada entrada: (padrao_regex, canonico, demonstrativo, fator).
"""
from __future__ import annotations

import re
import unicodedata

RULES: list[tuple[str, str, str, float]] = [
    (r"receita.*venda|sales.*revenu|revenues?\s+from\s+sales|total.*revenu|^revenues?$|receita.*liquida|receita operacional", "RECEITA_LIQUIDA", "DRE", 1.0),
    (r"lucro bruto|gross profit|gross margin", "LUCRO_BRUTO", "DRE", 1.0),
    (r"despesa.*operacional|despesas operacionais|operating expense|\bsg\s?&?\s?a\b|selling.*general.*admin", "DESPESA_OPERACIONAL", "DRE", 1.0),
    (r"ebitda ajustado|adjusted ebitda|ebitda", "EBITDA_AJUSTADO", "DRE", 1.0),
    (r"lucro liquido|net income|adjusted.*net income|lucro.*acionista|net earnings|lucro do periodo|income.{0,12}attributable|profit.{0,12}attributable|lucro atribuivel|resultado atribuido", "LUCRO_LIQUIDO", "DRE", 1.0),
    (r"fluxo de caixa operacional|cash flow from operat|operating cash flow|net cash provided.*operat|cash flows? provided by operating activit|fco\b", "FCO", "DFC", 1.0),
    (r"fluxo de caixa livre|free cash flow|fcl\b", "FCL", "DFC", 1.0),
    (r"divida liquida|net debt", "DIVIDA_LIQUIDA", "BP", 1.0),
    (r"divida bruta|gross debt|total debt", "DIVIDA_BRUTA", "BP", 1.0),
    (r"^capex$|capital expenditure|^investimentos?$|net investments?|^total capex$", "CAPEX", "DFC", 1.0),
    (r"total.*efetivo|efetivo.*total|headcount|total employees|number of employees|workforce", "EFETIVO_TOTAL", "OPER", 1.0),
    (r"producao.*m?boed|total production|producao total", "PRODUCAO_BOED", "OPER", 1.0),
    (r"utiliza.*refin|refin.*utili|fator.*utili", "FUT_REFINO", "OPER", 1.0),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), c, d, f) for p, c, d, f in RULES]


def normalize(text: str) -> str:
    ascii_txt = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", ascii_txt.strip().lower())


def resolve(label: str) -> tuple[str | None, str, float]:
    """Resolve um rotulo de origem -> (canonico|None, demonstrativo, fator)."""
    norm = normalize(label)
    for pattern, canon, demo, fator in _COMPILED:
        if pattern.search(norm):
            return canon, demo, fator
    return None, "DRE", 1.0


def seed_rows(empresa: str = "*") -> list[tuple[str, str, str, str, float]]:
    """Linhas de seed ilustrativas por empresa (o ETL usa `resolve` dinamico)."""
    rows = []
    exemplos = {
        "RECEITA_LIQUIDA": ["Receita de vendas", "Sales and other operating revenues"],
        "EBITDA_AJUSTADO": ["EBITDA ajustado", "Adjusted EBITDA"],
        "LUCRO_LIQUIDO": ["Lucro liquido - Acionistas", "Net income attributable"],
        "FCO": ["Fluxo de caixa operacional", "Cash flow from operating activities"],
        "DIVIDA_LIQUIDA": ["Divida liquida", "Net debt"],
        "EFETIVO_TOTAL": ["Total de efetivo", "Total employees"],
    }
    for canon, labels in exemplos.items():
        for lab in labels:
            rows.append((empresa, lab, canon, "DRE", 1.0))
    return rows
