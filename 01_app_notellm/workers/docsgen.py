"""Regeneracao dos entregaveis Markdown a partir do banco (usado pelo `trimestre`)."""
from __future__ import annotations

from config import DOCS_DIR
from models.database import DatabaseManager


def gerar_catalogo(db: DatabaseManager | None = None) -> str:
    import sqlite3
    db = db or DatabaseManager()
    conn = db.connect()
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) c FROM tb_fonte_dados").fetchone()["c"]
    linhas = ["# Catalogo de fontes utilizadas (gerado pelo ETL)", "",
               f"Total de arquivos catalogados: **{total}**.",
               "Origem: portais oficiais de RI + SEC EDGAR + Investidor10 + Container local.",
               "Rastreabilidade: cada fato carrega `id_fonte`; espelhos em `data/sources_catalog.json` e `.csv`.", "",
               "## Por empresa x tipo x status", "", "| Empresa | Tipo | Status | Qtd |", "|---|---|---|---|"]
    for r in conn.execute("SELECT nome_empresa, tipo_arquivo, status_processamento, COUNT(*) q"
                          " FROM tb_fonte_dados GROUP BY 1,2,3 ORDER BY 1,2,3"):
        linhas.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |")
    linhas += ["", "## Arquivos com dados extraidos (amostra, 30 primeiros PROCESSADO)", "",
                "| ID | Empresa | Arquivo | Download |", "|---|---|---|---|"]
    for r in conn.execute("SELECT id_fonte, nome_empresa, caminho_local, data_download FROM tb_fonte_dados"
                          " WHERE status_processamento='PROCESSADO' ORDER BY 1 LIMIT 30"):
        nome = (r[2] or r[1] or "").replace("\\", "/").split("/")[-1]
        linhas.append(f"| {r[0]} | {r[1]} | {nome} | {r[3]} |")
    conn.close()
    destino = DOCS_DIR / "CATALOGO_FONTES.md"
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return str(destino)


def gerar_evidencias(db: DatabaseManager | None = None) -> str:
    db = db or DatabaseManager()
    with db.connect() as conn:
        alertas = [dict(r) for r in conn.execute(
            "SELECT tipo_alerta, descricao, severidade FROM tb_quality_alerts ORDER BY 1 LIMIT 60").fetchall()]
        revisao = [dict(r) for r in conn.execute(
            "SELECT nome_empresa, periodo, rubrica, motivo, status FROM tb_review_queue"
            " ORDER BY criado_em DESC LIMIT 60").fetchall()]
        cob = [tuple(r) for r in conn.execute(
            "SELECT nome_empresa, periodo, COUNT(*) FROM tb_fato_financeiro GROUP BY 1,2 ORDER BY 1,2").fetchall()]
    ev = ["# Evidencias dos controles de qualidade (gerado pelo ETL)", "",
          "## Auditoria (tb_quality_alerts)", "", "| Tipo | Descrição | Severidade |", "|---|---|---|"]
    ev += [f"| {a['tipo_alerta']} | {a['descricao'][:120]} | {a['severidade']} |" for a in alertas]
    ev += ["", "## Fila de revisão (tb_review_queue, top 60)", "",
           "| Empresa | Período | Rubrica | Motivo | Status |", "|---|---|---|---|---|"]
    ev += [f"| {r['nome_empresa']} | {r['periodo']} | {r['rubrica']} | {(r['motivo'] or '')[:110]} | {r['status']} |"
           for r in revisao]
    ev += ["", "## Cobertura (fatos por empresa x periodo)", "", "| Empresa | Periodo | Fatos |", "|---|---|---|"]
    ev += [f"| {e} | {p} | {c} |" for e, p, c in cob]
    destino = DOCS_DIR / "EVIDENCIAS_QUALIDADE.md"
    destino.write_text("\n".join(ev) + "\n", encoding="utf-8")
    return str(destino)
