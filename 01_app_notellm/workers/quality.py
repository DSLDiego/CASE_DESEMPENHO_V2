"""Workers transversais: cambio PTAX e auditoria de qualidade."""
from __future__ import annotations

import requests

from config import PTAX_FALLBACK
from models.database import DatabaseManager
from models.repositories import FatoRepository, QualityRepository

# ---------------- Cambio ----------------

def ptax_bcb(data_iso: str) -> float | None:
    """Cotacao de venda BRL/USD (fechamento) na API Olinda do BCB."""
    url = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
           f"CotacaoMoedaDia(moeda=@moeda,dataCotacao=@data)?@moeda='USD'"
           f"&@data='{data_iso}'&$format=json")
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            vals = resp.json().get("value", [])
            if vals:
                return float(vals[-1]["cotacaoVenda"])
    except Exception:
        return None
    return None


FECHAMENTO = {"Q1": "-03-31", "Q2": "-06-30", "Q3": "-09-30", "Q4": "-12-31"}


def taxa_para_usd(periodo: str) -> float:
    """BRL por USD no fechamento do trimestre (fallback tabelado offline)."""
    ano, tri = FatoRepository.split_periodo(periodo)
    q = f"Q{tri}" if tri else "Q4"
    taxa = ptax_bcb(f"{ano}{FECHAMENTO[q]}")
    return taxa or PTAX_FALLBACK.get(f"{ano}{q}", 5.20)


def brl_milhoes_para_usd_bi(valor_brl_mi: float, periodo: str) -> float:
    return round(valor_brl_mi / 1000.0 / taxa_para_usd(periodo), 4)


# ---------------- Qualidade ----------------

ESTRICT_POSITIVO = {"RECEITA_LIQUIDA", "EFETIVO_TOTAL", "FCO", "EBITDA_AJUSTADO"}
QOQ_SPIKE = 0.40


def run_audit(db: DatabaseManager | None = None) -> dict[str, int]:
    """Aplica regras de qualidade; grava alertas + review_queue. Retorna contagens."""
    from config import CONFIDENCE_MIN
    db = db or DatabaseManager()
    quality = QualityRepository(db)
    resumo = {"negativos": 0, "spikes": 0, "baixa_confianca": 0, "incompletos": 0}
    with db.connect() as conn:
        fatos = conn.execute(
            "SELECT id_fato, nome_empresa, periodo, rubrica_padronizada, valor, confianca"
            " FROM tb_fato_financeiro").fetchall()
        por_serie: dict[tuple[str, str], list] = {}
        for row in fatos:
            rub = row["rubrica_padronizada"]
            if rub in ESTRICT_POSITIVO and (row["valor"] or 0) < 0:
                quality.alertar("tb_fato_financeiro", row["id_fato"], "INVALID_NEGATIVE",
                                f"{rub} negativo ({row['valor']}) em {row['periodo']}", "HIGH")
                resumo["negativos"] += 1
            if (row["confianca"] or 1.0) < CONFIDENCE_MIN:
                quality.para_revisao(row["nome_empresa"], row["periodo"], rub,
                                     row["valor"], "confianca abaixo do limiar", row["confianca"] or 0)
                resumo["baixa_confianca"] += 1
            por_serie.setdefault((row["nome_empresa"], rub), []).append(row)
        for (empresa, rub), serie in por_serie.items():
            serie = sorted(serie, key=lambda r: r["periodo"])
            for ant, cur in zip(serie, serie[1:]):
                if ant["valor"]:
                    var = abs(cur["valor"] - ant["valor"]) / abs(ant["valor"])
                    if var > QOQ_SPIKE:
                        quality.alertar("tb_fato_financeiro", cur["id_fato"], "VARIATION_SPIKE",
                                        f"{rub} {empresa}: {var:.0%} entre {ant['periodo']} e {cur['periodo']}",
                                        "MEDIUM")
                        resumo["spikes"] += 1
        # cobertura: empresa x periodo x rubrica esperada
        empresas = [r["nome_empresa"] for r in conn.execute(
            "SELECT DISTINCT nome_empresa FROM tb_fato_financeiro").fetchall()]
        periodos = [r["periodo"] for r in conn.execute(
            "SELECT DISTINCT periodo FROM tb_fato_financeiro").fetchall()]
        rubricas = [r["rubrica_padronizada"] for r in conn.execute(
            "SELECT DISTINCT rubrica_padronizada FROM tb_fato_financeiro").fetchall()]
        existentes = {(r["nome_empresa"], r["periodo"], r["rubrica_padronizada"]) for r in fatos}
        for emp in empresas:
            for per in periodos:
                for rub in rubricas:
                    if (emp, per, rub) not in existentes:
                        quality.para_revisao(emp, per, rub, None, "registro ausente (cobertura)", 0.0)
                        resumo["incompletos"] += 1
    return resumo
