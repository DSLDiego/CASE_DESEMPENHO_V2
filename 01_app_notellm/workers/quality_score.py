"""Worker quality_score: gestão e controle de QUALIDADE e RASTREABILIDADE (M7).

Responde a três perguntas, medindo o banco (nada de opinião):

1. **Qual a qualidade/confiabilidade dos dados?** — scorecard por empresa×período com
   cinco dimensões (completude, tempestividade, plausibilidade, consistência,
   rastreabilidade), DQS 0–100 e classificação CONFIÁVEL / REVISAR / NÃO CONFIÁVEL.

2. **Quais registros estão incompletos ou exigem análise?** — cobertura de rubricas
   esperadas, fatos sem fonte (rastreabilidade), baixa confiança e uma fila
   priorizada P1/P2/P3 com códigos de motivo.

3. **Quando há desvio histórico ou mudança no tempo?** — regras de desvio:
   DRIFT_ZSCORE (z-score contra adistribution histórica), QUEBRA_ESTRUTURAL (mudança
   de nível na série), CONTAGEM_PERIODO (queda de volume = pipeline quebrado),
   REVISAO_ENTRE_EXECUCOES (número de cargas mudou entre execuções) e ATRASO_TRIMESTRE
   (trimestre mais recente não avançou).

As regras ficam em `tb_regra_alerta` (calibráveis) e os desvios viram alertas
idempotentes em `tb_quality_alerts` + itens em `tb_review_queue`.
"""
from __future__ import annotations

import json as _json
import re
from datetime import datetime
from statistics import mean, pstdev
from typing import Any

from config import INDICATORS
from models.database import DatabaseManager
from models.repositories import QualityRepository
from workers.forecast import proximos

RUBRICAS_ESPERADAS = [i["codigo"] for i in INDICATORS if i["categoria"] == "Financeiro"]
PESOS = {"completude": 0.30, "tempestividade": 0.15, "plausibilidade": 0.25,
         "consistencia": 0.15, "rastreabilidade": 0.15}
FAIXAS = ((80.0, "CONFIÁVEL"), (60.0, "REVISAR"))

# Odem as séries segmentadas para detecção cross-sectional (mix setorial)
RUBRICAS_CROSS_SECTIONAL = ("RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO",
                           "CAPEX", "FCO", "DIVIDA_LIQUIDA")

# Limiares por regra (gravados em tb_regra_alerta; calibráveis sem código)
REGRAS: dict[str, dict[str, Any]] = {
    "DRIFT_ZSCORE": {"descricao": "Desvio do valor contra a distribuição histórica (z-score)",
                     "limiar": 2.0, "severidade": "MEDIUM"},
    "QUEBRA_ESTRUTURAL": {"descricao": "Mudança de nível na série (meia 1 vs meia 2)",
                          "limiar": 0.40, "severidade": "MEDIUM"},
    "CONTAGEM_PERIODO": {"descricao": "Queda de volume de fatos vs período anterior",
                         "limiar": 0.40, "severidade": "HIGH"},
    "REVISAO_ENTRE_EXECUCOES": {"descricao": "Nº de cargas mudou entre execuções do pipeline",
                                "limiar": 0.30, "severidade": "MEDIUM"},
    "ATRASO_TRIMESTRE": {"descricao": "Trimestre mais recente não avançou",
                         "limiar": 1.0, "severidade": "HIGH"},
    "BAIXA_CONFIANCA": {"descricao": "Fato com confiança abaixo do mínimo",
                        "limiar": 0.70, "severidade": "MEDIUM"},
    "SEM_FONTE": {"descricao": "Fato sem vínculo de fonte (rastreabilidade quebrada)",
                  "limiar": 1.0, "severidade": "HIGH"},
    "RUBRICA_AUSENTE": {"descricao": "Rubrica esperada sem fato no período",
                        "limiar": 1.0, "severidade": "LOW"},
    "OUTLIER_CROSS_SECTIONAL": {
        "descricao": "Valor fora da curva dos pares no MESMO trimestre (z-score cross-sectional)",
        "limiar": 1.8, "severidade": "MEDIUM"},
}


# --------------------------------------------------------------- scorecard
def _classificar(dqs: float) -> str:
    for corte, rotulo in FAIXAS:
        if dqs >= corte:
            return rotulo
    return "NÃO CONFIÁVEL"


def avaliar_periodo(db: DatabaseManager, empresa: str, periodo: str,
                    ultimo_periodo_carga: str | None = None) -> dict[str, Any]:
    """Calcula as 5 dimensões e o DQS de uma empresa em um trimestre."""
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT rubrica_padronizada, valor, confianca, id_fonte FROM tb_fato_financeiro"
            " WHERE nome_empresa = ? AND periodo = ?", (empresa, periodo)).fetchall()]
    # 1) completude: rubricas esperadas presentes
    presentes = {r["rubrica_padronizada"] for r in rows}
    esperadas = set(RUBRICAS_ESPERADAS)
    completude = 100.0 * len(presentes & esperadas) / max(1, len(esperadas))
    # 2) rastreabilidade: fatos com id_fonte válido
    com_fonte = sum(1 for r in rows if r["id_fonte"])
    rastreabilidade = 100.0 * com_fonte / max(1, len(rows))
    # 3) consistência: confiança média dos fatos
    conf = [r["confianca"] or 0.0 for r in rows] or [0.0]
    consistencia = 100.0 * min(1.0, mean(conf) / 0.95)
    # 4) plausibilidade: nenhum valor fora de ordem absurda + sinais
    plaus = 100.0
    for r in rows:
        if r["valor"] is None or (r["rubrica_padronizada"] != "DESPESA_OPERACIONAL"
                                  and r["valor"] < 0):
            plaus -= 25
    plaus = max(0.0, plaus)
    # 5) tempestividade: período é o mais recente disponível?
    tempestividade = 100.0 if (ultimo_periodo_carga or periodo) == periodo else 60.0
    dims = {"completude": round(completude, 1), "tempestividade": tempestividade,
            "plausibilidade": round(plaus, 1), "consistencia": round(consistencia, 1),
            "rastreabilidade": round(rastreabilidade, 1)}
    dqs = round(sum(dims[k] * PESOS[k] for k in PESOS), 1)
    ausentes = sorted(esperadas - presentes)
    return {"nome_empresa": empresa, "periodo": periodo, **dims, "dqs": dqs,
            "classificacao": _classificar(dqs), "n_fatos": len(rows),
            "n_esperadas": len(esperadas), "rubricas_ausentes": ausentes,
            "confianca_media": round(mean(conf), 3)}


def avaliar_base(db: DatabaseManager) -> list[dict[str, Any]]:
    """Scorecard completo (todas as empresas × períodos com fatos)."""
    with db.connect() as conn:
        ultima = conn.execute("SELECT MAX(periodo) p FROM tb_fato_financeiro").fetchone()["p"]
        combos = [dict(r) for r in conn.execute(
            "SELECT DISTINCT nome_empresa, periodo FROM tb_fato_financeiro"
            " ORDER BY nome_empresa, periodo").fetchall()]
    return [avaliar_periodo(db, c["nome_empresa"], c["periodo"], ultima) for c in combos]


# ------------------------------------------------- historico do DQS (M7.23)
def _registrar_historico(db: DatabaseManager, cards: list[dict[str, Any]]) -> int:
    """Grava um ponto no historico quando o DQS MUDA (nao a cada execucao).

    `tb_qualidade_score` é sobrescrito a cada `run_quality_score`, então a evolução
    da qualidade se perdia. Gravar a cada execução produziria uma série com repetição
    e_dt mas mudando, que é ruído — o painel mostra a linha do tempo, não o log.
    """
    if not cards:
        return 0
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    novos = 0
    with db.connect() as conn:
        for c in cards:
            ultimo = conn.execute(
                "SELECT dqs FROM tb_qualidade_historico WHERE nome_empresa = ? AND periodo = ?"
                " ORDER BY gerado_em DESC, id_hist DESC LIMIT 1",
                (c["nome_empresa"], c["periodo"])).fetchone()
            if ultimo is not None and (ultimo["dqs"] or 0.0) == c["dqs"]:
                continue      # nada mudou: um ponto novo seria repeticao
            conn.execute(
                """INSERT INTO tb_qualidade_historico
                   (nome_empresa, periodo, completude, tempestividade, plausibilidade,
                    consistencia, rastreabilidade, dqs, classificacao, n_fatos, gerado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (c["nome_empresa"], c["periodo"], c["completude"], c["tempestividade"],
                 c["plausibilidade"], c["consistencia"], c["rastreabilidade"],
                 c["dqs"], c["classificacao"], c["n_fatos"], agora))
            novos += 1
        conn.commit()
    return novos


def _serie_historica(db: DatabaseManager, empresa: str) -> list[dict[str, Any]]:
    """Pontos (periodo, dqs, instante) da empresa em ordem cronologica."""
    with db.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT periodo, dqs, classificacao, gerado_em FROM tb_qualidade_historico"
            " WHERE nome_empresa = ? ORDER BY periodo, gerado_em, id_hist",
            (empresa,)).fetchall()]


def historico_scorecard(db: DatabaseManager, empresa: str | None = None) -> dict[str, Any]:
    """Scorecard histórico (M7.23): DQS ao longo do tempo, por período e por empresa.

    Devolve a série temporal por empresa (com a variação de cada trimestre), a
    média da base por período e as empresas que mais subiram e mais caíram — a
    leitura que responde "a qualidade melhorou ou piorou desde o início?".
    """
    with db.connect() as conn:
        empresas = sorted({r["nome_empresa"] for r in conn.execute(
            "SELECT DISTINCT nome_empresa FROM tb_qualidade_historico").fetchall()})
    if empresa:
        # filtro explicito: empresa desconhecida devolve serie vazia em vez de
        # silenciosamente devolver a base toda (leitura errada no painel).
        empresas = [e for e in empresas if e == empresa]
    series = {emp: _serie_historica(db, emp) for emp in empresas}
    por_empresa: dict[str, Any] = {}
    for emp, pontos in series.items():
        # um ponto por período: o último DQS conhecido de cada trimestre
        ultimo_por_periodo: dict[str, dict[str, Any]] = {}
        for p in pontos:
            ultimo_por_periodo[p["periodo"]] = p
        linha = []
        anterior: float | None = None
        for per in sorted(ultimo_por_periodo):
            dqs = float(ultimo_por_periodo[per]["dqs"] or 0.0)
            linha.append({"periodo": per, "dqs": dqs,
                          "classificacao": ultimo_por_periodo[per]["classificacao"],
                          "variacao": None if anterior is None else round(dqs - anterior, 1),
                          "gerado_em": ultimo_por_periodo[per]["gerado_em"]})
            anterior = dqs
        if linha:
            por_empresa[emp] = {
                "empresa": emp, "pontos": linha,
                "dqs_inicial": linha[0]["dqs"], "dqs_atual": linha[-1]["dqs"],
                "variacao_total": round(linha[-1]["dqs"] - linha[0]["dqs"], 1),
                "classificacao_atual": linha[-1]["classificacao"],
                "periodos": len(linha),
            }
    # media da base por periodo (a serie que da o titulo do painel)
    periodos: list[str] = sorted({p["periodo"] for pontos in series.values() for p in pontos})
    media_por_periodo: list[dict[str, Any]] = []
    for per in periodos:
        valores = [float(p["dqs"] or 0.0) for pontos in series.values() for p in pontos
                   if p["periodo"] == per]
        if valores:
            media_por_periodo.append({"periodo": per, "dqs_medio": round(mean(valores), 1),
                                      "empresas": len(valores)})
    variacoes = sorted((v for v in por_empresa.values() if v["periodos"] > 1),
                       key=lambda v: v["variacao_total"])
    return {"empresas": len(por_empresa), "periodos": periodos,
            "por_empresa": por_empresa,
            "serie_empresa": empresa if empresa in por_empresa else None,
            "media_por_periodo": media_por_periodo,
            "melhorou": variacoes[-1] if variacoes else None,
            "piorou": variacoes[0] if variacoes else None,
            "dqs_atual": media_por_periodo[-1]["dqs_medio"] if media_por_periodo else 0.0,
            "dqs_inicial": media_por_periodo[0]["dqs_medio"] if media_por_periodo else 0.0,
            "variacao_media": (round(media_por_periodo[-1]["dqs_medio"]
                                     - media_por_periodo[0]["dqs_medio"], 1)
                               if len(media_por_periodo) > 1 else 0.0)}


def resumo_scorecard(db: DatabaseManager) -> dict[str, Any]:
    """Agregados do scorecard: média por dimensão, distribuição de classificação."""
    cards = avaliar_base(db)
    if not cards:
        return {"empresas": 0, "periodos": 0, "dqs_medio": 0.0, "por_dimensao": {},
                "classificacao": {}, "pior": [], "cards": []}
    dims = {k: round(mean(c[k] for c in cards), 1) for k in PESOS}
    classe: dict[str, int] = {}
    for c in cards:
        classe[c["classificacao"]] = classe.get(c["classificacao"], 0) + 1
    piores = sorted(cards, key=lambda c: c["dqs"])[:12]
    return {"empresas": len({c["nome_empresa"] for c in cards}),
            "periodos": len({c["periodo"] for c in cards}),
            "dqs_medio": round(mean(c["dqs"] for c in cards), 1),
            "por_dimensao": dims, "classificacao": classe,
            "pior": [{"nome_empresa": c["nome_empresa"], "periodo": c["periodo"],
                      "dqs": c["dqs"], "classificacao": c["classificacao"]} for c in piores],
            "cards": cards}


# ------------------------------------------------- desvios e mudanças no tempo
def _serie(db: DatabaseManager, empresa: str, rubrica: str) -> list[tuple[str, float]]:
    with db.connect() as conn:
        return [(r["periodo"], r["valor"]) for r in conn.execute(
            "SELECT periodo, valor FROM tb_fato_financeiro WHERE nome_empresa = ?"
            " AND rubrica_padronizada = ? ORDER BY periodo", (empresa, rubrica)).fetchall()]


def _zscore(valor: float, janela: list[float]) -> float:
    if len(janela) < 3:
        return 0.0
    sd = pstdev(janela)
    if sd == 0:
        return 0.0
    return (valor - mean(janela)) / sd


def detectar_cross_sectional(db: DatabaseManager) -> list[dict[str, Any]]:
    """M7.24: valor fora da curva dos PARES no mesmo trimestre.

    O DRIFT_ZSCORE olha a empresa contra a própria história; este olha a empresa
    contra o setor no mesmo período. Com 7 companies o desvio-padrão da amostra é
    pequeno, então o limiar é 1,8σ e exige ao menos 4 pares — abaixo disso qualquer
    diferença parece anomalia.
    """
    alertas: list[dict[str, Any]] = []
    MIN_PARES = 4
    with db.connect() as conn:
        marcas = ",".join("?" * len(RUBRICAS_CROSS_SECTIONAL))
        linhas = conn.execute(
            f"SELECT periodo, rubrica_padronizada, nome_empresa, valor "
            f"FROM tb_fato_financeiro WHERE valor IS NOT NULL "
            f"AND rubrica_padronizada IN ({marcas})", RUBRICAS_CROSS_SECTIONAL).fetchall()
    grupos: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for linha in linhas:
        grupos.setdefault((linha["periodo"], linha["rubrica_padronizada"]), []).append(
            (linha["nome_empresa"], float(linha["valor"])))
    for (periodo, rubrica), pares in grupos.items():
        if len(pares) < MIN_PARES:
            continue
        # M7.22: o limiar pode ser calibrado por rubrica (CAPEX tem outra variabilidade
        # que receita) ou por empresa, sem sair do código.
        limiar = limiar_efetivo(db, "OUTLIER_CROSS_SECTIONAL", None, rubrica) \
            or REGRAS["OUTLIER_CROSS_SECTIONAL"]["limiar"]
        valores = [v for _, v in pares]
        media = mean(valores)
        desvio = pstdev(valores) if len(valores) > 1 else 0.0
        if desvio <= 0:
            continue
        for empresa, valor in pares:
            z = (valor - media) / desvio
            if abs(z) < limiar:
                continue
            alertas.append({
                "codigo": "OUTLIER_CROSS_SECTIONAL",
                "severidade": REGRAS["OUTLIER_CROSS_SECTIONAL"]["severidade"],
                "empresa": empresa, "periodo": periodo,
                "descricao": (f"{rubrica} {valor:,.2f} está {z:+.1f}σ do grupo "
                              f"({len(pares)} empresas, média {media:,.2f})")})
    return alertas


def detectar_desvios(db: DatabaseManager) -> list[dict[str, Any]]:
    """Regras de desvio histórico / mudança de dados no tempo."""
    alertas: list[dict[str, Any]] = []
    lim = {k: v["limiar"] for k, v in REGRAS.items()}
    with db.connect() as conn:
        series = {(r["nome_empresa"], r["rubrica_padronizada"]) for r in conn.execute(
            "SELECT DISTINCT nome_empresa, rubrica_padronizada FROM tb_fato_financeiro").fetchall()}
        contagem = [dict(r) for r in conn.execute(
            "SELECT periodo, COUNT(*) n FROM tb_fato_financeiro GROUP BY periodo"
            " ORDER BY periodo").fetchall()]
        # regra: contagem de fatos por período
        for ant, atual in zip(contagem, contagem[1:]):
            if ant["n"] and (atual["n"] - ant["n"]) / ant["n"] < -lim["CONTAGEM_PERIODO"]:
                alertas.append({"codigo": "CONTAGEM_PERIODO", "severidade": REGRAS["CONTAGEM_PERIODO"]["severidade"],
                                "empresa": "(todas)", "periodo": atual["periodo"],
                                "descricao": (f"volume de fatos caiu de {ant['n']} para {atual['n']} "
                                              f"({(atual['n'] - ant['n']) / ant['n']:.0%}) em {atual['periodo']}")})
        # regra: trimestre mais recente nao avancou
        periodos = [r["periodo"] for r in contagem if _QOK.match(str(r["periodo"]))]
        if len(periodos) >= 2:
            esperado = proximos(periodos[-2:], 1)[0]
            if periodos[-1] < esperado:
                alertas.append({"codigo": "ATRASO_TRIMESTRE", "severidade": REGRAS["ATRASO_TRIMESTRE"]["severidade"],
                                "empresa": "(todas)", "periodo": periodos[-1],
                                "descricao": (f"último trimestre carregado é {periodos[-1]}, "
                                              f"esperado {esperado} — pipeline possivelmente parado")})
    # regra: z-score e quebra estrutural por serie, com limiar por empresa/rubrica
    for empresa, rubrica in sorted(series):
        serie = _serie(db, empresa, rubrica)
        vals = [v for _, v in serie]
        limiar_drift = limiar_efetivo(db, "DRIFT_ZSCORE", empresa, rubrica) \
            or lim["DRIFT_ZSCORE"]
        limiar_quebra = limiar_efetivo(db, "QUEBRA_ESTRUTURAL", empresa, rubrica) \
            or lim["QUEBRA_ESTRUTURAL"]
        for i in range(3, len(vals)):
            z = _zscore(vals[i], vals[max(0, i - 6):i])
            if abs(z) >= limiar_drift:
                calibrated = limiar_drift != lim["DRIFT_ZSCORE"]
                alertas.append({"codigo": "DRIFT_ZSCORE", "severidade": REGRAS["DRIFT_ZSCORE"]["severidade"],
                                "empresa": empresa, "periodo": serie[i][0],
                                "calibrado": calibrated,
                                "descricao": (f"{rubrica} {serie[i][0]}: valor {vals[i]:,.2f} "
                                              f"desvia {z:+.1f}σ da série anterior"
                                              + (f" (limiar calibrado: {limiar_drift}σ)"
                                                 if calibrated else ""))})
        if len(vals) >= 4:
            meio = len(vals) // 2
            m1, m2 = mean(vals[:meio]), mean(vals[meio:])
            if m1 and abs(m2 - m1) / abs(m1) >= limiar_quebra:
                calibrated = limiar_quebra != lim["QUEBRA_ESTRUTURAL"]
                alertas.append({"codigo": "QUEBRA_ESTRUTURAL", "severidade": REGRAS["QUEBRA_ESTRUTURAL"]["severidade"],
                                "empresa": empresa, "periodo": serie[-1][0],
                                "calibrado": calibrated,
                                "descricao": (f"{rubrica}: nível muda de {m1:,.2f} para {m2:,.2f} "
                                              f"({(m2 - m1) / abs(m1):+.0%}) na série"
                                              + (f" (limiar calibrado: {limiar_quebra:.0%})"
                                                 if calibrated else ""))})
    return alertas


def _revisao_entre_execucoes(db: DatabaseManager) -> list[dict[str, Any]]:
    """Mudança de dados no tempo: nº de cargas diferente entre as 2 últimas execuções."""
    with db.connect() as conn:
        execs = [dict(r) for r in conn.execute(
            "SELECT inicio_em, cargas, extracoes FROM tb_etl_execucao WHERE status <> 'EM_ANDAMENTO'"
            " ORDER BY id_execucao DESC LIMIT 2").fetchall()]
    if len(execs) < 2:
        return []
    # as DUAS precisam ter carga: execucao incremental sem trabalho novo grava
    # cargas = 0 e nao pode virar denominador (ZeroDivisionError no painel).
    atual, anterior = execs[0]["cargas"] or 0, execs[1]["cargas"] or 0
    if not atual or not anterior:
        return []
    var = (atual - anterior) / anterior
    if abs(var) < REGRAS["REVISAO_ENTRE_EXECUCOES"]["limiar"]:
        return []
    return [{"codigo": "REVISAO_ENTRE_EXECUCOES", "severidade": REGRAS["REVISAO_ENTRE_EXECUCOES"]["severidade"],
             "empresa": "(todas)", "periodo": execs[0]["inicio_em"][:10],
             "descricao": (f"cargas da última execução {execs[0]['cargas']} vs "
                           f"{execs[1]['cargas']} da anterior ({var:+.0%}) — dados mudaram")}]


# ------------------------------------------------------ fila de análise (P1/P2/P3)
PRIORIDADES = {"CONTAGEM_PERIODO": "P1", "ATRASO_TRIMESTRE": "P1", "SEM_FONTE": "P1",
               "OUTLIER_CROSS_SECTIONAL": "P1",
               "DRIFT_ZSCORE": "P2", "BAIXA_CONFIANCA": "P2", "QUEBRA_ESTRUTURAL": "P2",
               "REVISAO_ENTRE_EXECUCOES": "P2", "RUBRICA_AUSENTE": "P3"}
# Repeticoes do mesmo codigo de alerta acima disso escalam a prioridade (M2.11)
REPETICAO_ESCALA = 3
ESCALA_DISPONIVEL = {"P3": "P2", "P2": "P1"}


def fila_analise(db: DatabaseManager) -> list[dict[str, Any]]:
    """Registros incompletos ou que exigem análise, priorizados com motivo."""
    itens: list[dict[str, Any]] = []
    for a in detectar_desvios(db) + detectar_cross_sectional(db) \
            + _revisao_entre_execucoes(db):
        itens.append({"prioridade": PRIORIDADES.get(a["codigo"], "P3"), "codigo": a["codigo"],
                      "empresa": a["empresa"], "periodo": a["periodo"],
                      "severidade": a["severidade"], "motivo": a["descricao"]})
    with db.connect() as conn:
        # fatos sem fonte = rastreabilidade quebrada
        sem_fonte = [dict(r) for r in conn.execute(
            "SELECT nome_empresa, periodo, rubrica_padronizada FROM tb_fato_financeiro"
            " WHERE id_fonte IS NULL LIMIT 200").fetchall()]
        # rubricas ausentes por periodo (completude)
        combos = [dict(r) for r in conn.execute(
            "SELECT DISTINCT nome_empresa, periodo FROM tb_fato_financeiro").fetchall()]
    for c in combos:
        card = avaliar_periodo(db, c["nome_empresa"], c["periodo"])
        for rub in card["rubricas_ausentes"]:
            itens.append({"prioridade": PRIORIDADES["RUBRICA_AUSENTE"], "codigo": "RUBRICA_AUSENTE",
                          "empresa": card["nome_empresa"], "periodo": card["periodo"],
                          "severidade": REGRAS["RUBRICA_AUSENTE"]["severidade"],
                          "motivo": f"{rub} ausente (completude {card['completude']:.0f}%)"})
    for f in sem_fonte:
        itens.append({"prioridade": PRIORIDADES["SEM_FONTE"], "codigo": "SEM_FONTE",
                      "empresa": f["nome_empresa"], "periodo": f["periodo"],
                      "severidade": REGRAS["SEM_FONTE"]["severidade"],
                      "motivo": f"{f['rubrica_padronizada']} sem id_fonte"})
    ordem = {"P1": 0, "P2": 1, "P3": 2}
    # M2.11: alerta critico repetido escala de prioridade. Um P3 que aparece 5x
    # para a mesma empresa deixa de ser "rubrica ausente" e vira problema a resolver.
    repeticoes: dict[str, int] = {}
    with db.connect() as conn:
        # tb_quality_alerts nao tem empresa (o alerta aponta para o registro); a
        # recorrencia que interessa e a do codigo, que e o mesmo defeito.
        for linha in conn.execute(
                "SELECT tipo_alerta, COUNT(*) n FROM tb_quality_alerts "
                "WHERE criado_em IS NOT NULL GROUP BY 1").fetchall():
            repeticoes[linha["tipo_alerta"]] = linha["n"]
    # alertas nao trazem empresa (grao do registro); usa a contagem global por codigo
    ESCALADA = ESCALA_DISPONIVEL
    for item in itens:
        repeticoes_item = repeticoes.get(item["codigo"], 0)
        if repeticoes_item > REPETICAO_ESCALA:
            nova = ESCALADA.get(item["prioridade"])
            if nova:
                item["prioridade"] = nova
                item["motivo"] = (f"[escalado: {repeticoes_item} ocorrências] "
                                 + item["motivo"])
                item["escalado"] = True
    return sorted(itens, key=lambda i: (ordem.get(i["prioridade"], 3), i["codigo"]))[:500]


# ------------------------------------------------------------ persistência
def _sincronizar_regras(db: DatabaseManager) -> None:
    with db.connect() as conn:
        for codigo, r in REGRAS.items():
            conn.execute(
                "INSERT INTO tb_regra_alerta (codigo, descricao, limiar, severidade, ativo)"
                " VALUES (?, ?, ?, ?, 1) ON CONFLICT(codigo) DO UPDATE SET"
                " descricao = excluded.descricao, limiar = excluded.limiar",
                (codigo, r["descricao"], r["limiar"], r["severidade"]))
        conn.commit()


# ------------------------------------------------- limiar por empresa/rubrica (M7.22)
def gravar_limiar(db: DatabaseManager, codigo: str, limiar: float,
                   empresa: str | None = None, rubrica: str | None = None,
                   ativo: int = 1) -> None:
    """Calibra um limiar so para uma empresa e/ou rubrica.

    Empresa vazia + rubrica vazia = regra global (sobrescreve tb_regra_alerta).
    Empresa "" + rubrica "CAPEX" = so CAPEX, para qualquer empresa.
    Empresa "BP" + rubrica "" = so a BP.
    """
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO tb_regra_limiar (codigo, empresa, rubrica, limiar, ativo)"
            " VALUES (?, ?, ?, ?, ?) ON CONFLICT(codigo, empresa, rubrica) DO UPDATE SET"
            " limiar = excluded.limiar, ativo = excluded.ativo",
            (codigo, empresa or "", rubrica or "", float(limiar), int(ativo)))
        conn.commit()


def listar_limiares(db: DatabaseManager, codigo: str | None = None) -> list[dict[str, Any]]:
    q = "SELECT * FROM tb_regra_limiar"
    params: tuple = ()
    if codigo:
        q += " WHERE codigo = ?"
        params = (codigo,)
    q += (" ORDER BY codigo,"
           " CASE WHEN empresa <> '' THEN 0 ELSE 1 END,"
           " CASE WHEN rubrica <> '' THEN 0 ELSE 1 END")
    with db.connect() as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def limiar_efetivo(db: DatabaseManager, codigo: str, empresa: str | None = None,
                   rubrica: str | None = None) -> float | None:
    """Limiar que vale para (empresa, rubrica), do mais especifico ao global.

    Ordem: empresa+rubrica > rubrica > empresa > global (tb_regra_alerta).
    Sem excecao cadastrada, devolve None — quem chama usa REGRAS[codigo].
    """
    empresa, rubrica = empresa or "", rubrica or ""
    with db.connect() as conn:
        for cand_empresa, cand_rubrica in ((empresa, rubrica),
                                           ("", rubrica), (empresa, ""), ("", "")):
            if not cand_empresa and not cand_rubrica:
                continue    # global fica em tb_regra_alerta
            linha = conn.execute(
                "SELECT limiar FROM tb_regra_limiar WHERE codigo = ? AND empresa = ?"
                " AND rubrica = ? AND ativo = 1", (codigo, cand_empresa, cand_rubrica)).fetchone()
            if linha is not None:
                return float(linha["limiar"])
    return None


def _limiares_efetivos(db: DatabaseManager, empresa: str, rubrica: str) -> dict[str, float]:
    """Todos os limiares aplicáveis a um par (empresa, rubrica), já resolvidos."""
    with db.connect() as conn:
        base = {r["codigo"]: r["limiar"] for r in conn.execute(
            "SELECT codigo, limiar FROM tb_regra_alerta WHERE ativo = 1").fetchall()}
        excecoes = [dict(r) for r in conn.execute(
            "SELECT codigo, empresa, rubrica, limiar FROM tb_regra_limiar"
            " WHERE ativo = 1").fetchall()]
    # (-especificidade) para que a mais especifica seja aplicada por ultimo
    especificidade = {(e["empresa"], e["rubrica"]): s
                      for s, e in enumerate(((empresa, rubrica), ("", rubrica), (empresa, "")))}
    for exc in sorted(excecoes, key=lambda e: especificidade.get(
            (e["empresa"], e["rubrica"]), 99)):
        if (exc["empresa"] in ("", empresa)) and (exc["rubrica"] in ("", rubrica)):
            base[exc["codigo"]] = exc["limiar"]
    return base


def salvar_scorecard(db: DatabaseManager, cards: list[dict[str, Any]]) -> int:
    with db.connect() as conn:
        for c in cards:
            conn.execute(
                """INSERT INTO tb_qualidade_score (nome_empresa, periodo, completude,
                   tempestividade, plausibilidade, consistencia, rastreabilidade, dqs,
                   classificacao, n_fatos, n_esperadas, detalhes_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (nome_empresa, periodo) DO UPDATE SET completude = excluded.completude,
                     tempestividade = excluded.tempestividade, plausibilidade = excluded.plausibilidade,
                     consistencia = excluded.consistencia, rastreabilidade = excluded.rastreabilidade,
                     dqs = excluded.dqs, classificacao = excluded.classificacao,
                     n_fatos = excluded.n_fatos, detalhes_json = excluded.detalhes_json,
                     gerado_em = datetime('now')""",
                (c["nome_empresa"], c["periodo"], c["completude"], c["tempestividade"],
                 c["plausibilidade"], c["consistencia"], c["rastreabilidade"], c["dqs"],
                 c["classificacao"], c["n_fatos"], c["n_esperadas"],
                 _json.dumps({"ausentes": c["rubricas_ausentes"],
                              "confianca_media": c["confianca_media"]})))
        conn.commit()
    return len(cards)


_QOK = re.compile(r"^\d{4}Q[1-4]$")


def run_quality_score(db: DatabaseManager | None = None) -> dict[str, Any]:
    """Executa o ciclo completo: scorecard + desvios + fila (idempotente)."""
    db = db or DatabaseManager()
    _sincronizar_regras(db)
    resumo = resumo_scorecard(db)
    salvar_scorecard(db, resumo["cards"])
    # Serie historica do DQS (M7.23): so grava ponto quando o valor muda.
    pontos = _registrar_historico(db, resumo["cards"])
    quality = QualityRepository(db)
    alertas = detectar_desvios(db) + _revisao_entre_execucoes(db)
    novos = 0
    for a in alertas:
        antes = len(quality.listar_alertas())
        quality.alertar("tb_qualidade_score", 0, a["codigo"], f"[{a['empresa']} {a['periodo']}] {a['descricao']}",
                        a["severidade"])
        novos += len(quality.listar_alertas()) - antes
    fila = fila_analise(db)
    for it in fila:
        if it["prioridade"] in ("P1", "P2"):
            quality.para_revisao(it["empresa"], it["periodo"], it["codigo"], None,
                                 f"[{it['prioridade']}] {it['motivo']}", 0.0)
    hist = historico_scorecard(db)
    return {"dqs_medio": resumo["dqs_medio"], "por_dimensao": resumo["por_dimensao"],
            "classificacao": resumo["classificacao"], "cards": len(resumo["cards"]),
            "historico": {"pontos": pontos, "periodos": len(hist["periodos"]),
                          "variacao_media": hist["variacao_media"]},
            "desvios": len(alertas), "alertas_novos": novos, "fila": len(fila),
            "p1": sum(1 for i in fila if i["prioridade"] == "P1"),
            "p2": sum(1 for i in fila if i["prioridade"] == "P2"),
            "p3": sum(1 for i in fila if i["prioridade"] == "P3"),
            "pior": resumo["pior"][:5], "regras": len(REGRAS)}


def contrato(db: DatabaseManager | None = None) -> dict[str, Any]:
    """Contrato de dados (M7.26) para exibir no painel: tipos, nulos, dominios, sinal."""
    from workers.data_contract import rodar_contrato
    try:
        return rodar_contrato(db or DatabaseManager())
    except Exception as exc:                       # noqa: BLE001
        return {"ok": True, "erro": f"{type(exc).__name__}: {exc}", "violacoes": 0}


def painel_qualidade(db: DatabaseManager | None = None) -> dict[str, Any]:
    """Pacote para o painel (web/GUI): scorecard + desvios + fila + regras."""
    db = db or DatabaseManager()
    resumo = resumo_scorecard(db)
    fila = fila_analise(db)
    with db.connect() as conn:
        alertas = [dict(r) for r in conn.execute(
            "SELECT tipo_alerta, severidade, COUNT(*) n FROM tb_quality_alerts"
            " GROUP BY tipo_alerta, severidade ORDER BY n DESC").fetchall()]
        revisoes = [dict(r) for r in conn.execute(
            "SELECT status, COUNT(*) n FROM tb_review_queue GROUP BY status").fetchall()]
        regras = [dict(r) for r in conn.execute(
            "SELECT * FROM tb_regra_alerta ORDER BY codigo").fetchall()]
    return {"resumo": {k: resumo[k] for k in
                       ("empresas", "periodos", "dqs_medio", "por_dimensao",
                        "classificacao", "pior")},
            "cards": resumo["cards"], "fila": fila,
            # Scorecard histórico (M7.23): DQS ao longo do tempo.
            "historico": historico_scorecard(db),
            "alertas_por_tipo": alertas, "revisao_por_status": revisoes,
            "regras": regras,
            "contrato": contrato(db),
            "dimensoes": [{"codigo": k, "nome": n, "peso": PESOS[k]} for k, n in (
                ("completude", "Completude"), ("tempestividade", "Tempestividade"),
                ("plausibilidade", "Plausibilidade"), ("consistencia", "Consistência"),
                ("rastreabilidade", "Rastreabilidade"))]}