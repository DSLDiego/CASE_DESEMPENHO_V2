"""Worker parse_tab: planilhas (xlsx/xlsm/xls/csv) -> extracoes canonicas.

Cobre layouts heterogeneos das RIs:
- rotulo na 1a..3a coluna (Shell/Chevron usam col B);
- cabecalhos "Q2 2026", "2T26", "2026Q2", "1Q" (com ano no contexto), "at 6/30";
- semestrais "1H26/1S26" (mapeados p/ S1, filtrados depois pelos alvos);
- colunas de variacao (vs/X/%) e linhas unitarias (per share, $/bbl) ignoradas;
- deteccao de moeda (BRL) e escala (milhoes vs bilhoes vs dolares cheios).
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from models.depara import normalize, resolve

PERIOD_PATTERNS = [
    (re.compile(r"([1-4])T(\d{2})\b"), lambda m: (f"20{m.group(2)}Q{m.group(1)}", True)),
    (re.compile(r"Q([1-4])\s*20(\d{2})", re.IGNORECASE), lambda m: (f"20{m.group(2)}Q{m.group(1)}", True)),
    (re.compile(r"([1-4])Q(\d{2})\b", re.IGNORECASE), lambda m: (f"20{m.group(2)}Q{m.group(1)}", True)),
    (re.compile(r"\b(20\d{2})\s*[-/]?\s*Q([1-4])"), lambda m: (f"{m.group(1)}Q{m.group(2)}", True)),
    (re.compile(r"\b(20\d{2})Q([1-4])"), lambda m: (f"{m.group(1)}Q{m.group(2)}", True)),
    (re.compile(r"([12])[HS](2\d)\b", re.IGNORECASE), lambda m: (f"20{m.group(2)}S{m.group(1)}", True)),
    (re.compile(r"\b(20\d{2})\s*[HS]([12])"), lambda m: (f"{m.group(1)}S{m.group(2)}", True)),
    # trimestres nus (ano vem do contexto): "1Q".."4Q", "Q1".."Q4"
    (re.compile(r"^([1-4])Q$", re.IGNORECASE), lambda m: (f"Q{m.group(1)}", False)),
    (re.compile(r"^Q([1-4])$", re.IGNORECASE), lambda m: (f"Q{m.group(1)}", False)),
    # balanco "at 6/30" / datas "06/30/2026"
    (re.compile(r"at\s*(3/31|6/30|9/30|12/31)", re.IGNORECASE),
     lambda m: ({"3/31": "Q1", "6/30": "Q2", "9/30": "Q3", "12/31": "Q4"}[m.group(1)], False)),
    (re.compile(r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/(20\d{2})\b"),
     lambda m: (f"{m.group(3)}Q{(int(m.group(1)) - 1) // 3 + 1}", True)),
]

YEAR_CELL = re.compile(r"\b(20\d{2})\b")
BARE_YEAR = re.compile(r"^\s*(20\d{2})\s*$")
SKIP_COL = re.compile(r"varia|vs\.?|variation|%|p\.p|\(x\)|per share|por a[cç][aã]o|\$/|margin|guidance|target", re.IGNORECASE)
SKIP_ROW = re.compile(r"per share|per ads|por a[cç][aã]o|\$/bbl|/bbl|/mbtu|margin|ratio|gearing|roce|yield|dividend.*share|\beps\b|variation|back to index|click|contents|attach|per boe|unit cost|contribution of|of which|equity affiliate|after taxes paid|before capital distribution|non.?controlling|minority interest|participa[cç][aã]o minorit[aá]ria|non.?contr|adjusting items|identified items|special items|one-off|impairment|joint venture|equity securit|investing activit", re.IGNORECASE)
SCALE_MILLIONS = re.compile(r"milh|million|000\b|US\$ m|\$ million", re.IGNORECASE)
SCALE_BILLIONS = re.compile(r"bilh|billion|\(B\$\)|in billions", re.IGNORECASE)
BRL_HINT = re.compile(r"R\$|reais|BRL|\(R\$", re.IGNORECASE)


@dataclass
class RawExtraction:
    rubrica: str
    periodo: str
    valor: float
    unidade: str = "USD bi"
    confianca: float = 1.0
    origem: str = ""
    moeda_origem: str = "USD"
    extras: dict = field(default_factory=dict)


def norm_period(cell: object) -> tuple[str | None, bool]:
    """Retorna (periodo_ou_Qn, tem_ano)."""
    if cell is None:
        return None, False
    text = str(cell).strip()
    if SKIP_COL.search(text):
        return None, False
    for pattern, fmt in PERIOD_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                return fmt(m)
            except (IndexError, KeyError):
                continue
    return None, False


def year_context(rows: list[list], header_idx: int, col: int) -> str | None:
    header = rows[header_idx]
    for c in range(col + 1, min(col + 9, len(header))):  # ano a direita (ex.: BP: Q1..Q4 2022)
        m = BARE_YEAR.match(str(header[c] or ""))
        if m:
            return m.group(1)
    for i in range(header_idx - 1, max(-1, header_idx - 5), -1):
        for c in (col - 1, col, col + 1):
            if 0 <= c < len(rows[i]):
                m = YEAR_CELL.search(str(rows[i][c] or ""))
                if m:
                    return m.group(1)
    for c in range(col - 1, max(-1, col - 9), -1):  # ano a esquerda (leading)
        m = BARE_YEAR.match(str(header[c] or ""))
        if m:
            return m.group(1)
    years = [m.group(1) for r in rows[:header_idx + 1] for cell in r
             for m in [YEAR_CELL.search(str(cell or ""))] if m]
    return max(years) if years else None


def label_of(row: list) -> str:
    for cell in row[:3]:
        text = str(cell or "").strip()
        if text:
            return text
    return ""


def scale_and_currency(rows: list[list], fonte: str) -> tuple[float, str]:
    probe = " ".join(str(c or "") for r in rows[:8] for c in r[:6]) + " " + fonte
    moeda = "BRL" if BRL_HINT.search(probe) else "USD"
    if SCALE_BILLIONS.search(probe):
        return 1.0, moeda
    if SCALE_MILLIONS.search(probe):
        return 1 / 1000.0, moeda
    return 1 / 1000.0, moeda


def to_number(cell: object) -> float | None:
    if cell is None:
        return None
    if isinstance(cell, (int, float)):
        return float(cell)
    text = str(cell).strip()
    if not text or text in ("-", "--", "n/a", "N/A", "...", "–", "—"):
        return None
    negativo = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        text = text.replace(",", ".") if len(parts[-1]) <= 2 else text.replace(",", "")
    text = re.sub(r"[^0-9.\-eE]", "", text)
    try:
        value = float(text)
        return -value if negativo else value
    except ValueError:
        return None


MONTH_Q = {"january": "Q1", "february": "Q1", "march": "Q1", "april": "Q2",
           "may": "Q2", "june": "Q2", "july": "Q3", "august": "Q3",
           "september": "Q3", "october": "Q4", "november": "Q4", "december": "Q4"}
ENDED_MONTH = re.compile(r"(three|six|nine|twelve)\s+months?\s+ended|ended\s+\w+\s+\d{1,2}", re.IGNORECASE)


def ended_period_columns(rows: list[list]) -> tuple[int, dict[int, str]] | None:
    """Fallback p/ suplementos estilo Exxon: 'Three Months Ended June 30' + linha de anos."""
    for i, row in enumerate(rows[:12]):
        joined = " ".join(str(c or "") for c in row).lower()
        if "months ended" not in joined and "ended" not in joined:
            continue
        quarter = next((q for m, q in MONTH_Q.items() if m in joined), None)
        if not quarter:
            continue
        semesters = "six" in joined
        for j in range(i + 1, min(i + 4, len(rows))):
            year_row = rows[j]
            cols = {}
            for k in range(1, min(len(year_row), 20)):
                m = YEAR_CELL.search(str(year_row[k] or ""))
                if m and not SKIP_COL.search(str(year_row[k] or "")):
                    cols[k] = f"{m.group(1)}{quarter}"
            if len(cols) >= 2:
                return j, cols
    return None


def extract_from_matrix(rows: list[list[object]], fonte: str) -> list[RawExtraction]:
    rows = [r for r in rows if any(c is not None and str(c).strip() for c in r)]
    header_idx, period_cols = -1, {}
    for i, row in enumerate(rows[:40]):
        found = {}
        com_ano = False
        for j in range(1, min(len(row), 42)):
            per, tem_ano = norm_period(row[j])
            if not per:
                continue
            if not tem_ano:
                ano = year_context(rows, i, j)
                if not ano:
                    continue
                per = f"{ano}{per}"
            else:
                com_ano = True
            found[j] = per
        # >= 2 colunas: regra original (evita confundir uma célula solta com período).
        # == 1 colunia: só aceito se o PRÓPRIO cabeçalho traz o ano ("2026Q3", "1T26"),
        # que é inequívoco. Uma coluna única de "Q3" sem ano continua rejeitada,
        # senão qualquer número solto na planilha viraria trimestre.
        if len(found) >= 2 or (len(found) == 1 and com_ano):
            header_idx, period_cols = i, found
            break
    if header_idx < 0:
        fallback = ended_period_columns(rows)
        if not fallback:
            return []
        header_idx, period_cols = fallback
    scale, moeda = scale_and_currency(rows, fonte)
    base_conf = 0.95 if "principais" in fonte.lower() else 0.85
    candidatos: dict[tuple[str, str], RawExtraction] = {}
    for row in rows[header_idx + 1:]:
        label = label_of(row)
        if not label or SKIP_ROW.search(label):
            continue
        canon, _, _ = resolve(label)
        if canon is None and "invest" in fonte.lower() and normalize(label) in ("subtotal", "total"):
            canon = "CAPEX"  # total da tabela de investimentos (ex.: Petrobras TABELA 3)
        if not canon:
            continue
        unidade = "pessoas" if canon == "EFETIVO_TOTAL" else ("kboed" if canon == "PRODUCAO_BOED" else "USD bi")
        for col, periodo in period_cols.items():
            if col >= len(row):
                continue
            num = to_number(row[col])
            if num is None:
                continue
            valor = num if canon in ("EFETIVO_TOTAL", "PRODUCAO_BOED", "FUT_REFINO") else num * scale
            ext = RawExtraction(canon, periodo, round(valor, 4), unidade, base_conf, fonte,
                                moeda, {"rotulo_origem": label})
            key = (canon, periodo)
            if key not in candidatos or ext.confianca > candidatos[key].confianca:
                candidatos[key] = ext
    return list(candidatos.values())


def parse_excel(path: Path) -> list[RawExtraction]:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out: list[RawExtraction] = []
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True, max_row=150, max_col=44)]
        out.extend(extract_from_matrix(rows, f"{path.name}#{ws.title}"))
    wb.close()
    best: dict[tuple[str, str], RawExtraction] = {}
    for ext in out:
        key = (ext.rubrica, ext.periodo)
        if key not in best or ext.confianca > best[key].confianca:
            best[key] = ext
    return list(best.values())


def _delimitador(texto: str) -> str:
    """Detecta o separador do CSV (padrao brasileiro = ';')."""
    try:
        return csv.Sniffer().sniff(texto[:4096], delimiters=";,\t|").delimiter
    except csv.Error:
        return ";" if texto.count(";") >= texto.count(",") else ","


def parse_csv(path: Path) -> list[RawExtraction]:
    """CSV com separador detectado (antes assumia ',', e um CSV com ';' saia vazio)."""
    texto = path.read_text(encoding="utf-8-sig", errors="ignore")
    rows = list(csv.reader(io.StringIO(texto), delimiter=_delimitador(texto)))
    return extract_from_matrix(rows, path.name)


def parse_tab(path: Path) -> list[RawExtraction]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return parse_csv(path)
    if suffix in (".xlsx", ".xlsm"):
        return parse_excel(path)
    if suffix == ".xls":
        try:
            import pandas as pd
            out: list[RawExtraction] = []
            sheets = pd.read_excel(path, sheet_name=None, header=None, nrows=150)
            for sheet, df in sheets.items():
                rows = df.where(pd.notnull(df), None).values.tolist()
                out.extend(extract_from_matrix(rows, f"{path.name}#{sheet}"))
            return out
        except Exception:
            return []
    return []
