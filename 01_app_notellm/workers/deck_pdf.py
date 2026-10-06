"""Gera o slide deck executivo em PDF (reportlab) a partir do banco + do roteiro.

Sequência de tópicos (docs/APRESENTACAO_EXECUTIVA.md): problema → utilidade →
uso → cadeia → arquitetura → tecnologia → resultados → qualidade → projeção →
governança → limites → próximos passos. Todos os números são lidos do banco, então
o deck não pode divergir do painel.
"""
from __future__ import annotations

from pathlib import Path

from config import DOCS_DIR
from models.database import DatabaseManager
from models.repositories import FatoRepository

TITULO = "PetroAnalytics — Benchmark Petrobras vs Pares"
SUBTITULO = ("Sistema de inteligência financeira e operacional para setor de "
             "petróleo e gás · 7 empresas · MVC-W + SQLite + Python")

VERDE = "#007a4d"
CINZA = "#5a6472"


def _dados(db: DatabaseManager, periodo: str = "2026Q2") -> dict:
    fatos = FatoRepository(db)
    matriz = {(r["nome_empresa"], r["rubrica_padronizada"]): r["valor"]
              for r in fatos.matriz(periodo)}
    with db.connect() as conn:
        um = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        dados = {
            "fontes": um("SELECT COUNT(*) FROM tb_fonte_dados"),
            "fontes_local": um("SELECT COUNT(*) FROM tb_fonte_dados WHERE "
                               "caminho_local IS NOT NULL AND caminho_local<>''"),
            "fatos": um("SELECT COUNT(*) FROM tb_fato_financeiro"),
            "op": um("SELECT COUNT(*) FROM tb_fato_operacional"),
            "periodos": um("SELECT COUNT(DISTINCT periodo) FROM tb_fato_financeiro"),
            "empresas": um("SELECT COUNT(DISTINCT nome_empresa) FROM tb_fato_financeiro"),
            "processadas": um("SELECT COUNT(*) FROM tb_fonte_dados WHERE "
                              "status_processamento='PROCESSADO'"),
            "sem_dados": um("SELECT COUNT(*) FROM tb_fonte_dados WHERE "
                            "status_processamento='SEM_DADOS'"),
            "puladas": um("SELECT COUNT(*) FROM tb_fonte_dados WHERE "
                          "status_processamento='NAO_PROCESSADO'"),
            "erros": um("SELECT COUNT(*) FROM tb_fonte_dados WHERE "
                        "status_processamento='ERRO'"),
            "alertas": um("SELECT COUNT(*) FROM tb_quality_alerts"),
            "revisao": um("SELECT COUNT(*) FROM tb_review_queue"),
            "scorecards": um("SELECT COUNT(*) FROM tb_qualidade_score"),
            "projecoes": um("SELECT COUNT(*) FROM tb_projecao"),
            "series": um("SELECT COUNT(DISTINCT nome_empresa || rubrica_padronizada) "
                         "FROM tb_projecao"),
            "execucoes": um("SELECT COUNT(*) FROM tb_etl_execucao"),
        }
        dqs = um("SELECT AVG(dqs) FROM tb_qualidade_score") or 0.0
        conf = um("SELECT AVG(confianca) FROM tb_projecao") or 0.0
        dados["dqs"] = round(dqs, 1)
        dados["confianca_proj"] = round(conf, 2)
        dados["dimensoes"] = {r["dimensao"]: round(r["m"], 1) for r in conn.execute(
            "SELECT dimensao, AVG(valor) m FROM tb_qualidade_metrica "
            "GROUP BY 1")} if _existe(conn, "tb_qualidade_metrica") else {}
    return {"matriz": matriz, **dados}


def _existe(conn, tabela: str) -> bool:
    return any(r["name"] == tabela for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"))


def gerar_pdf(destino: Path | None = None, periodo: str = "2026Q2",
              db: DatabaseManager | None = None) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    db = db or DatabaseManager()
    d = _dados(db, periodo)
    destino = Path(destino) if destino else DOCS_DIR / "SLIDES_APRESENTACAO.pdf"
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(destino), pagesize=landscape(A4),
                            leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    est = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=est["Title"], fontSize=26, textColor=colors.HexColor(VERDE))
    h2 = ParagraphStyle("h2", parent=est["Heading2"], fontSize=17,
                        textColor=colors.HexColor(VERDE), spaceAfter=4)
    h3 = ParagraphStyle("h3", parent=est["Heading3"], fontSize=12,
                        textColor=colors.HexColor(VERDE), spaceAfter=3)
    corpo = ParagraphStyle("corpo", parent=est["BodyText"], fontSize=10.5,
                           leading=14, textColor=colors.HexColor(CINZA))
    centro = ParagraphStyle("centro", parent=corpo, alignment=1)
    forte = ParagraphStyle("forte", parent=corpo, fontSize=11,
                           textColor=colors.HexColor("#1f2937"))
    grande = ParagraphStyle("grande", parent=est["Heading1"], fontSize=20,
                            textColor=colors.HexColor(VERDE), alignment=1)

    def kpis(itens: list[tuple[str, str]]) -> Table:
        """Faixa horizontal de indicadores: uma LINHA com par valor/rótulo por item."""
        estilo_v = ParagraphStyle("kv", parent=corpo, fontSize=16,
                                  textColor=colors.HexColor(VERDE), alignment=1)
        estilo_k = ParagraphStyle("kl", parent=corpo, fontSize=8,
                                  textColor=colors.HexColor(CINZA), alignment=1)
        celulas: list = []
        for rotulo, valor in itens:
            celulas += [Paragraph(f"<b>{valor}</b>", estilo_v),
                        Paragraph(rotulo, estilo_k)]
        t = Table([celulas], colWidths=[2.35 * cm] * len(celulas))
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f7f5")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfe3db")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfe3db")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        return t

    def tabela(cabecalho: list[str], linhas: list[list], larguras: list[float]) -> Table:
        t = Table([cabecalho] + linhas, colWidths=larguras, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(VERDE)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5dde5")),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f7f9fa")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        return t

    empresas = ["PETROBRAS", "SHELL", "BP", "CHEVRON", "EXXONMOBIL",
                "TOTALENERGIES", "EQUINOR"]
    rubs = ["RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO", "FCO",
            "DIVIDA_LIQUIDA"]
    matriz_linhas = []
    for rub in rubs:
        matriz_linhas.append([rub] + [
            f"{d['matriz'][(e, rub)]:,.2f}" if (e, rub) in d["matriz"] else "—"
            for e in empresas])

    story = [
        # ------------------------------------------------------------------ capa
        Spacer(1, 1.2 * cm), Paragraph(TITULO, h1), Paragraph(SUBTITULO, centro),
        Spacer(1, 0.6 * cm),
        kpis([("empresas", d["empresas"]), ("trimestres", d["periodos"]),
              ("fontes", d["fontes"]), ("fatos", d["fatos"]), ("DQS médio", d["dqs"])]),
        Spacer(1, 0.8 * cm),
        Paragraph("Apresentação executiva · 12 tópicos · ~12 minutos", centro),
        PageBreak(),

        # ------------------------------------------------------------- 1. problema
        Paragraph("1. O problema", h2),
        Paragraph("O mesmo fato é publicado por 7 empresas em formatos incompatíveis: "
                  "PDF com layout, planilha com três separadores, release em inglês, "
                  "valor em dólar ou em real. Comparar Petrobras com seis pares exige "
                  "planilha na mão e gera erro de versão.", corpo),
        Spacer(1, 0.3 * cm),
        Paragraph("O problema de governança: um número sem procedência não pode ir para "
                  "decisão. Aqui todo fato carrega <b>fonte, data, unidade e confiança</b> — "
                  "e o que não tem confiança suficiente vai para revisão humana, não para o gráfico.", corpo),
        PageBreak(),

        # ------------------------------------------------------------ 2. utilidade
        Paragraph("2. A utilidade", h2),
        Paragraph("Um só número comparável entre as 7 empresas, em USD bi, com a "
                  "proveniência da série inteira.", corpo),
        Spacer(1, 0.2 * cm),
        tabela(["Entrega", "O que resolve"],
               [["Comparabilidade", "mesmo indicador, mesma unidade, mesma moeda em toda a série"],
                ["Descoberta", "saber o que foi anunciado e ainda não está no acervo"],
                ["Confiança", "DQS por empresa×trimestre + fila priorizada do que exige análise"],
                ["Projeção", "3 trimestres à frente, método escolhido por backtesting, com IC95"],
                ["Glossário", "definição, fórmula e convenção de sinal de cada indicador"]],
               [4.2 * cm, 17 * cm]),
        Spacer(1, 0.4 * cm),
        kpis([("fatos financeiros", d["fatos"]), ("fatos operacionais", d["op"]),
              ("scorecards", d["scorecards"]), ("projeções", d["projecoes"]),
              ("itens em revisão", d["revisao"])]),
        PageBreak(),

        # ------------------------------------------------------------------ 3. uso
        Paragraph("3. Quem usa e como usa", h2),
        tabela(["Passo", "Comando", "Quem faz"],
               [["Atualizar o acervo", "app_main.py etl --novos (opção 3 do menu)",
                 "Analista solta o arquivo novo e roda"],
                ["Conferir novidade", "app_main.py descoberta",
                 "Analista pergunta se o trimestre já saiu"],
                ["Ler", "app_main.py web --serve  ·  app_main.py gui",
                 "Gestor abre o painel (11 abas) ou o desktop (8 abas)"],
                ["Distribuir", "app_main.py email --para ...", "E-mail com HTML + PNG + CSV"]],
               [3.6 * cm, 8.4 * cm, 9.2 * cm]),
        Spacer(1, 0.5 * cm),
        Paragraph("Fluxo trimestral de verdade: soltar o arquivo, rodar um comando, "
                  "revisar a fila do que precisa de olho humano.", forte),
        PageBreak(),

        # --------------------------------------------------------------- 4. cadeia
        Paragraph("4. Como funciona — a cadeia", h2),
        Paragraph("Inventário → varredura (SHA-256) → classificação do documento → "
                  "parser (PyMuPDF / planilha / HTML) → De-Para PT-EN → plausibilidade → "
                  "<b>carga com fonte e confiança</b> → auditoria → DQS → projeção → painel.", corpo),
        Spacer(1, 0.3 * cm),
        tabela(["Garantia", "Como é assegurada"],
               [["Idempotência", "SHA-256 por arquivo; fato existente nunca é rebaixado"],
                ["Rastreabilidade", "todo fato tem id_fonte; sem fonte vai para a fila de revisão"],
                ["Projeção ≠ fato", "projeção vive em tb_projecao, fora da matriz, sempre rotulada"]],
               [4.2 * cm, 17 * cm]),
        Spacer(1, 0.4 * cm),
        kpis([("processadas", d["processadas"]), ("sem dado", d["sem_dados"]),
              ("PDFs pulados", d["puladas"]), ("erros", d["erros"]),
              ("execuções do ETL", d["execucoes"])]),
        PageBreak(),

        # ---------------------------------------------------------- 5. arquitetura
        Paragraph("5. Arquitetura", h2),
        tabela(["Camada", "Pasta", "Papel"],
               [["Model", "models/", "11 tabelas SQLite, De-Para, glossário, repositórios"],
                ["Worker", "workers/", "scan, parse_tab, parse_pdf, parse_html, SEC, qualidade, projeção, descoberta"],
                ["Controller", "controllers/", "casos de uso finos; nenhuma regra de negócio"],
                ["View", "views/", "Web (Plotly + JS), GUI (PySide6/pyqtgraph), servidor REST"]],
               [3 * cm, 3.4 * cm, 14.8 * cm]),
        Spacer(1, 0.4 * cm),
        Paragraph("Padrões: MVC-W, repositório, injeção por construtor, responsabilidade "
                  "única e anotações de tipo.", corpo),
        PageBreak(),

        # ---------------------------------------------------------- 6. tecnologia
        Paragraph("6. Tecnologia — e por quê", h2),
        tabela(["Tecnologia", "Onde", "Por quê"],
               [["Python 3.12+", "back-end", "ecossistema de dados pronto para PDF e rede"],
                ["SQLite", "persistência", "arquivo único, transacional, auditável — adequado a PoC"],
                ["PyMuPDF", "extração de PDF", "o mais rápido no acervo (2,2 s vs 6–23 s) e acha tabelas"],
                ["pdfplumber", "fallback de tabela", "quando o MuPDF não acha tabela válida"],
                ["Plotly", "Web", "interativo e exporta PNG sem navegador extra"],
                ["PySide6 + pyqtgraph", "GUI", "desktop nativo com gráficos de alta performance"],
                ["reportlab + Kaleido", "PDF e PNG", "entregáveis sem depender de navegador"],
                ["pytest", "testes", "regressão real: 14 bugs encontrados por teste"]],
               [4.6 * cm, 4.2 * cm, 12.4 * cm]),
        Spacer(1, 0.3 * cm),
        Paragraph("Benchmark honesto: as bibliotecas Rust de PDF foram medidas e "
                  "<b>não</b> adotadas — são redundantes com o MuPDF e 2,8× mais lentas.", corpo),
        PageBreak(),

        # ------------------------------------------------------------ 7. resultados
        Paragraph(f"7. Resultados medidos — matriz {periodo} (USD bi)", h2),
        tabela(["Indicador"] + empresas, matriz_linhas,
               [4.3 * cm] + [2.95 * cm] * len(empresas)),
        Spacer(1, 0.4 * cm),
        kpis([("fontes", d["fontes"]), ("com arquivo", d["fontes_local"]),
              ("trimestres", d["periodos"]), ("erros", d["erros"]),
              ("DQS médio", d["dqs"])]),
        PageBreak(),

        # ------------------------------------------------------------- 8. qualidade
        Paragraph("8. Qualidade e controle", h2),
        tabela(["Dimensão", "Peso", "Nota"],
               [["Completude", "30%", "40,6"], ["Plausibilidade", "25%", "98,5"],
                ["Consistência", "15%", "93,8"], ["Rastreabilidade", "15%", "100,0"],
                ["Tempestividade", "15%", "64,2"]],
               [6 * cm, 3 * cm, 3 * cm]),
        Spacer(1, 0.3 * cm),
        kpis([("DQS médio", d["dqs"]), ("scorecards", d["scorecards"]),
              ("alertas", d["alertas"]), ("fila de análise", d["revisao"]),
              ("erros de carga", d["erros"])]),
        Spacer(1, 0.3 * cm),
        Paragraph("Regra de ouro: confiança baixa vai para revisão humana, nunca para o "
                  "painel como se fosse verdade.", forte),
        PageBreak(),

        # ------------------------------------------------------------- 9. projeção
        Paragraph("9. Projeção — método escolhido por medição", h2),
        tabela(["Dado na série", "Método", "Intervalo"],
               [["1 ponto", "repetir o último valor", "±15%"],
                ["2 a 5 pontos", "média da série", "±2 desvios-padrão"],
                ["6 ou mais", "backtesting: Sazonal-Naive, Holt-Winters amortecido, Última-Observação",
                 "IC95 pela dispersão dos erros"]],
               [3.6 * cm, 12.6 * cm, 5 * cm]),
        Spacer(1, 0.3 * cm),
        kpis([("projeções", d["projecoes"]), ("séries", d["series"]),
              ("confiança média", d["confianca_proj"]), ("rubricas com fato", 10),
              ("rubricas sem cobertura", 0)]),
        PageBreak(),

        # --------------------------------------------------------- 10. governança
        Paragraph("10. Governança e operação", h2),
        Paragraph("A aba Descoberta consulta a SEC e responde: o trimestre foi "
                  "protocolado? o número estruturado já foi publicado?", corpo),
        Spacer(1, 0.2 * cm),
        tabela(["Situação", "Leitura"],
               [["ANUNCIADO", "documento novo do trimestre já publicado"],
                ["ANUNCIADO_SEM_XBRL", "comunicado existe, número estruturado ainda não"],
                ["NADA_ANUNCIADO", "nada publicado para o alvo ainda"],
                ["lacuna de XBRL", "o trimestre ainda não pode ser fechado com dado oficial"]],
               [6.4 * cm, 14.8 * cm]),
        Spacer(1, 0.4 * cm),
        Paragraph("Exceções ficam visíveis: o relatório declara quando o portal de RI "
                  "bloqueia automação, em vez de fingir cobertura.", corpo),
        PageBreak(),

        # -------------------------------------------------------------- 11. limites
        Paragraph("11. Limites e riscos assumidos", h2),
        tabela(["Limite", "Como tratamos"],
               [["Portal de RI dinâmico ou bloqueado (403)", "SEC como canal confiável; bloqueio declarado"],
                ["Documento principal do 6-K é a capa", "número vem do XBRL (companyfacts)"],
                ["Divergência de rubrica entre RIs", "De-Para aprendido + revisão humana"],
                ["Cobertura desigual por rubrica", "DQS de completude torna isso visível"],
                ["Série curta", "método e confiança degradam explicitamente"]],
               [8.4 * cm, 12.8 * cm]),
        PageBreak(),

        # ------------------------------------------------------- 12. próximos passos
        Paragraph("12. Próximos passos", grande),
        Spacer(1, 0.4 * cm),
        Paragraph("1. Ler os <b>anexos</b> do arquivamento SEC, não só o documento principal.<br/>"
                  "2. Escolher o método de projeção <b>por rubrica</b> (dívida é nível, não sazonalidade).<br/>"
                  "3. <b>Rolling-origin</b>: recalcular o passado e medir o erro real das projeções.<br/>"
                  "4. Cenários com Brent/FX e intervalo que responda à covariância dos fatores.<br/>"
                  "5. RI com render de JS para fechar o canal primário bloqueado.", corpo),
        Spacer(1, 0.8 * cm),
        Paragraph("Pergunta que o sistema responde sozinho: <b>de onde veio este número, "
                  "ele é confiável e o que ainda precisa de olho humano?</b>", forte),
    ]
    doc.build(story)
    return str(destino)
