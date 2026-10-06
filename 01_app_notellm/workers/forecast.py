"""Worker forecast: projecao estatistica de series trimestrais (ate 3 trimestres).

Metodologia (documentada em docs/PLANO_TAREFAS_2000.md, item M3):
1. Serie por empresa x rubrica em YYYYQn; lacunas interpoladas linearmente.
2. Sazonalidade trimestral (k=4) com indices normalizados (soma zero).
3. Tendencia Holt linear com amortecimento (phi) - evita extrapolacao explosiva.
4. O metodo e escolhido por BACKTESTING (MAE/MAPE na janela de validacao) entre:
   sazonal-naive, HW-damped e ultima-observacao. Nada de "a priori".
5. Incerteza: sigma dos erros de backtesting; IC95 = f +- 1,96*sigma*sqrt(h).
6. Confianca baixa quando ha poucos pontos ou sigma alto; a projecao NUNCA
   sobrescreve um fato real (vive em tb_projecao).
"""
from __future__ import annotations

import math
from statistics import mean, pstdev, stdev
from typing import Any, Callable

K = 4                      # trimestres por ano
HORIZONTE_MAX = 3          # requisito: ate 3 trimestres a frente
MIN_PONTOS = 6             # abaixo disso a sazonalidade nao e confiavel
PHI = 0.85                 # amortecimento da tendencia


# ---------------------------------------------------------------- utilitarios
def parse_periodo(p: str) -> tuple[int, int]:
    p = (p or "").upper()
    return int(p[:4]), int(p[-1])


def format_periodo(ano: int, trimestre: int) -> str:
    return f"{ano}Q{trimestre}"


def proximos(periodos: list[str], n: int = HORIZONTE_MAX) -> list[str]:
    """ proximos n trimestres apos o ultimo periodo informado (YYYYQn)."""
    if not periodos:
        return []
    ano, tri = parse_periodo(max(periodos))
    out = []
    for _ in range(n):
        tri += 1
        if tri > K:
            tri, ano = 1, ano + 1
        out.append(format_periodo(ano, tri))
    return out


def _completar(valores: list[float | None]) -> tuple[list[float], int]:
    """Interpola lacunas linearmente. Retorna (serie, nº de lacunas)."""
    n = len(valores)
    serie: list[float | None] = [None if v is None or (isinstance(v, float) and math.isnan(v))
                                 else float(v) for v in valores]
    faltando = sum(1 for v in serie if v is None)
    if faltando == 0:
        return [v for v in serie if v is not None], 0
    conhecidos = [i for i, v in enumerate(serie) if v is not None]
    if not conhecidos:
        return [], faltando
    for i in range(n):
        if serie[i] is None:
            antes = max([j for j in conhecidos if j < i], default=None)
            depois = min([j for j in conhecidos if j > i], default=None)
            if antes is None:
                serie[i] = serie[depois]
            elif depois is None:
                serie[i] = serie[antes]
            else:
                peso = (i - antes) / (depois - antes)
                serie[i] = serie[antes] + peso * (serie[depois] - serie[antes])
    return [v for v in serie if v is not None], faltando


# ------------------------------------------------------------------ metodos
def m_ultima_observacao(serie: list[float], h: int, k: int = K) -> list[float]:
    return [serie[-1]] * h


def m_sazonal_naive(serie: list[float], h: int, k: int = K) -> list[float]:
    if len(serie) < k:
        return [serie[-1]] * h
    return [serie[-k + (i % k)] for i in range(h)]


def m_holt_damped(serie: list[float], h: int, k: int = K, alpha: float = 0.4,
                  beta: float = 0.2, phi: float = PHI) -> list[float]:
    """Holt-Winters aditivo com tendencia amortecida e sazonalidade multiplicativa
    aproximada por indices medios (ratio-to-mean)."""
    n = len(serie)
    if n < k:
        return [serie[-1]] * h
    # 1) indices sazonais: media de (y / media movel de k)
    indices = []
    media_k = mean(serie[:k])
    for i in range(k):
        janela = serie[max(0, i - 1): i + 2] or [serie[i]]
        base = mean([v for v in serie[i:i + k] if v]) or media_k
        indices.append(mean(janela) / base if base else 1.0)
    # 2) nivel e tendencia inicial
    nivel = mean(serie[:k])
    tend = (mean(serie[k:2 * k]) - nivel) / k if n >= 2 * k else 0.0
    # 3) atualizacao
    ajustada = [serie[t] / max(indices[t % k], 1e-9) for t in range(n)]
    for t in range(k, n):
        nivel_novo = alpha * ajustada[t] + (1 - alpha) * (nivel + phi * tend)
        tend = beta * (nivel_novo - nivel) + (1 - beta) * phi * tend
        nivel = nivel_novo
    # 4) projecao
    out = []
    for i in range(1, h + 1):
        acum = sum(phi ** j for j in range(1, i + 1))
        out.append((nivel + acum * tend) * indices[(n + i - 1) % k])
    return out


def m_media_2dp(serie: list[float], h: int, k: int = K) -> list[float]:
    """Poucos dados: repete a media da serie (intervalo = +/- 2 desvios padrao)."""
    m = mean(serie)
    return [m] * h


def m_repetir_15(serie: list[float], h: int, k: int = K) -> list[float]:
    """Um unico dado: repete o valor (intervalo = +/- 15%)."""
    return [serie[-1]] * h


METODOS: dict[str, Callable[[list[float], int, int], list[float]]] = {
    "ULTIMA_OBSERVACAO": m_ultima_observacao,
    "SAZONAL_NAIVE": m_sazonal_naive,
    "HOLT_WINTERS_DAMPED": m_holt_damped,
    "MEDIA_2DP": m_media_2dp,          # regra para series curtas (poucos dados)
    "REPETIR_15": m_repetir_15,        # regra para serie de um unico dado
}

# Candidatos do backtesting, por TIPO de rubrica (M10.7).
#
# Antes o mesmo conjunto de 3 métodos era oferecido para toda rubrica. Isso é errado
# por natureza do dado, não por ajuste fino: Sazonal-Naive pressupõe que o trimestre
# se repete ano a ano, e isso vale para FLUXO (receita, EBITDA, lucro) mas não para
# ESTOQUE (dívida, CAPEX). Dívida líquida não "repete o Q1" — ela carrega saldo.
# Deixar o sazonal competir em estoque é o backtest "ganhando" por acaso: ele
# ganha quando o nível é estável e perde quando a dívida sobe ou cai, misturando
# os dois regimes numa série só.
FLUXO = "fluxo"      # receita, lucro, EBITDA: fluxo do período, sazonal faz sentido
ESTOQUE = "estoque"  # dívida, CAPEX: saldo acumulado, sazonal não se aplica
PERFIL_PADRAO = FLUXO

CANDIDATOS: dict[str, tuple[str, ...]] = {
    FLUXO: ("ULTIMA_OBSERVACAO", "SAZONAL_NAIVE", "HOLT_WINTERS_DAMPED"),
    # Holt-Winters com tendência amortecida ainda modela saldo (nível + tendência);
    # o que se exclui é só o sazonal, que pressupõe ciclo anual.
    ESTOQUE: ("ULTIMA_OBSERVACAO", "HOLT_WINTERS_DAMPED"),
}

# Classificação das rubricas gravadas em tb_fato_financeiro.
RUBRICAS_ESTOQUE = {"DIVIDA_LIQUIDA", "DIVIDA_BRUTA", "CAPEX"}
RUBRICAS_FLUXO = {"RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO", "FCO",
                  "LUCRO_BRUTO", "DESPESA_OPERACIONAL", "FCL"}


def perfil_rubrica(rubrica: str | None) -> str:
    """ESTOQUE ou FLUXO. Rubrica desconhecida cai em FLUXO (o regime mais geral)."""
    if rubrica in RUBRICAS_ESTOQUE:
        return ESTOQUE
    return FLUXO


def candidatos_rubrica(rubrica: str | None) -> tuple[str, ...]:
    return CANDIDATOS[perfil_rubrica(rubrica)]

# Metodos sem backtesting: escolhidos por regra de negocio (poucos dados).
METODOS_REGRA: dict[str, str] = {
    "REPETIR_15": "apenas 1 dado: repete o valor com intervalo de ±15%",
    "MEDIA_2DP": "série curta (<6 pontos): média ± 2 desvios-padrão",
}
POCOS_DADOS = 6      # abaixo disso usa MEDIA_2DP


def _intervalos(metodo: str, serie: list[float], previsto: list[float],
                sigma: float) -> tuple[list[float], list[float]]:
    """Intervalo de predicao conforme o método (regra fixa ou dispersão do erro)."""
    if metodo == "REPETIR_15":
        v = serie[-1]
        # Serie negativa (ex.: despesa operacional, negativa por convencao) invertia
        # o intervalo: inf = v*0.85 ficava MAIOR que sup = v*1.15.
        if v >= 0:
            lo, hi = v * 0.85, v * 1.15
        else:
            lo, hi = v * 1.15, v * 0.85
        return ([round(lo, 4)] * len(previsto), [round(hi, 4)] * len(previsto))
    if metodo == "MEDIA_2DP":
        m = mean(serie)
        sd = stdev(serie) if len(serie) > 1 else 0.0
        return ([round(m - 2 * sd, 4)] * len(previsto), [round(m + 2 * sd, 4)] * len(previsto))
    return ([round(v - 1.96 * sigma * math.sqrt(h + 1), 4) for h, v in enumerate(previsto)],
            [round(v + 1.96 * sigma * math.sqrt(h + 1), 4) for h, v in enumerate(previsto)])


def _mae(erros: list[float]) -> float:
    return sum(abs(e) for e in erros) / len(erros) if erros else float("inf")


def _mape(erros: list[float], reais: list[float]) -> float:
    pares = [(abs(e / r), e) for e, r in zip(erros, reais) if r]
    return mean([p[0] for p in pares]) * 100 if pares else float("inf")


def backtest(serie: list[float], metodo: Callable, k: int = K,
             min_train: int = 4) -> tuple[float, float]:
    """Erros (real - previsto) treinando ate t-h e prevendo h, para h=1..k."""
    erros, reais = [], []
    for h in range(1, min(k, len(serie) - min_train) + 1):
        treino = serie[:len(serie) - h]
        if len(treino) < 2:
            continue
        try:
            previsto = metodo(treino, 1, k)
        except Exception:
            return float("inf"), float("inf")
        if not previsto:
            continue
        erros.append(serie[len(serie) - h] - previsto[0])
        reais.append(serie[len(serie) - h])
    return _mae(erros), _mape(erros, reais)


def projetar(valores: list[float | None], horizonte: int = HORIZONTE_MAX,
              k: int = K, rubrica: str | None = None) -> dict[str, Any]:
    """Projeta uma serie. Retorna metodo, valores, IC95, confianca e avisos.

    Regras de fallback (poucos dados), na ordem:
      1. 1 unico dado  -> REPETIR_15  (repete o valor, intervalo ±15%)
      2. 2 a 5 dados   -> MEDIA_2DP   (média da série, intervalo ±2 desvios-padrão)
      3. >= 6 dados    -> backtesting entre os métodos do PERFIL da rubrica (M10.7)

    `rubrica` decide quais métodos disputam: em estoque (dívida, CAPEX) o
    sazonal é excluído da disputa por não descrever o dado.
    """
    horizonte = max(1, min(int(horizonte), HORIZONTE_MAX))
    candidatos_nomes = candidatos_rubrica(rubrica)
    serie, lacunas = _completar(valores)
    n = len(serie)
    if n < 1:
        return {"metodo": None, "valores": [], "erro": "serie vazia",
                "confianca": 0.0, "sigma": None, "mae": None, "mape": None, "n": n,
                "lacunas": lacunas, "inf": [], "sup": [], "alternativas": []}
    # --- regra 1: um unico dado ---
    if n == 1:
        previsto = METODOS["REPETIR_15"](serie, horizonte, k)
        inf, sup = _intervalos("REPETIR_15", serie, previsto, 0.0)
        return {"metodo": "REPETIR_15", "valores": [round(v, 4) for v in previsto],
                "inf": inf, "sup": sup, "sigma": 0.0, "mae": None, "mape": None,
                "confianca": 0.25, "n": n, "lacunas": lacunas,
                "perfil": perfil_rubrica(rubrica), "candidatos": [],
                "regra": METODOS_REGRA["REPETIR_15"], "alternativas": []}
    # --- regra 2: poucos dados (2..5) ---
    if n < POCOS_DADOS:
        previsto = METODOS["MEDIA_2DP"](serie, horizonte, k)
        inf, sup = _intervalos("MEDIA_2DP", serie, previsto, 0.0)
        sd = stdev(serie) if n > 1 else 0.0
        conf = 0.5 if n >= POCOS_DADOS - 1 else 0.35
        conf = round(max(0.05, conf - 0.05 * min(lacunas, 3)), 2)
        return {"metodo": "MEDIA_2DP", "valores": [round(v, 4) for v in previsto],
                "inf": inf, "sup": sup, "sigma": round(sd, 4), "mae": None, "mape": None,
                "confianca": conf, "n": n, "lacunas": lacunas,
                "perfil": perfil_rubrica(rubrica), "candidatos": [],
                "regra": METODOS_REGRA["MEDIA_2DP"], "alternativas": []}
    # --- regra 3: serie suficiente -> backtesting entre os candidatos do perfil ---
    candidatos: list[tuple[float, float, str]] = []
    for nome in candidatos_nomes:
        mae, mape = backtest(serie, METODOS[nome], k)
        if math.isfinite(mae):
            candidatos.append((mae, mape, nome))
    if not candidatos:
        candidatos = [(float("inf"), float("inf"), "ULTIMA_OBSERVACAO")]
    candidatos.sort(key=lambda t: (t[0], t[1]))
    mae, mape, escolhido = candidatos[0]
    previsto = METODOS[escolhido](serie, horizonte, k)
    # sigma dos erros de backtesting do metodo escolhido
    erros = []
    for h in range(1, min(k, n - 4) + 1):
        treino = serie[:n - h]
        if len(treino) >= 2:
            try:
                p = METODOS[escolhido](treino, 1, k)
                if p:
                    erros.append(serie[n - h] - p[0])
            except Exception:
                pass
    sigma = pstdev(erros) if len(erros) >= 2 else (abs(erros[0]) if erros else 0.0)
    inf, sup = _intervalos(escolhido, serie, previsto, sigma)
    # confianca: cai com poucos pontos, com lacunas e com erro relativo alto
    esc = max(abs(v) for v in serie) or 1.0
    erro_rel = (sigma / esc) if esc else 1.0
    confianca = 0.9
    confianca -= 0.05 * min(lacunas, 4)
    if n < MIN_PONTOS:
        confianca -= 0.3
    confianca -= min(0.4, erro_rel)
    confianca = round(max(0.05, min(0.95, confianca)), 2)
    return {
        "metodo": escolhido,
        "valores": [round(v, 4) for v in previsto],
        "inf": inf, "sup": sup,
        "sigma": round(sigma, 4),
        "mae": None if math.isinf(mae) else round(mae, 4),
        "mape": None if math.isinf(mape) else round(mape, 2),
        "confianca": confianca,
        "n": n,
        "lacunas": lacunas,
        "regra": None,
        "perfil": perfil_rubrica(rubrica),
        "candidatos": list(candidatos_nomes),
        "alternativas": [{"metodo": c[2], "mae": None if math.isinf(c[0]) else round(c[0], 4)}
                         for c in candidatos[1:]],
    }


def projetar_serie(periodos: list[str], valores: list[float | None],
                   horizonte: int = HORIZONTE_MAX,
                   rubrica: str | None = None) -> dict[str, Any]:
    """Une a serie do banco com a projecao, incluindo os periodos futuros."""
    r = projetar(valores, horizonte, rubrica=rubrica)
    if not r["valores"]:
        return r
    r["periodos"] = list(periodos)
    r["reais"] = [v for v in valores]
    r["futuros"] = proximos(periodos, len(r["valores"]))
    return r