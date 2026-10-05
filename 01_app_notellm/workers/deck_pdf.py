"""Gera o slide deck oficial em PDF (reportlab) a partir do banco + docs."""
from __future__ import annotations

from pathlib import Path

from config import DOCS_DIR
from models.database import DatabaseManager
from models.repositories import FatoRepository

TITULO = "PetroAnalytics PoC — Benchmark Petrobras vs Pares"


def _dados(db: DatabaseManager, periodo: str = "2026Q2") -> dict:
    fatos = FatoRepository(db)
    matriz = {(r["nome_empresa"], r["rubrica_padronizada"]): r["valor"]
              for r in fatos.matriz(periodo)}
    cont = fatos.contar()
    with db.connect() as conn:
        n_alert = conn.execute("SELECT COUNT(*) c FROM tb_quality_alerts").fetchone()["c"]
        n_rev = conn.execute("SELECT COUNT(*) c FROM tb_review_queue").fetchone()["c"]
    return {"matriz": matriz, "cont": cont, "alertas": n_alert, "revisao": n_rev}


def gerar_pdf(destino: Path | None = None, periodo: str = "2026Q2",
              db: DatabaseManager | None = None) -> str:
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib import colors

    db = db or DatabaseManager()
    dados, matriz = _dados(db, periodo), _dados(db, periodo)["matriz"]
    destino = Path(destino) if destino else DOCS_DIR / "SLIDES_APRESENTACAO.pdf"
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(destino), pagesize=landscape(A4),
                            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.5 * cm)
    estilos = getSampleStyleSheet()
    h1, h2, corpo = estilos["Heading1"], estilos["Heading2"], estilos["BodyText"]

    def tabela(matriz_rows: list[list]) -> Table:
        t = Table(matriz_rows, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#007a4d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        return t

    empresas = ["PETROBRAS", "SHELL", "BP", "CHEVRON", "EXXONMOBIL", "TOTALENERGIES", "EQUINOR"]
    rubs = ["RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO", "FCO", "DIVIDA_LIQUIDA"]
    linhas = [["Indicador (USD bi)"] + empresas]
    for rub in rubs:
        linhas.append([rub] + [f"{matriz.get((e, rub), float('nan')):.2f}"
                               if (e, rub) in matriz else "—" for e in empresas])

    story = [
        Paragraph(TITULO, h1),
        Paragraph(f"Sistema de Inteligência Financeira e Operacional (Petróleo & Gás) — {periodo}", h2),
        Spacer(1, 0.5 * cm),
        Paragraph("1. Problema: 7 RIs publicam o mesmo fato em 7 formatos (PDF/XLSX/TR), 3 moedas, 2 idiomas.", corpo),
        Paragraph("2. Arquitetura MVC-W + SQLite: Model (6 tabelas), Workers (scan/hash, parse_*, SEC CIK, qualidade), "
                  "Controllers finos, Views Web (Plotly) + GUI (PySide6).", corpo),
        Paragraph(f"3. Base: {dados['cont']['fontes']} fontes, {dados['cont']['fatos']} fatos, "
                  f"{dados['alertas']} alertas, {dados['revisao']} itens em revisão.", corpo),
        PageBreak(),
        Paragraph(f"Matriz comparativa {periodo} (USD bi)", h2),
        tabela(linhas),
        Spacer(1, 0.5 * cm),
        Paragraph("4. Qualidade: negativos, spikes QoQ, plausibilidade, cobertura, divergência RI×SEC; "
                  "confiança <0,70 vai para revisão; fatos bons nunca são rebaixados.", corpo),
        Paragraph("5. Atualização trimestral: soltar arquivos na pasta + <b>python app_main.py trimestre --novo 2026Q3</b> "
                  "(scan incremental, ETL, SEC, derivados, painel, docs).", corpo),
        Paragraph("6. Escala: +1 linha por empresa (COMPANIES+CIK), +1 regra por indicador (depara.py).", corpo),
    ]
    doc.build(story)
    return str(destino)
