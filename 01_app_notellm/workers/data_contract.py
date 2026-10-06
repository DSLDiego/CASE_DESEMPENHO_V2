"""Contrato de dados: valida tipos, nulos e dominios das tabelas de fato.

Uma carga errada nao quebra o ETL (o de-para e a plausibilidade ja filtram muita
coisa), mas deixa numero invalido no banco e na matriz. O contrato roda ao fim de
cada execucao e aponta a violacao com a linha exata, em vez de descoberta casual
depois.

Regras por coluna: tipo, obrigatoriedade e dominio. Nao e um schemarigido de
colunas novas — e uma lista de invariantes que, se quebrada, muda o sentido do
numero (ex.: receita negativa, confianca acima de 1, periodo mal formado).
"""
from __future__ import annotations

import re
from typing import Any

PERIODO_RE = re.compile(r"^20\d{2}Q[1-4]$")
# Na tabela operacional o periodo tambem pode ser ANUAL ("2024A"): e de la que vem a
# ancora de efetivo (9 registros na base real). O escopo trimestral da PoC vale para
# a tabela financeira, nao para a operacional.
PERIODO_TRIM_OU_ANUAL_RE = re.compile(r"^(20\d{2}Q[1-4]|20\d{2}A)$")
MOEDAS = ("USD", "BRL")

# coluna -> (tipo python, obrigatoria?, dominio ou None, descricao do dominio)
CONTRATO_FINANCEIRO: dict[str, tuple[str, bool, Any, str]] = {
    "nome_empresa": ("texto", True, None, "nome da empresa"),
    "periodo": ("texto", True, PERIODO_RE, "período no formato 20xxQ1..Q4"),
    "rubrica_padronizada": ("texto", True, None, "rubrica canônica"),
    "valor": ("numero", True, None, "valor numérico"),
    "moeda": ("texto", True, MOEDAS, "moeda de apresentação (USD ou BRL)"),
    "confianca": ("numero", False, (0.0, 1.0), "confiança entre 0 e 1"),
    "id_fonte": ("inteiro", False, None, "fonte que originou o fato"),
}

CONTRATO_OPERACIONAL: dict[str, tuple[str, bool, Any, str]] = {
    "nome_empresa": ("texto", True, None, "nome da empresa"),
    "periodo": ("texto", True, PERIODO_TRIM_OU_ANUAL_RE,
                 "período trimestral (20xxQn) ou anual (20xxA)"),
    "indicador": ("texto", True, None, "indicador operacional"),
    "valor": ("numero", True, None, "valor numérico"),
    "unidade_medida": ("texto", False, None, "unidade (kboed, %, x, pessoas)"),
}

# Rubricas de resultado que nao fazem sentido negativas.
NUNCA_NEGATIVAS = ("RECEITA_LIQUIDA", "LUCRO_BRUTO", "EBITDA_AJUSTADO", "FCO")
# Sinal forcado pela convencao do projeto (custo reduz, uso de caixa e positivo).
CONVENCAO_SINAL = {"DESPESA_OPERACIONAL": "negativo", "CAPEX": "positivo"}


def _viola(valor: Any, tipo: str, obrigatoria: bool, dominio: Any) -> str | None:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return "obrigatoria mas vazia" if obrigatoria else None
    if tipo == "numero":
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return f"esperava numero, veio {type(valor).__name__}"
        return _checar_dominio(valor, dominio)
    if tipo == "inteiro":
        if isinstance(valor, bool) or not isinstance(valor, int):
            return f"esperava inteiro, veio {type(valor).__name__}"
        return _checar_dominio(valor, dominio)
    if not isinstance(valor, str):
        return f"esperava texto, veio {type(valor).__name__}"
    return _checar_dominio(valor, dominio)


def _checar_dominio(valor: Any, dominio: Any) -> str | None:
    """Regra de dominio: padrao (regex), intervalo (min,max) ou lista de valores."""
    if dominio is None:
        return None
    if hasattr(dominio, "match"):
        return None if dominio.match(valor) else f"fora do padrao ({dominio.pattern})"
    if isinstance(dominio, tuple) and len(dominio) == 2 \
            and all(isinstance(x, (int, float)) for x in dominio):
        lo, hi = dominio
        return None if lo <= valor <= hi else f"fora do intervalo [{lo}, {hi}]"
    if isinstance(dominio, (tuple, list)):
        return None if valor in dominio else f"valor '{valor}' fora de {list(dominio)}"
    return None


def _checar(conn, tabela: str, contrato: dict[str, tuple[str, bool, Any, str]],
            limite: int = 20_000) -> list[dict[str, Any]]:
    """Valida cada linha da tabela contra o contrato.

    Sem filtro `WHERE coluna IS NULL`: ele excluiria justamente as linhas cujo
    problema é um VALOR inválido (período '26Q2', confiança 1.7), que é o caso
    mais importante. O limite é só para não varrer tabela gigante.
    """
    colunas = [r["name"] for r in conn.execute(f"PRAGMA table_info({tabela})")]
    alvo = [c for c in contrato if c in colunas]
    if not alvo:
        return []
    violacoes: list[dict[str, Any]] = []
    sql = (f"SELECT rowid AS _row, {', '.join(alvo)} FROM {tabela} LIMIT {int(limite)}")
    for linha in conn.execute(sql).fetchall():
        for coluna, (tipo, obrigatoria, dominio, desc) in contrato.items():
            if coluna not in alvo:
                continue
            problema = _viola(linha[coluna], tipo, obrigatoria, dominio)
            if problema:
                violacoes.append({"tabela": tabela, "linha": linha["_row"],
                                  "coluna": coluna, "valor": linha[coluna],
                                  "problema": problema, "regra": desc})
    return violacoes


def checar_dominio_financeiro(conn, limite: int = 200) -> list[dict[str, Any]]:
    """Invariantes que dependem do VALOR (sinal e plausibilidade de negócio)."""
    problemas: list[dict[str, Any]] = []
    for rubrica, negativa in ((r, False) for r in NUNCA_NEGATIVAS):
        if negativa:
            continue
        for linha in conn.execute(
                "SELECT rowid AS _row, nome_empresa, periodo, valor FROM tb_fato_financeiro "
                "WHERE rubrica_padronizada = ? AND valor IS NOT NULL AND valor <= 0 LIMIT ?",
                (rubrica, limite)).fetchall():
            problemas.append({
                "tabela": "tb_fato_financeiro", "linha": linha["_row"],
                "coluna": "valor", "valor": linha["valor"],
                "problema": f"{rubrica} nao pode ser <= 0",
                "regra": "receita/EBITDA/lucro/FCO sao quantities positivas"})
    for rubrica, esperado in CONVENCAO_SINAL.items():
        # violacao quando o sinal e' o CONTRARIO ao esperado:
        #   esperado "negativo" -> viola se valor >= 0
        #   esperado "positivo" -> viola se valor < 0
        cond = "valor >= 0" if esperado == "negativo" else "valor < 0"
        for linha in conn.execute(
                "SELECT rowid AS _row, nome_empresa, periodo, valor FROM tb_fato_financeiro "
                f"WHERE rubrica_padronizada = ? AND valor IS NOT NULL AND {cond} LIMIT ?",
                (rubrica, limite)).fetchall():
            problemas.append({
                "tabela": "tb_fato_financeiro", "linha": linha["_row"],
                "coluna": "valor", "valor": linha["valor"],
                "problema": f"{rubrica} com sinal fora da convencao ({esperado})",
                "regra": "convenção de sinal do projeto"})
    return problemas


def rodar_contrato(db, limite_por_coluna: int = 100) -> dict[str, Any]:
    """Executa o contrato nas tabelas de fato. Devolve resumo + violações."""
    violacoes: list[dict[str, Any]] = []
    with db.connect() as conn:
        violacoes += _checar(conn, "tb_fato_financeiro", CONTRATO_FINANCEIRO)
        violacoes += _checar(conn, "tb_fato_operacional", CONTRATO_OPERACIONAL)
        violacoes += checar_dominio_financeiro(conn, limite_por_coluna)
        with db.connect() as c2:
            contagens = {
                "fatos_financeiro": c2.execute(
                    "SELECT COUNT(*) FROM tb_fato_financeiro").fetchone()[0],
                "fatos_operacional": c2.execute(
                    "SELECT COUNT(*) FROM tb_fato_operacional").fetchone()[0],
            }
    por_coluna: dict[str, int] = {}
    for v in violacoes:
        chave = f"{v['tabela']}.{v['coluna']}"
        por_coluna[chave] = por_coluna.get(chave, 0) + 1
    return {"ok": not violacoes,
            "violacoes": len(violacoes),
            "por_coluna": por_coluna,
            "detalhe": violacoes[:50],
            "fatos_verificados": contagens}