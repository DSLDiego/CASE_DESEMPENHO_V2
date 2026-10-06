"""Coleta os números reais do banco para a apresentação (não inventa nada)."""
from __future__ import annotations

from collections import defaultdict

from config import INDICATORS
from models.database import DatabaseManager
from models.repositories import FatoRepository

EMPS = ["PETROBRAS", "SHELL", "BP", "CHEVRON", "EXXONMOBIL", "TOTALENERGIES", "EQUINOR"]
RUBS = ["RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO", "FCO", "CAPEX",
        "DIVIDA_LIQUIDA"]


def main() -> None:
    db = DatabaseManager()
    d: dict[str, dict[str, float]] = defaultdict(dict)
    for r in FatoRepository(db).matriz("2026Q2"):
        d[r["rubrica_padronizada"]][r["nome_empresa"]] = r["valor"]
    print("== matriz 2026Q2 (USD bi)")
    for rub in RUBS:
        vals = d.get(rub, {})
        print(f"{rub:<20}", {e: (round(vals[e], 2) if e in vals else None) for e in EMPS})
    one = lambda s: db.connect().execute(s).fetchone()[0]  # noqa: E731
    with db.connect() as c:
        u = lambda s: c.execute(s).fetchone()[0]  # noqa: E731
        print("\n== base")
        print("fatos financeiros", u("SELECT COUNT(*) FROM tb_fato_financeiro"))
        print("fatos operacionais", u("SELECT COUNT(*) FROM tb_fato_operacional"))
        print("fontes", u("SELECT COUNT(*) FROM tb_fonte_dados"))
        print("com arquivo local",
              u("SELECT COUNT(*) FROM tb_fonte_dados WHERE caminho_local <> ''"))
        print("processadas", u("SELECT COUNT(*) FROM tb_fonte_dados"
                               " WHERE status_processamento='PROCESSADO'"))
        print("sem dados", u("SELECT COUNT(*) FROM tb_fonte_dados"
                             " WHERE status_processamento='SEM_DADOS'"))
        print("nao processadas", u("SELECT COUNT(*) FROM tb_fonte_dados"
                                   " WHERE status_processamento='NAO_PROCESSADO'"))
        print("erros", u("SELECT COUNT(*) FROM tb_fonte_dados"
                         " WHERE status_processamento='ERRO'"))
        print("alertas", u("SELECT COUNT(*) FROM tb_quality_alerts"))
        print("fila", u("SELECT COUNT(*) FROM tb_review_queue"))
        print("projecoes", u("SELECT COUNT(*) FROM tb_projecao"))
        print("series projetadas",
              u("SELECT COUNT(DISTINCT nome_empresa || rubrica_padronizada)"
                " FROM tb_projecao"))
        print("confianca media projecao",
              round(u("SELECT AVG(confianca) FROM tb_projecao") or 0, 2))
        print("metodos", [tuple(r) for r in c.execute(
            "SELECT metodo, COUNT(*) FROM tb_projecao GROUP BY 1 ORDER BY 2 DESC")])
        print("scorecards", u("SELECT COUNT(*) FROM tb_qualidade_score"))
        print("dqs medio", round(u("SELECT AVG(dqs) FROM tb_qualidade_score") or 0, 1))
        print("execucoes etl", u("SELECT COUNT(*) FROM tb_etl_execucao"))
        print("tabelas", [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")])
        print("ortopedia", len(INDICATORS), "indicadores")
    _ = one


if __name__ == "__main__":
    main()