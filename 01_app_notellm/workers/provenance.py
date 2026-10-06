"""M7.27 — score de proveniência: o quanto o número está longe da fonte primária.

Um número de receita da Petrobras coletado do RI 2T26 tem uma cadeia de
trust de um salto. O mesmo número vindo de um XBRL do SEC tem dois (a SEC publica
o mesmo documento, mas é cópia). E uma margem calculada por nós tem três, porque
depende dos dois anteriores e ainda pode estar errada por divisão ou troca de
unidade.

Não existe "certificado": o score é a distância declarada entre o número e o
documento original, e a cadeia fica escrita no próprio fato. Ele não altera
valor nenhum — só diz de onde o valor veio, para quem lê o painel saber quando
pode usar o número e quando precisa conferir no documento.
"""
from __future__ import annotations

from typing import Any

from models.database import DatabaseManager

# profundidade 1 = documento da própria empresa; 2 = cópia regulatória;
# 3 = derivado por nós (depende de outros fatos).
NIVEL_RI = 1
NIVEL_SEC = 2
NIVEL_DERIVADA = 3

ORIGENS: dict[str, tuple[int, str]] = {
    # ---- 1: a empresa publica o número
    "RI": (NIVEL_RI, "RI da própria empresa"),
    "MANUAL": (NIVEL_RI, "arquivo local no Container (RI da empresa)"),
    "CONTAINER": (NIVEL_RI, "arquivo local no Container (RI da empresa)"),
    # ---- 2: cópia regulatória do mesmo documento
    "SEC:10-Q": (NIVEL_SEC, "cópia regulatória (SEC 10-Q)"),
    "SEC:6-K": (NIVEL_SEC, "cópia regulatória (SEC 6-K)"),
    "SEC:20-F": (NIVEL_SEC, "cópia regulatória (SEC 20-F)"),
    "SEC": (NIVEL_SEC, "cópia regulatória (SEC)"),
    # ---- sem fonte declarada: não dá para afirmar de onde veio
    "DESCONHECIDA": (0, "origem não declarada"),
}

# rubricas que calculamos a partir de outros fatos (workers/derived.py)
DERIVADAS = {
    "MARGEM_EBITDA": ("EBITDA_AJUSTADO", "RECEITA_LIQUIDA"),
    "MARGEM_LIQUIDA": ("LUCRO_LIQUIDO", "RECEITA_LIQUIDA"),
    "DIVIDA_LIQUIDA_EBITDA": ("DIVIDA_LIQUIDA", "EBITDA_AJUSTADO"),
}

# score 0..100 por profundidade: 1 -> 100 (fonte primária), 2 -> 70 (cópia
# regulatória), 3 -> 40 (derivado), 0 -> 0 (origem desconhecida).
PESO_NIVEL = {1: 100, 2: 70, 3: 40, 0: 0}

ROTULO_NIVEL = {
    1: "primário",
    2: "secundário",
    3: "derivado",
    0: "desconhecido",
}


def classificar(origem: str | None, derivado_de: tuple[str, ...] | None = None
                ) -> dict[str, Any]:
    """Traduz a origem da fonte (e a fórmula, se houver) em nível + cadeia."""
    origem = (origem or "DESCONHECIDA").strip().upper()
    # "SEC:10-Q/anexo" é a mesma cópia, com peça anexada
    base = origem.split("/")[0]
    if base in ORIGENS:
        nivel, rotulo = ORIGENS[base]
    elif base.startswith("SEC"):
        # formulário novo (10-K, 8-K, ...): continua sendo cópia regulatória.
        # Tratar como "desconhecido" puniria o documento por um código novo.
        nivel, rotulo = NIVEL_SEC, f"cópia regulatória ({base})"
    else:
        nivel, rotulo = 0, "origem não declarada"
    if derivado_de:
        # derivada: um nível acima do insumo mais fraco da fórmula
        cadeia = "derivada: " + " / ".join(derivado_de)
        return {"profundidade": NIVEL_DERIVADA, "rotulo": ROTULO_NIVEL[NIVEL_DERIVADA],
                "origem": "DERIVADA", "cadeia": cadeia,
                "score": PESO_NIVEL[NIVEL_DERIVADA]}
    return {"profundidade": nivel, "rotulo": ROTULO_NIVEL[nivel], "origem": origem,
            "cadeia": rotulo, "score": PESO_NIVEL[nivel]}


def _origem_da_fonte(db: DatabaseManager, id_fonte: int | None) -> str | None:
    if id_fonte is None:
        return None
    with db.connect() as conn:
        row = conn.execute("SELECT origem FROM tb_fonte_dados WHERE id_fonte = ?",
                           (id_fonte,)).fetchone()
    return row["origem"] if row else None


def anotar_fatos(db: DatabaseManager | None = None) -> dict[str, int]:
    """Grava profundidade/origem/cadeia em todos os fatos. Idempotente.

    Roda separado do ETL de propósito: a coluna nova pode ser preenchida sem
    reprocessar documento nenhum, e reclassificar a origem não invalida o fato.
    """
    db = db or DatabaseManager()
    resumo = {"financeiro": 0, "operacional": 0, "primario": 0, "secundario": 0,
              "derivado": 0, "desconhecido": 0}

    def _contabiliza(p: dict[str, Any]) -> None:
        resumo[{"primário": "primario", "secundário": "secundario",
                "derivado": "derivado"}.get(p["rotulo"], "desconhecido")] += 1

    # cache de origem por id_fonte: a mesma fonte atende dezenas de fatos e
    # a consulta por linha custaria uma leitura por fato
    origens: dict[int, str | None] = {}
    with db.connect() as conn:
        origens = {r["id_fonte"]: r["origem"] for r in
                   conn.execute("SELECT id_fonte, origem FROM tb_fonte_dados").fetchall()}

    with db.connect() as conn:
        fins = [dict(r) for r in conn.execute(
            "SELECT id_fato, id_fonte, rubrica_padronizada FROM tb_fato_financeiro"
        ).fetchall()]
        for f in fins:
            p = classificar(origens.get(f["id_fonte"]) if f["id_fonte"] is not None else None)
            conn.execute(
                "UPDATE tb_fato_financeiro SET profundidade_proveniencia = ?,"
                " origem_proveniencia = ?, cadeia_proveniencia = ? WHERE id_fato = ?",
                (p["profundidade"], p["origem"], p["cadeia"], f["id_fato"]))
            resumo["financeiro"] += 1
            _contabiliza(p)
        ops = [dict(r) for r in conn.execute(
            "SELECT id_operacional, id_fonte, indicador FROM tb_fato_operacional"
        ).fetchall()]
        for o in ops:
            formula = DERIVADAS.get(o["indicador"])
            p = classificar(origens.get(o["id_fonte"]) if o["id_fonte"] is not None else None,
                            derivado_de=formula)
            conn.execute(
                "UPDATE tb_fato_operacional SET profundidade_proveniencia = ?,"
                " origem_proveniencia = ?, cadeia_proveniencia = ? WHERE id_operacional = ?",
                (p["profundidade"], p["origem"], p["cadeia"], o["id_operacional"]))
            resumo["operacional"] += 1
            _contabiliza(p)
        conn.commit()
    return resumo


def resumo_cadeia(db: DatabaseManager | None = None) -> dict[str, Any]:
    """Contagem e score médio por nível, no formato que a web/GUI/CLI mostram."""
    db = db or DatabaseManager()
    with db.connect() as conn:
        linhas = [dict(r) for r in conn.execute(
            "SELECT profundidade_proveniencia AS p, COUNT(*) AS n FROM tb_fato_financeiro"
            " GROUP BY profundidade_proveniencia").fetchall()]
        linhas += [dict(r) for r in conn.execute(
            "SELECT profundidade_proveniencia AS p, COUNT(*) AS n FROM tb_fato_operacional"
            " GROUP BY profundidade_proveniencia").fetchall()]
    contagem: dict[int, int] = {}
    for l in linhas:
        if l["p"] is not None:
            contagem[int(l["p"])] = contagem.get(int(l["p"]), 0) + int(l["n"])
    total = sum(contagem.values())
    por_nivel = [{"profundidade": p, "rotulo": ROTULO_NIVEL.get(p, "?"),
                  "score": PESO_NIVEL.get(p, 0), "fatos": n,
                  "pct": round(n / total * 100, 1) if total else 0.0}
                 for p, n in sorted(contagem.items(), reverse=True)]
    score_medio = (round(sum(PESO_NIVEL.get(p, 0) * n for p, n in contagem.items())
                         / total, 1) if total else 0.0)
    return {"total": total, "por_nivel": por_nivel, "score_medio": score_medio,
            "pior_profundidade": max(contagem) if contagem else None}


def por_rubrica(db: DatabaseManager | None = None) -> list[dict[str, Any]]:
    """Nível médio por rubrica: onde a base é mais fraca é onde o número pesa menos."""
    db = db or DatabaseManager()
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT rubrica_padronizada AS rubrica, COUNT(*) AS fatos,"
            " AVG(profundidade_proveniencia) AS prof, AVG(confianca) AS conf"
            " FROM tb_fato_financeiro WHERE profundidade_proveniencia IS NOT NULL"
            " GROUP BY rubrica_padronizada ORDER BY prof DESC, fatos DESC").fetchall()]
    for r in rows:
        prof = round(r["prof"] or 0, 2)
        r["profundidade"] = prof
        r["rotulo"] = ROTULO_NIVEL.get(int(round(prof)), "?")
        r["score"] = PESO_NIVEL.get(int(round(prof)), 0)
        r["confianca"] = round(r["conf"] or 0, 3)
    return rows


def cadeia_de(db: DatabaseManager, nome_empresa: str, periodo: str) -> list[dict[str, Any]]:
    """A trilha completa de um trimestre: cada fato e de onde veio."""
    db = db or DatabaseManager()
    with db.connect() as conn:
        fin = [dict(r) for r in conn.execute(
            "SELECT rubrica_padronizada AS item, valor, moeda, confianca,"
            " origem_proveniencia AS origem, cadeia_proveniencia AS cadeia,"
            " profundidade_proveniencia AS prof, id_fonte"
            " FROM tb_fato_financeiro WHERE nome_empresa = ? AND periodo = ?"
            " ORDER BY rubrica_padronizada", (nome_empresa, periodo)).fetchall()]
        ops = [dict(r) for r in conn.execute(
            "SELECT indicador AS item, valor, unidade_medida AS moeda, origem_proveniencia,"
            " cadeia_proveniencia AS cadeia, profundidade_proveniencia AS prof, id_fonte"
            " FROM tb_fato_operacional WHERE nome_empresa = ? AND periodo = ?"
            " ORDER BY indicador", (nome_empresa, periodo)).fetchall()]
    for r in fin + ops:
        prof = r["prof"]
        r["profundidade"] = int(prof) if prof is not None else None
        r["rotulo"] = ROTULO_NIVEL.get(int(prof), "?") if prof is not None else "?"
        r["score"] = PESO_NIVEL.get(int(prof), 0) if prof is not None else 0
    return fin + ops