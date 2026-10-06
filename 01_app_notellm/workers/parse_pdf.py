"""Worker parse_pdf: PDFs (releases/demonstracoes) -> extracoes.

Usa PyMuPDF (rapido) + pdfplumber (tabelas). Processa em streaming por pagina
para nao estourar memoria (skill BigString: evita concatenar tudo).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from models.depara import resolve
from workers.naming import periodo_do_nome
from workers.parse_tab import (RawExtraction, norm_period, scale_and_currency,
                               to_number, SKIP_ROW)

MONEY = re.compile(r"\(?\$?\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?\)?")
QUARTER_HEAD = re.compile(r"Q([1-4])\s*(20\d{2})", re.IGNORECASE)
NUM_TOKEN = re.compile(r"^\(?[\d.,]+\)?$")
FOOTNOTE = re.compile(r"^\(\d{1,2}\)$|^\[\d{1,2}\]$|^\d{1,2}\)$")


def _num_tokens(text: str) -> list[str]:
    return [t for t in text.split()
            if NUM_TOKEN.match(t.strip("*,[]")) and "%" not in t and not FOOTNOTE.match(t.strip())]


# ------------------------------------------------------- cache de texto (M8.11)
# Texto extraído é a parte cara do parse (0,31 s nas 12 primeiras páginas do DF
# da Petrobras). Reprocessar o MESMO arquivo reextrai tudo de novo, e reprocessar
# é comum: um `etl` completo apósoload de um trimestre novo relê o acervo inteiro.
#
# A chave é o SHA-256 do arquivo (o mesmo que identifica a fonte), então o cache é
# seguro por construção: arquivo com o mesmo hash tem o mesmo texto. Nome do cache
# = hash + nº de páginas lidas, porque mudar a profundidade muda o texto.
CACHE_DIR = Path(os.environ.get("PETRO_CACHE_DIR", "")) if os.environ.get(
    "PETRO_CACHE_DIR") else Path(__file__).resolve().parent.parent / "data" / "cache_pdf"
_CACHE_MB_MAX = 512          # teto: o acervo cresce, o disco não é infinito


def _chave_cache(path: Path, max_pages: int) -> str:
    from models.repositories import sha256_file
    return f"{sha256_file(path)}_{max_pages}"


def _caminho_cache(chave: str) -> Path:
    return CACHE_DIR / f"{chave}.json"


def cache_ler(chave: str) -> list[str] | None:
    """Texto em cache, ou None se não houver / estiver corrompido."""
    destino = _caminho_cache(chave)
    if not destino.exists():
        return None
    try:
        import json
        dados = json.loads(destino.read_text(encoding="utf-8"))
        textos = dados["textos"]
        return [str(t) for t in textos] if isinstance(textos, list) else None
    except Exception:
        return None       # cache corrompido e um cache normal: reextrai


def cache_gravar(chave: str, textos: list[str]) -> None:
    try:
        import json
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _caminho_cache(chave).write_text(
            json.dumps({"textos": textos}, ensure_ascii=False), encoding="utf-8")
        cache_limpar()
    except Exception:
        return      # disco cheio/permission: o parse ja foi feito, cache e otimizacao


def cache_limpar(tudo: bool = False) -> int:
    """Remove entradas antigas até o teto de disco. Devolve quantas saiu.

    `tudo=True` esvazia o cache (o que o `fontes cache --limpar` faz): nome
    "usar_teto=False" seria ambíguo — se sem teto, o que a função faria?
    """
    if not CACHE_DIR.exists():
        return 0
    arquivos = sorted(CACHE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if tudo:
        for p in arquivos:
            p.unlink(missing_ok=True)
        return len(arquivos)
    total = sum(p.stat().st_size for p in arquivos)
    teto = _CACHE_MB_MAX * 1024 * 1024
    removidos = 0
    for p in arquivos:
        if total <= teto:
            break
        total -= p.stat().st_size
        p.unlink(missing_ok=True)
        removidos += 1
    return removidos


def cache_stats() -> dict:
    arquivos = list(CACHE_DIR.glob("*.json")) if CACHE_DIR.exists() else []
    return {"entradas": len(arquivos),
            "mb": round(sum(p.stat().st_size for p in arquivos) / 1024 / 1024, 1),
            "dir": str(CACHE_DIR)}


def page_texts(path: Path, max_pages: int = 12) -> list[str]:
    """Texto por página, com cache por hash do arquivo (M8.11).

    O cache é ligado por padrão porque o caso que o justifica é o reprocessamento:
    um `etl` completo relê o acervo inteiro e o texto não mudou. Quem quiser medir
    o parse cru desliga com PETRO_CACHE_PDF=0.
    """
    usar_cache = os.environ.get("PETRO_CACHE_PDF", "1") != "0"
    chave: str | None = None
    if usar_cache:
        try:
            chave = _chave_cache(path, max_pages)
            em_cache = cache_ler(chave)
            if em_cache is not None:
                return em_cache
        except Exception:
            chave = None      # hash falha (arquivo sumindo): segue sem cache
    try:
        import pymupdf
        out = []
        with pymupdf.open(path) as doc:
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                out.append(page.get_text("text") or "")
    except Exception:
        return []
    if chave:
        cache_gravar(chave, out)
    return out


# Ultima metrica de leitura do PDF processado (M8.12). O ETL le este valor logo
# depois do parse, entao um dicionario por processo e suficiente: o parse de cada
# arquivo acontece em um processo (ou na serial), e a leitura e imediata.
_ULTIMA_METRICA: dict[str, int] = {}


def ultima_metrica() -> dict[str, int]:
    """Metrica de leitura do ULTIMO PDF parseado (paginas/paginas_lidas/tabelas)."""
    return dict(_ULTIMA_METRICA)


def _registrar_metricas(path: Path, max_pages: int, tabelas: list | None) -> None:
    _ULTIMA_METRICA.clear()
    _ULTIMA_METRICA.update(metricas(path, max_pages, tabelas))


def n_paginas(path: Path) -> int:
    """Total de páginas do PDF (0 se não der para abrir). Só a contagem, sem texto."""
    try:
        import pymupdf
        with pymupdf.open(path) as doc:
            return int(doc.page_count)
    except Exception:
        return 0


def _contar_tabelas(path: Path, max_pages: int) -> int:
    """Quantas tabelas o detector acha no documento (sem extrair as matrizes).

    `find_tables()` já faz o trabalho caro da detecção; `extract()` (o que o parse
    usa para virar extração) é o passo seguinte. Contar separadamente custa ~0,2 s
    por documento e por isso só acontece quando o parse NÃO já passou por aqui.
    """
    try:
        import pymupdf
        achadas = 0
        with pymupdf.open(path) as doc:
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                detector = getattr(page, "find_tables", None)
                if detector is None:          # build antigo do MuPDF, sem suporte
                    break
                try:
                    achadas += len(getattr(detector(), "tables", None) or [])
                except Exception:
                    continue
        if achadas:
            return achadas
    except Exception:
        pass
    try:
        return len(_tables_pdfplumber(path, min(max_pages, 8)))
    except Exception:
        return 0


def metricas(path: Path, max_pages: int = 12, tabelas: list | None = None) -> dict[str, int]:
    """Métrica de leitura do documento (M8.12): páginas e tabelas detectadas.

    `paginas` é o total real do arquivo e `paginas_lidas` o que o parse realmente
    percorreu (limitado por max_pages) — misturar os dois esconderia o custo de um
    DF de 37 páginas lido só até a 12ª.

    `tabelas` reaproveita a detecção que o parse acabou de fazer (mesma lista,
    mesmo custo). Só quando ela não é passada é que a contagem roda aqui.
    """
    total = n_paginas(path)
    if not total:
        return {"paginas": 0, "paginas_lidas": 0, "tabelas": 0}
    lidas = min(total, max_pages)
    return {"paginas": total, "paginas_lidas": lidas,
            "tabelas": len(tabelas) if tabelas is not None else _contar_tabelas(path, lidas)}


def extract_tables(path: Path, max_pages: int = 8) -> list[list[list[object]]]:
    """Tabelas do PDF: PyMuPDF primeiro (rápido, MuPDF nativo), pdfplumber como fallback.

    PyMuPDF é ~3-8x mais rápido e não depende de cairo; em DFs da Petrobras ele
    encontra as tabelas com a mesma qualidade, então virou o caminho primário.
    """
    tabelas = _tables_pymupdf(path, max_pages)
    if tabelas:
        return tabelas
    return _tables_pdfplumber(path, max_pages)


def _tables_pymupdf(path: Path, max_pages: int) -> list[list[list[object]]]:
    """Detecção de tabelas via PyMuPDF (page.find_tables, seleção 'lines')."""
    out: list[list[list[object]]] = []
    try:
        import pymupdf
    except ImportError:
        return out
    try:
        with pymupdf.open(path) as doc:
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                detector = getattr(page, "find_tables", None)
                if detector is None:          # build antigo do MuPDF, sem suporte
                    break
                try:
                    achadas = detector()
                except Exception:
                    continue
                for tb in (getattr(achadas, "tables", None) or []):
                    try:
                        matriz = tb.extract()
                    except Exception:
                        continue
                    matriz = [[c for c in linha] for linha in (matriz or [])]
                    if matriz and len(matriz) >= 3:
                        out.append(matriz)
    except Exception:
        return out
    return out


def _tables_pdfplumber(path: Path, max_pages: int) -> list[list[list[object]]]:
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

# Extrator complementar (PDFOxide/Rust). Liga/desliga por var de ambiente para
# poder desligar em maquina sem a lib sem mexer no codigo.
ENABLE_EXTRATOR_ALTERNATIVO = os.environ.get("PETRO_NO_ALTERNATIVO", "0") != "1"
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
    """(ano, trimestre) do nome/pasta, tolerante a acento/espaco/hifen/cifrao.

    Cobre 4Q25, q2-2026, 1T26, 3Q25, '2025 3T', 'Demonstracoes ... US$ (1)'.
    """
    m = DOC_FOLDER.search(path.parent.name)
    if m:
        return m.group(1), f"Q{m.group(2)}"
    return periodo_do_nome(path.name)


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


def page_texts_alternativo(path: Path, max_pages: int = 12) -> list[str]:
    """Fallback de texto (PDFOxide/Rust) para quando o MuPDF não devolve nada.

    Benchmark no acervo (11 PDFs, `docs/LISTA_TAREFAS.md` M8.8): o PDFOxide é 2,8x
    mais lento que o PyMuPDF para texto e **não** acha mais tabelas (0 contra 2 nos
    DFs da Petrobras), e como extrator *primário* não amplia os fatos extraídos
    (mesmas 35 extrações). Portanto fica só como resiliência: entra quando o
    PyMuPDF falha em abrir/decodificar o arquivo (stream corrompido, por exemplo).
    """
    try:
        import pdf_oxide
    except ImportError:
        return []
    try:
        doc = pdf_oxide.PdfDocument.from_bytes(Path(path).read_bytes())
        return [str(doc.extract_text(i))
                for i in range(min(max_pages, doc.page_count()))]
    except Exception:
        return []
    except BaseException as exc:      # noqa: BLE001
        # PDFOxide é Rust/pyo3: um PDF truncado derruba um pânico que NÃO é
        # Exception (PanicException deriva de BaseException) e derrubaria o ETL
        # inteiro. Fallback de resiliência não pode ser o que quebra a carga.
        print(f"[parse_pdf] fallback oxide falhou em {Path(path).name}: "
              f"{type(exc).__name__}")
        return []


def parse_pdf(path: Path) -> list[RawExtraction]:
    from workers.parse_tab import extract_from_matrix
    deep = "financial-statement" in path.name.lower()
    max_pag = 30 if deep else 12
    textos = page_texts(path, max_pages=max_pag)
    if not textos and ENABLE_EXTRATOR_ALTERNATIVO:
        textos = page_texts_alternativo(path, max_pag)   # MuPDF falhou: tenta o Rust
    lines = [ln.strip() for t in textos for ln in t.splitlines()]
    keyfig = extract_key_figures(lines, path.name)
    frase = extract_sentence_figures(lines, path.name)
    frase2 = extract_sentence2_figures(lines, path.name, doc_year_hint(path))
    frase3 = extract_sentence3_figures(lines, path.name, doc_period_hint(path))
    precisos = {(e.rubrica, e.periodo): e for e in keyfig}
    for e in frase + frase2 + frase3:
        precisos.setdefault((e.rubrica, e.periodo), e)
    if precisos:  # layouts de alta precisao dispensam tabelas ruidosas
        _registrar_metricas(path, max_pag, None)
        return list(precisos.values())
    out: list[RawExtraction] = []
    tabelas = extract_tables(path)
    _registrar_metricas(path, max_pag, tabelas)
    for tbl in tabelas:
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
    joined = "\n".join(textos[:6])
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
                                     f"{path.name}#texto",
                                     extras={"rotulo_origem": label.strip()}))
    return results
