"""Worker forecast (orquestrador): le as series do banco e grava as projecoes.

Regra de ouro: projecao NUNCA entra em tb_fato_financeiro. Fica em tb_projecao,
com metodo, intervalo e confianca — o painel mostra sempre rotulado como projecao.
"""
from __future__ import annotations

from typing import Any

from models.database import DatabaseManager
from models.repositories import ProjectionRepository
from workers.forecast import HORIZONTE_MAX, MIN_PONTOS, projetar_serie

# Antes: lista fixa de 7 rubricas, que deixava FCL, DIVIDA_BRUTA e
# DESPESA_OPERACIONAL sem projecao mesmo com serie suficiente. Agora o criterio e
# "toda rubrica financeira com dados", e a exclusao e sempre explicita.
RUBRICAS_PROJETAveis = ["RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO",
                       "FCO", "DIVIDA_LIQUIDA", "CAPEX", "LUCRO_BRUTO"]
# Rubricas que fazem sentido projetar; None = todas. Exclusoes sao por Justificativa.
RUBRICAS_EXCLUIDAS: dict[str, str] = {}


def series_do_banco(db: DatabaseManager, empresa: str, rubrica: str) -> tuple[list[str], list[float | None]]:
    """(periodos, valores) ordenados; inclui os trimestres sem dado como None."""
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT periodo, valor FROM tb_fato_financeiro WHERE nome_empresa = ?"
            " AND rubrica_padronizada = ? ORDER BY periodo", (empresa, rubrica)).fetchall()]
    if not rows:
        return [], []
    periodos = [r["periodo"] for r in rows]
    return periodos, [r["valor"] for r in rows]


def rubricas_do_banco(db: DatabaseManager) -> list[str]:
    """Toda rubrica financeira que tem fato gravado (fonte unica da verdade)."""
    with db.connect() as conn:
        return [r["rubrica_padronizada"] for r in conn.execute(
            "SELECT DISTINCT rubrica_padronizada FROM tb_fato_financeiro "
            "ORDER BY rubrica_padronizada").fetchall()]


def run_forecast(db: DatabaseManager | None = None, horizonte: int = HORIZONTE_MAX,
                 empresas: list[str] | None = None,
                 rubricas: list[str] | None = None) -> dict[str, Any]:
    db = db or DatabaseManager()
    proj = ProjectionRepository(db)
    if rubricas is None:
        rubricas = [r for r in rubricas_do_banco(db) if r not in RUBRICAS_EXCLUIDAS]
    if empresas is None:
        with db.connect() as conn:
            empresas = [r["nome_empresa"] for r in conn.execute(
                "SELECT DISTINCT nome_empresa FROM tb_fato_financeiro ORDER BY nome_empresa").fetchall()]
    resumo = {"series": 0, "projecoes": 0, "ignoradas": 0, "metodos": {},
              "confianca_media": 0.0, "avisos": [], "rubricas": rubricas,
              "cobertura": {}, "excluidas": dict(RUBRICAS_EXCLUIDAS),
              "por_perfil": {}}
    confiancas: list[float] = []
    for empresa in empresas:
        for rubrica in rubricas:
            periodos, valores = series_do_banco(db, empresa, rubrica)
            if not periodos:
                continue
            resultado = projetar_serie(periodos, valores, horizonte, rubrica=rubrica)
            if not resultado.get("valores"):
                resumo["ignoradas"] += 1
                if len(periodos) < MIN_PONTOS:
                    resumo["avisos"].append(
                        f"{empresa}/{rubrica}: só {len(periodos)} trimestre(s) — "
                        f"sazonalidade desativada")
                continue
            resumo["series"] += 1
            resumo["cobertura"][rubrica] = resumo["cobertura"].get(rubrica, 0) + 1
            gravados = proj.salvar(empresa, rubrica, periodos[-1], horizonte, resultado)
            resumo["projecoes"] += gravados
            resumo["metodos"][resultado["metodo"]] = resumo["metodos"].get(resultado["metodo"], 0) + 1
            perfil = resultado.get("perfil")
            if perfil:
                # quantas séries de estoque NÃO foram parar no sazonal (M10.7)
                por_perfil = resumo.setdefault("por_perfil", {})
                chave = f"{perfil}/{resultado['metodo']}"
                por_perfil[chave] = por_perfil.get(chave, 0) + 1
            confiancas.append(resultado["confianca"])
    if confiancas:
        resumo["confianca_media"] = round(sum(confiancas) / len(confiancas), 2)
    return resumo


def cenario(db: DatabaseManager | None = None, empresa: str = "PETROBRAS",
            rubrica: str = "RECEITA_LIQUIDA", horizonte: int = HORIZONTE_MAX) -> dict[str, Any]:
    """Série completa (real + projetado + IC) de uma empresa/rubrica, para o painel."""
    db = db or DatabaseManager()
    return ProjectionRepository(db).serie_com_projezcao(empresa, rubrica)