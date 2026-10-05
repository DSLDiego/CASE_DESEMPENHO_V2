"""Worker parse_pdf: PDFs (releases/demonstracoes) -> extracoes.

Usa PyMuPDF (rapido) + pdfplumber (tabelas). Processa em streaming por pagina
para nao estourar memoria (skill BigString: evita concatenar tudo).
"""
from __future__ import annotations

import re
from pathlib import Path

from models.depara import resolve
from workers.parse_tab import (RawExtraction, norm_period, scale_and_currency,
                               to_number, SKIP_ROW)

MONEY = re.compile(r"\(?\$?\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?\)?")
QUARTER_HEAD = re.compile(r"Q([1-4])\s*(20\d{2})", re.IGNORECASE)
NUM_TOKEN = re.compile(r"^\(?[\d.,]+\)?$")
FOOTNOTE = re.compile(r"^\(\d{1,2}\)$|^\[\d{1,2}\]$|^\d{1,2}\)$")


def _num_tokens(text: str) -> list[str]:
    return [t for t in text.split()
            if NUM_TOKEN.match(t.strip("*,[]")) and "%" not in t and not FOOTNOTE.match(t.strip())]


def page_texts(path: Path, max_pages: int = 12) -> list[str]:
    try:
        import pymupdf
        out = []
        with pymupdf.open(path) as doc:
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                out.append(page.get_text("text") or "")
        return out
    except Exception:
        return []


def extract_tables(path: Path, max_pages: int = 8) -> list[list[list[object]]]:
    try:
        import pdfplumber
        tables = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages[:max_pages]:
                try:
                    for tbl in page.extract_tables() or []:
                        if tbl and len(tbl) >= 3:
                            tables.append(tbl)
                except Exception:
                    continue
        return tables
    except Exception:
        return []


HEAD_WORD = re.compile(r"Q[1-4]\s*20\d{2}|20\d{2}|change|first half|unaudited|quarter|on Q[1-4]", re.IGNORECASE)
SENTENCE_FIG = re.compile(
    r"(?P<label>[A-Za-z][\w\s()/,&.'-]{4,60}?)\s+for\s+"
    r"(?:(?P<std>Q[1-4]\s*20\d{2}|[1-4]T\d{2}|20\d{2}Q[1-4])|"
    r"(?P<word>first|second|third|fourth)[- ]quarter\s*(?P<yr>20\d{2}))\s+"
    r"(?:was|is|were|reached|totalled|totaled)\s+\$?\s?(?P<num>[\d.,]+)\s*"
    r"(?P<esc>billion|million|trillion|bi\b)",
    re.IGNORECASE)
QWORD = {"first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4"}
SENTENCE_FIG2 = None  # substituido pela abordagem ancora+pares abaixo
LINE_QUARTER = re.compile(
    r"(?:in|for)\s+the\s+(first|second|third|fourth)\s+quarter(?:\s+of\s*(20\d{2}))?",
    re.IGNORECASE)
FIG_PAIR = re.compile(
    r"(?P<label>[A-Za-z][\w\s()/,&.'*-]{3,60}?)\s+"
    r"(?:of|at|was|were|is|totalled|totaled|reported|posted|reached|amounted to)\s+\$?\s?"
    r"(?P<num>[\d.,]+)\s*(?P<esc>billion|million|trillion|bi\b)",
    re.IGNORECASE)
SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+(?=[A-Z0-9$\"“])")


def sentences(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        for sent in SENT_SPLIT.split(line or ""):
            sent = " ".join(sent.split())
            if 30 <= len(sent) <= 300:
                out.append(sent)
    return out


def flowed(lines: list[str]) -> list[str]:
    """Junta quebras fisicas do PDF antes de fatiar em sentencas."""
    return [" ".join(lines)]
DOC_FOLDER = re.compile(r"(20\d{2})_([1-4])T")
ANNUAL_CUE = re.compile(
    r"full.year|annual|since|cumulative|guidance|expect|plan|compared|versus|target|outlook|"
    r"buyback|dividend|distribution|repurchase|20(2[0-4]|19\d)|2030",
    re.IGNORECASE)
COPULA_PAIR = re.compile(
    r"(?P<label>[A-Za-z][\w\s()/,&.'*-]{3,60}?)\s+(?:was|were|is)\s+\$?\s?"
    r"(?P<num>[\d.,]+)\s*(?P<esc>billion|million|trillion|bi\b)",
    re.IGNORECASE)
EPS_PAIR = re.compile(
    r"\$?\s?(?P<num>[\d.,]+)\s*(?P<esc>billion|million)\s*,?\s+or\s+\$?[\d.,]+\s+per share",
    re.IGNORECASE)


def doc_year_hint(path: Path) -> str | None:
    hint = doc_period_hint(path)
    return hint[0] if hint else None


def doc_period_hint(path: Path) -> tuple[str, str] | None:
    """(ano, trimestre) inferidos do nome/pasta: 4Q25->(2025,Q4), q2-2026->(2026,Q2)."""
    m = DOC_FOLDER.search(path.parent.name)
    if m:
        return m.group(1), f"Q{m.group(2)}"
    text = path.name
    m = re.search(r"\b([1-4])Q(\d{2})\b", text)
    if m:
        return f"20{m.group(2)}", f"Q{m.group(1)}"
    m = re.search(r"Q([1-4])[-_ ]?(20\d{2})", text, re.IGNORECASE)
    if m:
        return m.group(2), f"Q{m.group(1)}"
    m = re.search(r"\b([1-4])T(2\d)\b", text)
    if m:
        return f"20{m.group(2)}", f"Q{m.group(1)}"
    m = re.search(r"(20\d{2})", text)
    if m:
        return m.group(1), ""
    return None


def extract_sentence3_figures(lines: list[str], fonte: str,
                              doc_per: tuple[str, str] | None) -> list[RawExtraction]:
    """Frases copulares sem ancora ('Cash flow from operating activities was $12.7 billion').

    Vale o periodo do documento; exige ausencia de annual-cues e verbos was|were|is.
    Conf 0.70: so carrega onde nao ha fato melhor (prioridade de confianca no ETL)."""
    out: list[RawExtraction] = []
    if not doc_per or not doc_per[1]:
        return out
    per = f"{doc_per[0]}{doc_per[1]}"
    for line in sentences(flowed(lines)):
        if len(line) > 300 or ANNUAL_CUE.search(line):
            continue
        for m in EPS_PAIR.finditer(line):  # "$6.5 billion, or $1.53 per share" = lucro do trimestre
            if re.search(r"excluding|adjusted|underlying", line, re.IGNORECASE):
                continue  # medida ajustada, nao GAAP: nao carrega como lucro liquido
            num = to_number(m.group("num"))
            if num is None:
                continue
            fator = 1.0 if m.group("esc").lower().startswith("b") else 1 / 1000.0
            out.append(RawExtraction("LUCRO_LIQUIDO", per, round(num * fator, 4), "USD bi", 0.70,
                                     f"{fonte}#eps", "USD", {"rotulo_origem": "headline earnings per share"}))
        for m in COPULA_PAIR.finditer(line):
            label = m.group("label")
            if SKIP_ROW.search(label):
                continue
            canon, _, _ = resolve(label)
            if not canon:
                continue
            num = to_number(m.group("num"))
            if num is None:
                continue
            escala = m.group("esc").lower()
            fator = 1.0 if escala.startswith(("billion", "bi")) else 1 / 1000.0
            if escala.startswith("trillion"):
                fator = 1000.0
            unidade = ("pessoas" if canon == "EFETIVO_TOTAL"
                       else "kboed" if canon == "PRODUCAO_BOED" else "USD bi")
            valor = num if canon in ("EFETIVO_TOTAL", "PRODUCAO_BOED", "FUT_REFINO") else num * fator
            out.append(RawExtraction(canon, per, round(valor, 4), unidade, 0.70,
                                     f"{fonte}#frase3", "USD", {"rotulo_origem": label.strip()}))
    best: dict[tuple[str, str], RawExtraction] = {}
    for ext in out:
        if (ext.rubrica, ext.periodo) not in best:
            best[(ext.rubrica, ext.periodo)] = ext
    return list(best.values())


def extract_sentence2_figures(lines: list[str], fonte: str, doc_year: str | None) -> list[RawExtraction]:
    """Frases com ancora trimestral: '...adjusted net income of $6.0 billion ... in the second quarter'.

    A ancora (in|for the X quarter) marca a frase como trimestral; todos os pares
    'rotulo + verbo + $valor + escala' da mesma linha herdam o periodo.
    Sem ancora, a frase e ignorada (evita capturar numeros anuais/guidance)."""
    out: list[RawExtraction] = []
    for line in sentences(flowed(lines)):
        if len(line) > 300:
            continue
        anchor = LINE_QUARTER.search(line)
        if not anchor:
            continue
        ano = anchor.group(2) or doc_year
        if not ano:
            continue
        per = f"{ano}{QWORD[anchor.group(1).lower()]}"
        for m in FIG_PAIR.finditer(line):
            label = m.group("label")
            if SKIP_ROW.search(label):
                continue
            canon, _, _ = resolve(label)
            if not canon:
                continue
            num = to_number(m.group("num"))
            if num is None:
                continue
            escala = m.group("esc").lower()
            fator = 1.0 if escala.startswith(("billion", "bi")) else 1 / 1000.0
            if escala.startswith("trillion"):
                fator = 1000.0
            unidade = ("pessoas" if canon == "EFETIVO_TOTAL"
                       else "kboed" if canon == "PRODUCAO_BOED" else "USD bi")
            valor = num if canon in ("EFETIVO_TOTAL", "PRODUCAO_BOED", "FUT_REFINO") else num * fator
            out.append(RawExtraction(canon, per, round(valor, 4), unidade, 0.70,
                                     f"{fonte}#frase2", "USD", {"rotulo_origem": label.strip()}))
    best: dict[tuple[str, str], RawExtraction] = {}
    for ext in out:
        if (ext.rubrica, ext.periodo) not in best:
            best[(ext.rubrica, ext.periodo)] = ext
    return list(best.values())


def extract_sentence_figures(lines: list[str], fonte: str) -> list[RawExtraction]:
    """Frases de releases: 'Income attributable to shareholders for Q2 2026 is $10.8 billion'."""
    out: list[RawExtraction] = []
    for line in sentences(flowed(lines)):
        if len(line) > 260:
            continue
        for m in SENTENCE_FIG.finditer(line):
            label = m.group("label")
            if SKIP_ROW.search(label):
                continue
            canon, _, _ = resolve(label)
            if not canon:
                continue
            if m.group("std"):
                per, tem_ano = norm_period(m.group("std"))
            else:
                per, tem_ano = f"{m.group('yr')}{QWORD[m.group('word').lower()]}", True
            if not per or not tem_ano:
                continue
            num = to_number(m.group("num"))
            if num is None:
                continue
            escala = m.group("esc").lower()
            fator = 1.0 if escala.startswith(("billion", "bi")) else 1 / 1000.0
            if escala.startswith("trillion"):
                fator = 1000.0
            unidade = ("pessoas" if canon == "EFETIVO_TOTAL"
                       else "kboed" if canon == "PRODUCAO_BOED" else "USD bi")
            valor = num if canon in ("EFETIVO_TOTAL", "PRODUCAO_BOED", "FUT_REFINO") else num * fator
            out.append(RawExtraction(canon, per, round(valor, 4), unidade, 0.72,
                                     f"{fonte}#frase", "USD", {"rotulo_origem": label.strip()}))
    best: dict[tuple[str, str], RawExtraction] = {}
    for ext in out:
        key = (ext.rubrica, ext.periodo)
        if key not in best:
            best[key] = ext
    return list(best.values())


def extract_key_figures(lines: list[str], fonte: str) -> list[RawExtraction]:
    """Blocos 'key figures' de releases: cabecalho com trimestres
    (ex.: 'Q2 2026 Q1 2026 Q2 2025 ...', mesmo quebrado em linhas) seguido
    de linhas 'rotulo v1 v2 v3...'."""
    out: list[RawExtraction] = []
    i = 0
    limite = min(len(lines), 1200)
    while i < limite:
        line = lines[i]
        if len(line) > 60 or not QUARTER_HEAD.search(line):
            i += 1
            continue
        block, j = [line], i + 1
        while j < len(lines) and len(lines[j]) < 60 and HEAD_WORD.search(lines[j] or ""):
            block.append(lines[j])
            j += 1
        quarters = [f"{m.group(2)}Q{m.group(1)}" for m in QUARTER_HEAD.finditer(" ".join(block))]
        data_start = j
        if len(quarters) < 2:
            i += 1
            continue
        window = "\n".join(lines[max(0, i - 3):i + 2])
        scale = 1.0 if re.search(r"bilh|billion|\(B\$\)", window, re.IGNORECASE) else 1 / 1000.0

        def registrar(label: str, valores: list[float]) -> None:
            if len(label) < 4 or SKIP_ROW.search(label):
                return
            canon, _, _ = resolve(label)
            if not canon or len(valores) < 2:
                return
            unidade = ("pessoas" if canon == "EFETIVO_TOTAL"
                       else "kboed" if canon == "PRODUCAO_BOED" else "USD bi")
            for per, num in zip(quarters, valores):
                valor = (num if canon in ("EFETIVO_TOTAL", "PRODUCAO_BOED", "FUT_REFINO")
                         else num * scale)
                out.append(RawExtraction(canon, per, round(valor, 4), unidade, 0.78,
                                         f"{fonte}#key-figures", "USD", {"rotulo_origem": label}))

        k = data_start
        while k < min(data_start + 60, len(lines)):
            line = lines[k] or ""
            if QUARTER_HEAD.search(line) or len(line) > 220:
                k += 1
                continue
            m_first_digit = re.search(r"\d", line)
            if m_first_digit:
                # inline: "rotulo v1 v2 v3"
                label, rest = line[:m_first_digit.start()].strip(), line[m_first_digit.start():]
                tokens = _num_tokens(rest)[:len(quarters)]
                valores = [v for v in (to_number(t) for t in tokens) if v is not None]
                registrar(label, valores)
                k += 1
            elif re.search(r"[A-Za-z]", line):
                # colunar: rotulo numa linha, numeros nas linhas seguintes
                label, nums, m = line.strip(), [], k + 1
                while m < len(lines) and len(nums) < len(quarters) + 3:
                    cand = (lines[m] or "").strip().strip("*,[]")
                    if not cand:
                        m += 1
                        continue
                    if NUM_TOKEN.match(cand) and "%" not in cand and not FOOTNOTE.match(cand):
                        v = to_number(cand)
                        if v is not None:
                            nums.append(v)
                        m += 1
                    else:
                        break
                registrar(label, nums[:len(quarters)])
                k = m if nums else k + 1
            else:
                k += 1
        i = data_start  # segue varrendo: proximo bloco (ex.: income statement apos key figures)
    best: dict[tuple[str, str], RawExtraction] = {}
    for ext in out:
        key = (ext.rubrica, ext.periodo)
        if key not in best or ext.confianca > best[key].confianca:
            best[key] = ext
    return list(best.values())


def parse_pdf(path: Path) -> list[RawExtraction]:
    from workers.parse_tab import extract_from_matrix
    deep = "financial-statement" in path.name.lower()
    texts = page_texts(path, max_pages=30 if deep else 12)
    lines = [ln.strip() for t in texts for ln in t.splitlines()]
    keyfig = extract_key_figures(lines, path.name)
    frase = extract_sentence_figures(lines, path.name)
    frase2 = extract_sentence2_figures(lines, path.name, doc_year_hint(path))
    frase3 = extract_sentence3_figures(lines, path.name, doc_period_hint(path))
    precisos = {(e.rubrica, e.periodo): e for e in keyfig}
    for e in frase + frase2 + frase3:
        precisos.setdefault((e.rubrica, e.periodo), e)
    if precisos:  # layouts de alta precisao dispensam tabelas ruidosas
        return list(precisos.values())
    out: list[RawExtraction] = []
    for tbl in extract_tables(path):
        rows = [[c for c in r] for r in tbl]
        out.extend(extract_from_matrix(rows, f"{path.name}#pdf-table"))
    if out:
        best: dict[tuple[str, str], RawExtraction] = {}
        for ext in out:
            ext.confianca = max(0.55, ext.confianca - 0.15)
            key = (ext.rubrica, ext.periodo)
            if key not in best or ext.confianca > best[key].confianca:
                best[key] = ext
        return list(best.values())
    # fallback textual: procura "Rotulo ... valor" proximo a periodo citado
    joined = "\n".join(texts[:6])
    periodo = None
    for cand in re.findall(r"[1-4]T\d{2}|Q[1-4]\s*20\d{2}|20\d{2}Q[1-4]|[1-4]Q\d{2}", joined):
        periodo, _ = norm_period(cand)
        if periodo:
            break
    if not periodo:
        m = re.search(r"(first|second|third|fourth)\s+quarter\s+(20\d{2})", joined, re.IGNORECASE)
        if m:
            q = {"first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4"}[m.group(1).lower()]
            periodo = f"{m.group(2)}{q}"
    if not periodo:
        return []
    results: list[RawExtraction] = []
    for line in joined.splitlines():
        label = line[:60]
        canon, _, _ = resolve(label)
        if not canon:
            continue
        nums = [n for n in MONEY.findall(line) if not FOOTNOTE.match(n.strip())]
        if not nums:
            continue
        num = to_number(nums[-1])
        if num is None:
            continue
        scale, _moeda = scale_and_currency([[joined[:500]]], path.name)
        valor = num if canon in ("EFETIVO_TOTAL", "PRODUCAO_BOED") else num * scale
        results.append(RawExtraction(canon, periodo, round(valor, 4), "USD bi", 0.55,
                                     f"{path.name}#texto", {"rotulo_origem": label.strip()}))
    return results
