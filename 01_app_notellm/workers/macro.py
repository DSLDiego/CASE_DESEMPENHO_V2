"""M3.13/M10.8 — cenários com premissa de Brent e câmbio, e intervalo que
responde à covariância dos fatores.

Projeção pura de série não mede o petróleo: a receita é uma função de Brent e
câmbio. Aqui tratamos Brent/PTAX como fatores e estimamos a sensibilidade (β) de
cada série a eles. O cenário aplica essa sensibilidade à premissa e, crucialmente,
o intervalo se abre quando a premissa é incerta — não é só a média que muda.

Intervalo (M10.8): σ_cenário² = σ_base² + β_b²·σ_Δb² + β_f²·σ_Δf²
                                   + 2·β_b·β_f·cov(Δb, Δf)
A largura do IC depende de covariância entre os próprios fatores: se Brent e
câmbio andam juntos (correlação), a receita pode descolar mais da previsão — e o
intervalo reflete isso. Sem o termo cruzado, o IC seria sistematicamente estreito.

Dados de macro: o repositório não tem feed externo garantido, então carregamos
uma série-base documentada como premissa (atualizável via tabela). É explicitamente
"premissa de cenário", nunca número de um fato.
"""
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from models.database import DatabaseManager

# Premissa de mercado (média trimestral aproximada de Brent e PTAX).
# Serve de base para os cenários; é número assumido, não coletado —
# por isso fica isolado e documentado, pronto para trocar por uma API live.
BRENT_BASE: dict[str, float] = {
    "2023Q1": 82.0, "2023Q2": 78.0, "2023Q3": 87.0, "2023Q4": 81.0,
    "2024Q1": 83.0, "2024Q2": 85.0, "2024Q3": 80.0, "2024Q4": 75.0,
    "2025Q1": 76.0, "2025Q2": 68.0, "2025Q3": 70.0, "2025Q4": 74.0,
    "2026Q1": 70.0, "2026Q2": 68.0,
}
PTAX_BASE: dict[str, float] = {
    "2023Q1": 5.20, "2023Q2": 4.95, "2023Q3": 4.85, "2023Q4": 4.95,
    "2024Q1": 4.95, "2024Q2": 5.20, "2024Q3": 5.45, "2024Q4": 5.70,
    "2025Q1": 5.80, "2025Q2": 5.60, "2025Q3": 5.45, "2025Q4": 5.40,
    "2026Q1": 5.30, "2026Q2": 5.20,
}

# Premissa do cenário é um choque PERCENTUAL sobre o último valor do fator.
CHOQUES_BRENT = {"pessimista": -0.15, "base": 0.0, "otimista": +0.15}
CHOQUES_PTAX = {"pessimista": +0.10, "base": 0.0, "otimista": -0.10}


def _serie_macro(db: DatabaseManager, fator: str) -> dict[str, float]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT periodo, valor FROM tb_macro_fator WHERE fator = ? ORDER BY periodo",
            (fator,)).fetchall()
    if rows:
        return {r["periodo"]: float(r["valor"]) for r in rows}
    return dict(BRENT_BASE if fator == "brent" else PTAX_BASE)


def carregar_base_macro(db: DatabaseManager | None = None) -> dict[str, int]:
    """Grava a série-base na tabela (vazio -> base). Não sobrescreve dado manual."""
    db = db or DatabaseManager()
    with db.connect() as conn:
        existe = conn.execute("SELECT COUNT(*) c FROM tb_macro_fator").fetchone()["c"]
        if existe:
            return {"gravados": 0}
        n = 0
        for periodo, v in BRENT_BASE.items():
            conn.execute("INSERT INTO tb_macro_fator (periodo, fator, valor) VALUES (?, 'brent', ?)",
                         (periodo, v))
            n += 1
        for periodo, v in PTAX_BASE.items():
            conn.execute("INSERT INTO tb_macro_fator (periodo, fator, valor) VALUES (?, 'ptax', ?)",
                         (periodo, v))
            n += 1
        conn.commit()
    return {"gravados": n}


def _retorno_log(periodos: list[str], valores: dict[str, float]) -> dict[str, float]:
    """Δ% (variação percentual) entre trimestres consecutivos."""
    out = {}
    for ant, atual in zip(periodos, periodos[1:]):
        v0, v1 = valores.get(ant), valores.get(atual)
        if v0 and v1:
            out[atual] = (v1 / v0) - 1.0
    return out


def sensibilidade(db: DatabaseManager, empresa: str, rubrica: str
                  ) -> dict[str, Any]:
    """β de crescimento da série vs crescimento de Brent e PTAX (OLS simples).

    O β responde: "se o Brent subir 10% num trimestre, a receita sobe/desce X%?".
    Com poucos pares (ou série de receitas sem variação), o β cai para 0 com
    honestidade — é melhor integrar um cenário neutro do que números confiados.
    """
    from workers.forecast_run import series_do_banco
    periodos, valores = series_do_banco(db, empresa, rubrica)
    serie = {p: float(v) for p, v in zip(periodos, valores) if v is not None}
    brent = _serie_macro(db, "brent")
    ptax = _serie_macro(db, "ptax")
    periodos_orden = sorted(set(serie) | set(brent) | set(ptax))
    ret_serie = _retorno_log(periodos_orden, serie)
    ret_b = _retorno_log(periodos_orden, brent)
    ret_f = _retorno_log(periodos_orden, ptax)
    pares = [p for p in ret_serie if p in ret_b and p in ret_f]
    if len(pares) < 4:
        return {"beta_brent": 0.0, "beta_ptax": 0.0, "cov_brent_ptax": 0.0,
                "sigma_brent": 0.0, "sigma_ptax": 0.0, "pares": len(pares),
                "motivo": "serie curta: cenário neutro"}
    xs_b = [ret_b[p] for p in pares]
    xs_f = [ret_f[p] for p in pares]
    ys = [ret_serie[p] for p in pares]

    def beta(y: list[float], x: list[float]) -> float:
        mx, my = mean(x), mean(y)
        var = sum((v - mx) ** 2 for v in x)
        return sum((v - mx) * (yv - my) for v, yv in zip(x, y)) / var if var else 0.0

    cov = mean([a * b for a, b in zip(xs_b, xs_f)]) - mean(xs_b) * mean(xs_f)
    return {"beta_brent": round(beta(ys, xs_b), 4),
            "beta_ptax": round(beta(ys, xs_f), 4),
            "cov_brent_ptax": round(cov, 6),
            "sigma_brent": round(pstdev(xs_b), 4),
            "sigma_ptax": round(pstdev(xs_f), 4),
            "pares": len(pares), "motivo": "ols nos crescimentos trimestrais"}


def cenarios(db: DatabaseManager, empresa: str, rubrica: str,
             horizonte: int = 3) -> dict[str, Any]:
    """Cenários Brent/FX sobre a projeção base, com IC covariância-sensível (M10.8)."""
    db = db or DatabaseManager()
    from workers.forecast_run import series_do_banco, run_forecast
    from models.repositories import ProjectionRepository
    periodos, valores = series_do_banco(db, empresa, rubrica)
    if not periodos:
        return {"empresa": empresa, "rubrica": rubrica, "cenarios": [],
                "sensibilidade": sensibilidade(db, empresa, rubrica),
                "erro": "série vazia"}
    # garante que a projeção base existe antes de ler tb_projecao
    run_forecast(db, horizonte=horizonte, empresas=[empresa], rubricas=[rubrica])
    rows = [r for r in ProjectionRepository(db).listar()
            if r["nome_empresa"] == empresa and r["rubrica_padronizada"] == rubrica]
    if not rows:
        return {"empresa": empresa, "rubrica": rubrica, "cenarios": [],
                "sensibilidade": sensibilidade(db, empresa, rubrica),
                "erro": "sem projeção base"}
    sens = sensibilidade(db, empresa, rubrica)

    def _ajuste(bb: float, ff: float, row: dict) -> tuple[float, float, float]:
        # mudança percentual da premissa aplicada ao valor base
        base = float(row["valor"])
        b = sens["beta_brent"]
        f = sens["beta_ptax"]
        delta = b * bb + f * ff
        cen = base * (1.0 + delta)
        # IC covariância-sensível: a faixa abre com o risco que os dois fatores
        # trazem juntos — choques correlacionados não se cancelam.
        sigma_base = max((float(row.get("intervalo_sup") or base) - base) / 1.96, 0.0)
        var_extra = (b * sens["sigma_brent"]) ** 2 + (f * sens["sigma_ptax"]) ** 2
        if sens["pares"] >= 4:
            var_extra += 2 * b * f * sens["cov_brent_ptax"]
        h = int(row.get("horizonte") or 1)
        sigma_cen = math.sqrt(max(sigma_base ** 2 + var_extra, 0.0))
        half = 1.96 * sigma_cen * math.sqrt(max(h, 1))
        return round(cen, 4), round(cen - half, 4), round(cen + half, 4)

    saida = []
    for row in sorted(rows, key=lambda r: r["periodo_projetado"]):
        cen = {}
        for nome in ("pessimista", "base", "otimista"):
            v, lo, hi = _ajuste(CHOQUES_BRENT[nome], CHOQUES_PTAX[nome], row)
            cen[nome] = {"valor": v, "inf": lo, "sup": hi}
        # spread: o quanto o cenário mexe no intervalo em relação ao base
        spread = round(cen["otimista"]["sup"] - cen["pessimista"]["inf"], 4)
        saida.append({"periodo": row["periodo_projetado"], "metodo": row["metodo"],
                      "base": cen["base"], "pessimista": cen["pessimista"],
                      "otimista": cen["otimista"], "spread": spread,
                      "premissa": {"brent": CHOQUES_BRENT["base"], "ptax": CHOQUES_PTAX["base"]}})
    return {"empresa": empresa, "rubrica": rubrica, "sensibilidade": sens,
            "cenarios": saida,
            "choques": {"brent": CHOQUES_BRENT, "ptax": CHOQUES_PTAX},
            "nota": "cenários são premissa macro; não são fato publicado"}
