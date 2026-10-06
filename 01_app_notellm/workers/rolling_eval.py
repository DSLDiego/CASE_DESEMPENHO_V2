"""M3.14/M10.9 — avaliação honesta do que o pipeline projeta.

Dois cortes, propositamente separados:

1. **Erro real das projeções já gravadas** (M10.9): tb_projecao guarda o que foi
   projetado quando o fato ainda não existia (ou era a melhor estimativa). Anos
   depois há o fato: então medimos retroativamente se a previsão bateu com o
   publicado. O percentual de coberturas ("o valor real caiu dentro do IC95?")
   é o teste de calibragem mais honesto que dá para fazer sem série sintética.
   Os ICs são ~95% → se a cobertura real sai em 50%, o intervalo está estreito;
   se sai em 99%, largo demais. Nem um nem outro é "melhor": o IC não é
   relatório de auditoria, o alvo é próximo do nominal.

2. **Rolling-origin por método** (M3.14): referente de backtesting que não
   depende de um único corte fixo. Com origens t variando ao longo da série,
   medimos MAE/RMSE/MAPE de cada candidato do perfil (FLUXO/ESTOQUE) no mesmo
   trimestre-alvo — e só com isso é possível dizer "Holt bate sazonal na minha
   base" em vez de "virou verdade no ano de 2024".
"""
from __future__ import annotations

import math
from statistics import mean
from typing import Any

from models.database import DatabaseManager
from workers.forecast import METODOS, candidatos_rubrica


def erro_real_das_projecoes(db: DatabaseManager | None = None) -> dict[str, Any]:
    """Compara tb_projecao com o fato que apareceu depois (M10.9).

    Para cada projeção cujo período projetado agora TEM fact real: erro =
    real - previsto; MAPE quando o real != 0; e "coberto" = real caiu dentro do
    intervalo. Resultado por método e geral. `coberto` é a medida-chave — é a
    única que o público honesto consegue interpretar sem saber estatística.
    """
    db = db or DatabaseManager()
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT p.nome_empresa, p.rubrica_padronizada, p.periodo_projetado,"
            " p.valor AS previsto, p.intervalo_inf AS inf, p.intervalo_sup AS sup,"
            " p.metodo, p.horizonte, p.confianca,"
            " f.valor AS real"
            " FROM tb_projecao p"
            " JOIN tb_fato_financeiro f"
            "  ON f.nome_empresa = p.nome_empresa"
            " AND f.rubrica_padronizada = p.rubrica_padronizada"
            " AND f.periodo = p.periodo_projetado").fetchall()]
    por_metodo: dict[str, dict[str, Any]] = {}
    cobertos = 0
    erros: list[float] = []
    mapes: list[float] = []
    detalhe: list[dict[str, Any]] = []
    for r in rows:
        real = float(r["real"])
        previsto = float(r["previsto"])
        erro = real - previsto
        coberto = (r["inf"] is not None and r["sup"] is not None
                   and float(r["inf"]) <= real <= float(r["sup"]))
        cobertos += int(coberto)
        erros.append(abs(erro))
        if real:
            mapes.append(abs(erro / real) * 100)
        agg = por_metodo.setdefault(r["metodo"],
                                    {"n": 0, "mae": [], "mape": [], "cobertos": 0})
        agg["n"] += 1
        agg["mae"].append(abs(erro))
        if real:
            agg["mape"].append(abs(erro / real) * 100)
        agg["cobertos"] += int(coberto)
        detalhe.append({"empresa": r["nome_empresa"], "rubrica": r["rubrica_padronizada"],
                        "periodo": r["periodo_projetado"], "previsto": previsto,
                        "real": real, "erro": round(erro, 4),
                        "coberto": coberto, "metodo": r["metodo"]})
    for m, agg in por_metodo.items():
        agg["mae"] = round(mean(agg["mae"]), 4) if agg["mae"] else None
        agg["mape"] = round(mean(agg["mape"]), 2) if agg["mape"] else None
        agg["cobertura"] = round(agg["cobertos"] / agg["n"], 3) if agg["n"] else None
    n = len(rows)
    return {"total": n,
            "cobertura_geral": round(cobertos / n, 3) if n else None,
            "mae_geral": round(mean(erros), 4) if erros else None,
            "mape_geral": round(mean(mapes), 2) if mapes else None,
            "por_metodo": por_metodo,
            "detalhe": sorted(detalhe, key=lambda d: abs(d["erro"]), reverse=True)[:30],
            "nota": "projeção ≠ fato: quando o real aparece, comparamos de verdade"}


def rolling_method_eval(db: DatabaseManager | None = None, empresa: str | None = None,
                        rubrica: str | None = None) -> dict[str, Any]:
    """Rolling-origin: testa cada método em origens t ao longo da história (M3.14).

    Janela maior que o backtest fixo do projeto: em cada origem t >= min_train,
    treina na série até t e prevê h=1; no fim agrega MAE/RMSE/MAPE por método.
    É "método x MSE" na mesma base para todas as candidatas — a escolha deixa de
    ser fotografia de um trimestre e vira frequência dos erros.
    """
    db = db or DatabaseManager()
    resultado: dict[str, Any] = {"avaliadas": 0, "geral": {}, "series": []}
    # agrega global: (serie_total) → para cada metodo → listas de erros
    por_metodo: dict[str, dict[str, list[float]]] = {}

    def _eval_serie(emp: str, rub: str, valores: list[float | None]) -> None:
        s = [float(v) for v in valores if v is not None]
        if len(s) < 6:  # mínimo para tentar medir; abaixo fica o método de regra
            return
        for mi, nome in enumerate(candidatos_rubrica(rub)):
            fn = METODOS[nome]
            pares = []   # (erro, real) por origem — mesma posição, sem dessincronizar
            for t in range(4, len(s)):      # origem: treina em s[:t], prevê s[t]
                try:
                    p = fn(s[:t], 1, 4)
                except Exception:           # método não aplicável a esse corte
                    continue
                if p:
                    pares.append((s[t] - p[0], s[t]))
            if not pares:
                continue
            erros = [e for e, _ in pares]
            reais = [r for _, r in pares]
            agg = por_metodo.setdefault(nome, {"erros": [], "reais": []})
            agg["erros"].extend(erros)
            agg["reais"].extend(reais)
            resultado["series"].append({"empresa": emp, "rubrica": rub, "metodo": nome,
                                        "mae": round(mean(abs(e) for e in erros), 4),
                                        "n": len(erros)})
            resultado["avaliadas"] += 1

    with db.connect() as conn:
        pares = conn.execute(
            "SELECT DISTINCT nome_empresa, rubrica_padronizada FROM tb_fato_financeiro"
            " ORDER BY nome_empresa, rubrica_padronizada").fetchall()
    for r in pares:
        if empresa and r["nome_empresa"] != empresa:
            continue
        if rubrica and r["rubrica_padronizada"] != rubrica:
            continue
        from workers.forecast_run import series_do_banco
        _, valores = series_do_banco(db, r["nome_empresa"], r["rubrica_padronizada"])
        _eval_serie(r["nome_empresa"], r["rubrica_padronizada"], valores)

    geral: dict[str, dict[str, Any]] = {}
    for nome, agg in por_metodo.items():
        erros, reais = agg["erros"], agg["reais"]
        mae = mean(abs(e) for e in erros) if erros else None
        rmse = math.sqrt(mean(e * e for e in erros)) if erros else None
        pares_mape = [abs(e / r) * 100 for e, r in zip(erros, reais) if r]
        geral[nome] = {"mae": round(mae, 4) if mae is not None else None,
                       "rmse": round(rmse, 4) if rmse is not None else None,
                       "mape": round(mean(pares_mape), 2) if pares_mape else None,
                       "n": len(erros)}
    resultado["geral"] = geral
    resultado["nota"] = ("MAE antes do RMSE: RMSE penaliza fortemente um erro "
                         "grande — por isso o par ajuda a separar método"
                         " 'resiliente' de método 'normalmente bom, às vezes"
                         " catastrófico'")
    return resultado
