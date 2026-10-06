"""Normalizacao e classificacao de nomes de arquivo (nomes reais sao hostis).

Problema real: o Container traz arquivos como
    "_Demonstracoes Financeiras 1T26  - US$.pdf"   (espaco duplo, hifen, cifrao)
    "Transcricao Webcast 3T25.pdf"                  (acento)
    "DFS R$ Portugues.pdf"
    "Relatorio Fiscal 3Q25.pdf"                     (3Q em vez de 3T)
Comparacoes por substring falhavam (acento, pontuacao, plural) e geravam dois
erros opostos: transcricao era *parseada* e nomes com "$" nao casavam na allow-list.
Aqui a decisao vira REGEX sobre o nome normalizado, com regra explicita:
documento narrativo (transcricao/slides) nao entra; documento numerico entra.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

# --------------------------------------------------------------------------
# 1) normalizacao
# --------------------------------------------------------------------------
_CIFRAO = {"$": " dollar ", "€": " euro ", "£": " pound "}


def normalizar_nome(nome: str) -> str:
    """'Transcricao Webcast 3T25' -> 'transcricao webcast 3t25' (sem acento/pontuacao)."""
    texto = nome
    for simbolo, troca in _CIFRAO.items():
        texto = texto.replace(simbolo, troca)
    decomposto = unicodedata.normalize("NFKD", texto)
    ascii_ = decomposto.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", " ", ascii_).lower().strip()


# --------------------------------------------------------------------------
# 2) regexes de classificacao (stems, nao palavras exatas -> aceita plural)
# --------------------------------------------------------------------------
# Documento NARRATIVO: nao tem tabela estrutural, nao entra no ETL numerico.
SKIP_RE = re.compile(
    r"\b(transcri\w*|transcript\w*|webcast|slides?|apresent\w*|present\w*|speech\w*"
    r"|remark\w*|script\w*|qa|q\s*a|earnings\s+call|conference\s+call|call|video|audio"
    r"|webinar|cover|letter)\b"
)
# Documento NUMERICO: tem tabela/planilha, entra.
ALLOW_RE = re.compile(
    r"\b(result\w*|desempenho|demonstra\w*|demonstrat\w*|relatorio|relat\w*|fiscal"
    r"|itr|dre|dfs|account\w*|statement\w*|earnings|financial|financeiro|press|release\w*"
    r"|supplement\w*|suplement\w*|qra|tabela|planilha|proforma|guidance|guidance\w*"
    r"|q[1-4]|t[1-4](?=\s|$))\b"
)
# Tamanho maximo para documento SEM sinal linguistico (acervo generico).
PDF_SEM_SINAL_MAX_BYTES = 3_000_000

# Sinais de trimestre/ano ja normalizados (usados pelos hints de periodo).
TRIMESTRE_PALAVRA = {"first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4",
                     "primeiro": "Q1", "segundo": "Q2", "terceiro": "Q3", "quarto": "Q4"}
_ORDINAL_RE = re.compile(r"\b(" + "|".join(TRIMESTRE_PALAVRA) + r")[\s\-]+quarter\b")

PERIODO_PATTERNS = (
    (re.compile(r"\b([1-4])q\s?(\d{2})\b"), "q_ano"),        # 1q26 / 1q 26 / 3q25
    (re.compile(r"\bq\s?([1-4])\s?(20\d{2})\b"), "q_ano2"),  # q1-2026 / q1 2026
    (re.compile(r"\b([1-4])t\s?(\d{2})\b"), "t_ano"),        # 1t26 / 2t25 (padrao local BR)
    (re.compile(r"\b(20\d{2})\s?([1-4])t\b"), "ano_t"),      # 2025 3t
    (re.compile(r"\b(20\d{2})\s?q([1-4])\b"), "ano_q"),      # 2025 Q3
)


def periodo_do_nome(nome: str) -> tuple[str, str] | None:
    """(ano, trimestre) a partir do nome normalizado. Trimestre '' quando so ha ano.

    Cobre 1T26, 3Q25, q2-2026, '2025 3T', '2025 Q3' e 'fourth-quarter-2025'.
    """
    texto = normalizar_nome(nome)
    achado_ano = re.search(r"\b(20\d{2})\b", texto)
    ano = achado_ano.group(1) if achado_ano else None
    for padrao, forma in PERIODO_PATTERNS:
        achado = padrao.search(texto)
        if not achado:
            continue
        if forma == "q_ano":
            return f"20{achado.group(2)}", f"Q{achado.group(1)}"
        if forma == "q_ano2":
            return achado.group(2), f"Q{achado.group(1)}"
        if forma == "t_ano":
            return f"20{achado.group(2)}", f"Q{achado.group(1)}"
        if forma == "ano_t":
            return achado.group(1), f"Q{achado.group(2)}"
        return achado.group(1), f"Q{achado.group(2)}"  # ano_q
    # 'fourth-quarter-2025', '1o trimestre 2026'
    ordinal = _ORDINAL_RE.search(texto)
    if ordinal and ano:
        return ano, TRIMESTRE_PALAVRA[ordinal.group(1)]
    return (ano, "") if ano else None


# --------------------------------------------------------------------------
# 3) moeda (prioriza USD quando ha versao em dolar)
# --------------------------------------------------------------------------
USD_RE = re.compile(r"\b(us\s?dollars?|usd|dolars?|dolares?|dollars?)\b")
BRL_RE = re.compile(r"\b(reais|real\w*|r\s?dollars?|brl|portugues)\b")


def moeda_do_nome(nome: str) -> str | None:
    """'US$'/'(em dolar)' -> USD;  'R$'/'reais'/'portugues' -> BRL.

    BRL vence em caso de conflito: 'R$' se normaliza para 'r dollar', que casaria
    com o padrao de USD e faria a fonte brasileira passar por dolar.
    """
    texto = normalizar_nome(nome)
    if BRL_RE.search(texto):
        return "BRL"
    if USD_RE.search(texto):
        return "USD"
    return None


# --------------------------------------------------------------------------
# 4) decisao final (usada pelo ETL)
# --------------------------------------------------------------------------
def classificar_documento(nome: str, tamanho_bytes: int | None = None) -> tuple[bool, str]:
    """(deve_parsear, motivo) para o nome de um PDF/planilha."""
    texto = normalizar_nome(nome)
    if not texto:
        return False, "nome vazio"
    if SKIP_RE.search(texto):
        achado = SKIP_RE.search(texto)
        return False, f"narrativo ('{achado.group(1)}')"
    if ALLOW_RE.search(texto):
        achado = ALLOW_RE.search(texto)
        return True, f"numerico ('{achado.group(1)}')"
    if tamanho_bytes is not None and tamanho_bytes >= PDF_SEM_SINAL_MAX_BYTES:
        return False, f"sem sinal e {tamanho_bytes // 1000}KB"
    return True, "sem sinal, tamanho ok"


def deve_parsear_documento(caminho: Path) -> tuple[bool, str]:
    try:
        tamanho = caminho.stat().st_size
    except OSError:
        return False, "arquivo inacessivel"
    return classificar_documento(caminho.name, tamanho)
