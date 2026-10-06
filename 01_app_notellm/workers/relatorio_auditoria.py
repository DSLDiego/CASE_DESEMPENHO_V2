"""Worker relatorio_auditoria: relatório da auditoria em PDF (M2.10).

O relatório é a peça que se entrega ao auditor: quem decidiu o quê, quando e com
qual comentário, no período pedido. Todos os números são lidos do banco
(`resumo_auditoria` + `tb_auditoria_decisao`), então o PDF não pode divergir do
painel — é a mesma fonte.

Janela de período (`de`/`ate`, datas YYYY-MM-DD) filtra a trilha de decisão. Sem
os dois, o relatório cobre tudo que existe na base: a ausência de filtro é um
relatório completo, não um relatório vazio.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from config import DOCS_DIR
from models.database import DatabaseManager
from models.repositories import QualityRepository

VERDE = "#007a4d"
CINZA = "#5a6472"
DATA_FMT = "%Y-%m-%d"


def _periodo(de: str | None, ate: str | None) -> tuple[str, str, str]:
    """(de_sql, ate_sql, rotulo) — limites inclusivos em data, não em string vazia."""
    hoje = datetime.now().strftime(DATA_FMT)
    de_sql = f"{de} 00:00:00" if de else "0000-01-01 00:00:00"
    ate_sql = f"{ate} 23:59:59" if ate else "9999-12-31 23:59:59"
    rotulo = f"{de or 'início'} a {ate or hoje}"
    return de_sql, ate_sql, rotulo


def decisoes_periodo(db: DatabaseManager, de: str | None = None,
                     ate: str | None = None) -> list[dict[str, Any]]:
    """Trilha de decisão do período, com o item auditado resolvido (empresa/periodo).

    A decisão aponta para `registro_id`; sem o JOIN o relatório mostraria "#12
    ACEITO" e o auditor não saberia o que foi aceito.
    """
    de_sql, ate_sql, _ = _periodo(de, ate)
    with db.connect() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT d.id_decisao, d.decisao, d.comentario, d.decidido_em, d.decidido_por,
                      d.registro_id, d.tabela_ref,
                      r.nome_empresa, r.periodo, r.rubrica, r.status, r.motivo
               FROM tb_auditoria_decisao d
               LEFT JOIN tb_review_queue r
                      ON d.tabela_ref = 'tb_review_queue' AND r.id_review = d.registro_id
               WHERE d.decidido_em >= ? AND d.decidido_em <= ?
               ORDER BY d.decidido_em DESC, d.id_decisao DESC""",
            (de_sql, ate_sql)).fetchall()]


def _dados(db: DatabaseManager, de: str | None, ate: str | None) -> dict[str, Any]:
    quality = QualityRepository(db)
    resumo = quality.resumo_auditoria()
    decisoes = decisoes_periodo(db, de, ate)
    por_decisao: dict[str, int] = {}
    por_por: dict[str, int] = {}
    for d in decisoes:
        por_decisao[d["decisao"]] = por_decisao.get(d["decisao"], 0) + 1
        quem = d["decidido_por"] or "(não informado)"
        por_por[quem] = por_por.get(quem, 0) + 1
    _, _, rotulo = _periodo(de, ate)
    return {"resumo": resumo, "decisoes": decisoes, "periodo": rotulo,
            "total_decisoes": len(decisoes), "por_decisao": por_decisao,
            "por_decidido_por": por_por,
            "abertas": resumo["fila_aberta"],
            "revisoes": quality.listar_revisao(apenas_abertos=False)}


def gerar_relatorio(destino: Path | None = None, de: str | None = None,
                    ate: str | None = None,
                    db: DatabaseManager | None = None) -> str:
    """Gera o PDF da auditoria e devolve o caminho."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)

    db = db or DatabaseManager()
    d = _dados(db, de, ate)
    destino = Path(destino) if destino else DOCS_DIR / "RELATORIO_AUDITORIA.pdf"
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(destino), pagesize=A4,
                            leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.4 * cm)
    est = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=est["Title"], fontSize=20,
                        textColor=colors.HexColor(VERDE))
    h2 = ParagraphStyle("h2", parent=est["Heading2"], fontSize=14,
                        textColor=colors.HexColor(VERDE), spaceAfter=4)
    corpo = ParagraphStyle("corpo", parent=est["BodyText"], fontSize=9.5, leading=13,
                           textColor=colors.HexColor(CINZA))
    nota = ParagraphStyle("nota", parent=corpo, fontSize=8, leading=11)

    def _esc(texto: Any) -> str:
        """Escapa para o Paragraph: um '<' no comentário quebraria o XML do PDF."""
        return (str(texto if texto is not None else "—")
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def tabela(cabecalho: list[str], linhas: list[list], larguras: list[float]) -> Table:
        t = Table([cabecalho] + linhas, colWidths=larguras, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(VERDE)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5dde5")),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f7f9fa")])]))
        return t

    r = d["resumo"]
    triagem = ", ".join(f"{k}: {v}" for k, v in sorted(d["por_decisao"].items())) or "—"
    severidade = ", ".join(f"{k}: {v}" for k, v in sorted(r["por_severidade"].items())) or "—"
    story = [
        Paragraph("Relatório de Auditoria de Dados", h1),
        Paragraph(f"PetroAnalytics · período: {_esc(d['periodo'])}", corpo),
        Spacer(1, 0.3 * cm),
        Paragraph("1. Situação da auditoria", h2),
        tabela(["Indicador", "Valor"],
               [["Alertas ativos", r["total_alertas"]],
                ["Itens na fila de revisão", r["fila_total"]],
                ["Abertos (aguardando decisão)", r["fila_aberta"]],
                ["Taxa de resolução", f"{r['taxa_resolucao']}%"],
                ["Aging 0–7 dias", r["aging"]["0-7d"]],
                ["Aging 8–30 dias", r["aging"]["8-30d"]],
                ["Aging +30 dias", r["aging"][">30d"]],
                ["Decisões no período", d["total_decisoes"]],
                ["Composição das decisões", _esc(triagem)]],
               [8 * cm, 9.6 * cm]),
        Spacer(1, 0.3 * cm),
        Paragraph(f"Severidade dos alertas: {_esc(severidade)}", corpo),
        Paragraph(f"Tipos mais frequentes: "
                  f"{_esc(', '.join(f'{k} ({v})' for k, v in list(r['por_tipo'].items())[:6]) or '—')}",
                  corpo),
        Spacer(1, 0.4 * cm),
        Paragraph("2. Quem decidiu", h2),
        tabela(["Decidido por", "Decisões"],
               [[_esc(k), v] for k, v in sorted(d["por_decidido_por"].items(),
                                                key=lambda kv: -kv[1])]
               or [["—", 0]],
               [11 * cm, 6.6 * cm]),
        PageBreak(),
        Paragraph("3. Trilha de decisão do período", h2),
        Paragraph("Cada linha é uma decisão de triagem: o que foi aceito, rejeitado "
                  "ou ignorado, por quem e com que justificativa. A linha continua "
                  "registrada mesmo depois de reabertura — a trilha é completa.",
                  nota),
        Spacer(1, 0.2 * cm),
    ]
    linhas = [[_esc(x["decidido_em"]), _esc(x["nome_empresa"] or f"({x['tabela_ref']} "
              f"#{x['registro_id']})"), _esc(x["periodo"]), _esc(x["rubrica"]),
               _esc(x["decisao"]), _esc(x["decidido_por"]),
               _esc((x["comentario"] or "")[:90] or (x["motivo"] or "")[:90])]
              for x in d["decisoes"]]
    story.append(tabela(["Quando", "Empresa", "Período", "Item", "Decisão", "Por", "Comentário"],
                        linhas or [["—"] * 7],
                        [2.5 * cm, 2.2 * cm, 1.7 * cm, 2.4 * cm, 2.0 * cm, 2.2 * cm, 4.6 * cm]))
    story += [Spacer(1, 0.4 * cm),
              Paragraph("4. Fila de revisão no encerramento", h2),
              Paragraph("Estado atual de cada item auditado, para saber o que ficou "
                        "pendente depois das decisões acima.", nota),
              Spacer(1, 0.2 * cm)]
    revisoes = d["revisoes"][:300]
    story.append(tabela(
        ["#", "Empresa", "Período", "Item", "Motivo", "Confiança", "Status"],
        [[r_["id_review"], _esc(r_["nome_empresa"]), _esc(r_["periodo"]),
          _esc(r_["rubrica"]), _esc(r_["motivo"][:80]), f"{r_['confianca'] or 0:.2f}",
          _esc(r_["status"])] for r_ in revisoes] or [["—"] * 7],
        [1.0 * cm, 2.6 * cm, 1.8 * cm, 2.6 * cm, 6.0 * cm, 1.6 * cm, 2.0 * cm]))
    if len(d["revisoes"]) > len(revisoes):
        story.append(Paragraph(
            f"Exibidos os {len(revisoes)} itens mais recentes de {len(d['revisoes'])}. "
            f"O restante está em <b>app_main.py auditoria fila --todas</b>.", nota))
    story += [Spacer(1, 0.5 * cm),
              Paragraph(f"Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · "
                        f"fonte: tb_quality_alerts, tb_review_queue e tb_auditoria_decisao.", nota)]
    doc.build(story)
    return str(destino)