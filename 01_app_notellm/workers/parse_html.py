"""Parser de HTML (comunicados da SEC / 6-K) reaproveitando a heuristica de frase.

Comunicado de resultado de emissor estrangeiro chega como 6-K em HTML, nao como
PDF. O texto e' o mesmo formato do PDF, entao a extracao por ancora+pares do
`workers.parse_pdf` serve aqui — nao reescrever as regex.
"""
from __future__ import annotations

import html as html_lib
import re
from pathlib import Path

from workers.parse_pdf import (extract_sentence2_figures,  # noqa: F401
                               extract_sentence_figures, extract_sentence3_figures)
from workers.parse_tab import RawExtraction

BLOCO = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
TAGS = re.compile(r"<[^>]+>")
# separador de celula: ESPACO, nao "|" — os rotulos das regex de frase aceitam
# [\w\s()/,&.'-] e um pipe quebraria "Net income | was $4.0 billion".
CELULA = re.compile(r"</(td|th)>", re.IGNORECASE)
NOVA_LINHA = re.compile(r"</(tr|p|div|br|h[1-6])\s*>", re.IGNORECASE)

# "third quarter of 2026", "3Q26", "Q3 2026", "1T26"
_PERIODO_TEXTO = re.compile(
    r"(?:(first|second|third|fourth)\s+quarter\s+(?:of\s+)?(20\d{2}))"
    r"|(?:\b([1-4])Q\s?(\d{2})\b)"          # 3Q26 (ano de 2 digitos)
    r"|(?:\bQ([1-4])\s+(20\d{2})\b)"
    r"|(?:\b([1-4])T\s?(\d{2})\b)", re.IGNORECASE)
_ORDINAL = {"first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4"}


_MESES = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
          "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
          "december": 12}
# "As of June 30, 2026", "Three months ended June 30, 2026", "30 June 2026"
_DATA_SEM = re.compile(
    r"(?:as\s+of\s+|months?\s+ended\s+|period\s+ended\s+)?"
    r"([a-z]+)\s+(\d{1,2}),\s*(20\d{2})", re.IGNORECASE)
_TRIM_DE_MES = {"01": "Q1", "02": "Q1", "03": "Q1", "04": "Q2", "05": "Q2", "06": "Q2",
                "07": "Q3", "08": "Q3", "09": "Q3", "10": "Q4", "11": "Q4", "12": "Q4"}


def _periodo_de_data(mes_nome: str, ano: str) -> tuple[str, str] | None:
    mes = _MESES.get(mes_nome.lower())
    if not mes:
        return None
    return ano, _TRIM_DE_MES[f"{mes:02d}"]


def periodo_do_texto(linhas: list[str]) -> tuple[str, str] | None:
    """(ano, trimestre) citado no corpo do comunicado — o nome do 6-K não tem período."""
    for linha in linhas[:80]:
        achado = _PERIODO_TEXTO.search(linha)
        if not achado:
            continue
        ordinal, ano_palavra, q_num, q_ano, q_esp_num, q_esp_ano, t_num, t_ano = \
            achado.groups()
        if ordinal:
            return ano_palavra, _ORDINAL[ordinal.lower()]
        if q_num:
            return f"20{q_ano}", f"Q{q_num}"
        if q_esp_num:
            return q_esp_ano, f"Q{q_esp_num}"
        if t_num:
            return f"20{t_ano}", f"Q{t_num}"
    # formato dos comunicados da SEC: "As of June 30, 2026" / "months ended March 31, 2026"
    for linha in linhas[:400]:
        achado = _DATA_SEM.search(linha)
        if achado:
            achado_data = _periodo_de_data(achado.group(1), achado.group(3))
            if achado_data:
                return achado_data
    return None


def html_para_linhas(bruto: str) -> list[str]:
    """HTML -> linhas de texto, quebrando em celula/linha de tabela."""
    sem_bloco = BLOCO.sub(" ", bruto)
    com_celula = CELULA.sub(" ", sem_bloco)
    com_linha = NOVA_LINHA.sub("\n", com_celula)
    texto = TAGS.sub("", com_linha)
    texto = html_lib.unescape(texto)
    linhas = []
    for bruta in texto.splitlines():
        limpa = " ".join(bruta.split())
        if limpa:
            linhas.append(limpa)
    return linhas


def parse_html(path: Path) -> list[RawExtraction]:
    """Extracoes de um comunicado HTML usando as mesmas ancoras do parser de PDF."""
    try:
        bruto = Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    linhas = html_para_linhas(bruto)
    if not linhas:
        return []

    from workers.parse_pdf import doc_period_hint
    # periodo: 1) nome do arquivo  2) citado no corpo  3) SEC: campo reportDate
    per = doc_period_hint(path) or periodo_do_texto(linhas)
    achados: dict[tuple[str, str], RawExtraction] = {}
    for extrator in (extract_sentence_figures, extract_sentence2_figures,
                     extract_sentence3_figures):
        try:
            if extrator is extract_sentence2_figures:
                res = extrator(linhas, path.name, per[0] if per else None)
            else:
                res = extrator(linhas, path.name, per)
        except Exception:
            continue
        for e in res:
            chave = (e.rubrica, e.periodo)
            if chave not in achados or e.confianca > achados[chave].confianca:
                achados[chave] = e
    return list(achados.values())
