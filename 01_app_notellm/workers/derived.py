"""Worker derivados: margens e alavancagem a partir dos fatos trimestrais (QWEN/CGPT).

MARGEM_EBITDA / MARGEM_LIQUIDA (%) e DIVIDA_LIQUIDA_EBITDA (x), gravados como
fatos operacionais para nao misturar unidades com a matriz USD bi.
"""
from __future__ import annotations

from models.database import DatabaseManager
from models.repositories import FatoRepository, QualityRepository


def compute_derived(db: DatabaseManager | None = None) -> dict[str, int]:
    db = db or DatabaseManager()
    fatos, quality = FatoRepository(db), QualityRepository(db)
    resumo = {"margens": 0, "alavancagem": 0, "revisao": 0}
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT nome_empresa, periodo, rubrica_padronizada, valor, id_fonte, confianca"
            " FROM tb_fato_financeiro").fetchall()]
    base: dict[tuple[str, str], dict] = {}
    for r in rows:
        base.setdefault((r["nome_empresa"], r["periodo"]), {})[r["rubrica_padronizada"]] = r
    for (empresa, periodo), vals in base.items():
        rec = (vals.get("RECEITA_LIQUIDA") or {}).get("valor") or 0
        ebitda = (vals.get("EBITDA_AJUSTADO") or {}).get("valor")
        lucro = (vals.get("LUCRO_LIQUIDO") or {}).get("valor")
        div = (vals.get("DIVIDA_LIQUIDA") or {}).get("valor")
        conf = min([vals[k].get("confianca") or 1.0 for k in vals] + [1.0])
        idf = (vals.get("RECEITA_LIQUIDA") or {}).get("id_fonte")
        if rec and rec > 0:
            for rub, num, uni in (("MARGEM_EBITDA", ebitda, "%"), ("MARGEM_LIQUIDA", lucro, "%")):
                if num is None:
                    continue
                margem = round(num / rec * 100, 2)
                if abs(margem) > 500:
                    quality.para_revisao(empresa, periodo, rub, margem, "margem implausivel", conf)
                    resumo["revisao"] += 1
                    continue
                fatos.upsert_operacional(empresa, periodo, rub, margem, uni, idf)
                resumo["margens"] += 1
        if div is not None and ebitda:
            alav = round(div / ebitda, 2) if ebitda != 0 else None
            if alav is None or abs(alav) > 50:
                quality.para_revisao(empresa, periodo, "DIVIDA_LIQUIDA_EBITDA", alav,
                                     "alavancagem implausivel/EBITDA nulo", conf)
                resumo["revisao"] += 1
            else:
                fatos.upsert_operacional(empresa, periodo, "DIVIDA_LIQUIDA_EBITDA", alav, "x", idf)
                resumo["alavancagem"] += 1
    return resumo
