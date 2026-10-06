"""Apresentação VISUAL em PPTX: uma tela real do produto por slide.

Diferente de `apresentacao_pptx.py`, que é um deck de conteúdo (números, método,
decisões), este aqui mostra **a tela rodando**. As imagens vêm de
`workers/screenshots.py` — Chrome headless contra o painel servindo de verdade,
porque uma figura desenhada à mão provaria o quê? Um mock-up.

Se a imagem faltar, o slide não some: ele avisa e segue com o texto. Melhor uma
apresentação com um slide sem figura do que uma apresentação que quebra na
primeira máquina sem Chrome.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DOCS_DIR
from models.database import DatabaseManager
from models.repositories import FatoRepository

# ---------------------------------------------------------------- paleta Petrobras
VERDE = "006B3F"          # verde Petrobras (corporativo)
VERDE_CLARO = "00953B"
AMARELO = "FFCD00"        # amarelo institucional
VERDE_ESCURO = "00432A"
CINZA = "5A6472"
CINZA_CLARO = "F2F5F3"
BRANCO = "FFFFFF"
PRETO = "1F2937"
LARANJA = "D97706"
VERMELHO = "DC2626"

EMPS = ["PETROBRAS", "SHELL", "BP", "CHEVRON", "EXXONMOBIL", "TOTALENERGIES", "EQUINOR"]
CURTA = {"PETROBRAS": "Petrobras", "SHELL": "Shell", "BP": "BP", "CHEVRON": "Chevron",
         "EXXONMOBIL": "ExxonMobil", "TOTALENERGIES": "TotalEnergies",
         "EQUINOR": "Equinor"}
NOME_PALETA = {"PETROBRAS": VERDE, "SHELL": AMARELO, "BP": "7B2CBF",
               "CHEVRON": "CC79A7", "EXXONMOBIL": "0072B2",
               "TOTALENERGIES": "B22222", "EQUINOR": "009E73"}

LARGURA, ALTURA = "13.333in", "7.5in"


# ------------------------------------------------------------------ números reais
def _numeros() -> dict[str, Any]:
    db = DatabaseManager()
    with db.connect() as c:
        u = lambda s: c.execute(s).fetchone()[0]  # noqa: E731
        n = {
            "empresas": u("SELECT COUNT(DISTINCT nome_empresa) FROM tb_fato_financeiro"),
            "periodos": u("SELECT COUNT(DISTINCT periodo) FROM tb_fato_financeiro"),
            "fontes": u("SELECT COUNT(*) FROM tb_fonte_dados"),
            "fontes_local": u("SELECT COUNT(*) FROM tb_fonte_dados"
                              " WHERE caminho_local <> ''"),
            "fatos": u("SELECT COUNT(*) FROM tb_fato_financeiro"),
            "operacionais": u("SELECT COUNT(*) FROM tb_fato_operacional"),
            "processadas": u("SELECT COUNT(*) FROM tb_fonte_dados"
                             " WHERE status_processamento='PROCESSADO'"),
            "sem_dados": u("SELECT COUNT(*) FROM tb_fonte_dados"
                           " WHERE status_processamento='SEM_DADOS'"),
            "nao_processadas": u("SELECT COUNT(*) FROM tb_fonte_dados"
                                 " WHERE status_processamento='NAO_PROCESSADO'"),
            "erros": u("SELECT COUNT(*) FROM tb_fonte_dados"
                       " WHERE status_processamento='ERRO'"),
            "alertas": u("SELECT COUNT(*) FROM tb_quality_alerts"),
            "fila": u("SELECT COUNT(*) FROM tb_review_queue"),
            "fila_aberta": u("SELECT COUNT(*) FROM tb_review_queue WHERE status='ABERTO'"),
            "projecoes": u("SELECT COUNT(*) FROM tb_projecao"),
            "series": u("SELECT COUNT(DISTINCT nome_empresa || rubrica_padronizada)"
                        " FROM tb_projecao"),
            "confianca_proj": round(u("SELECT AVG(confianca) FROM tb_projecao") or 0, 2),
            "scorecards": u("SELECT COUNT(*) FROM tb_qualidade_score"),
            "dqs": round(u("SELECT AVG(dqs) FROM tb_qualidade_score") or 0, 1),
            "execucoes": u("SELECT COUNT(*) FROM tb_etl_execucao"),
            "tabelas": u("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                         " AND name LIKE 'tb\\_%' ESCAPE '\\'"),
            "decisoes": u("SELECT COUNT(*) FROM tb_auditoria_decisao"),
            "metodos": {r["metodo"]: r["n"] for r in c.execute(
                "SELECT metodo, COUNT(*) n FROM tb_projecao GROUP BY 1 ORDER BY 2 DESC")},
            "dims": {r["dimensao"]: r["m"] for r in c.execute(
                """SELECT d.dimensao, AVG(d.valor) m FROM (
                     SELECT 'completude' dimensao, completude valor FROM tb_qualidade_score
                     UNION ALL SELECT 'tempestividade', tempestividade FROM tb_qualidade_score
                     UNION ALL SELECT 'plausibilidade', plausibilidade FROM tb_qualidade_score
                     UNION ALL SELECT 'consistencia', consistencia FROM tb_qualidade_score
                     UNION ALL SELECT 'rastreabilidade', rastreabilidade FROM tb_qualidade_score
                   ) d GROUP BY d.dimensao""")},
            "classe": {r["classificacao"]: r["n"] for r in c.execute(
                "SELECT classificacao, COUNT(*) n FROM tb_qualidade_score GROUP BY 1")},
            "hist_periodos": u("SELECT COUNT(DISTINCT periodo) FROM tb_qualidade_historico"),
            "pdf_docs": u("SELECT COUNT(*) FROM tb_fonte_dados WHERE n_paginas IS NOT NULL"),
            "pdf_lidas": u("SELECT COALESCE(SUM(n_paginas_lidas),0) FROM tb_fonte_dados"),
            "pdf_total": u("SELECT COALESCE(SUM(n_paginas),0) FROM tb_fonte_dados"),
            "pdf_tabelas": u("SELECT COALESCE(SUM(n_tabelas),0) FROM tb_fonte_dados"),
            "pdf_ms": u("SELECT COALESCE(SUM(duracao_ms),0) FROM tb_fonte_dados"
                        " WHERE n_paginas IS NOT NULL"),
        }
    n["pdf_pps"] = round(1000.0 * n["pdf_lidas"] / n["pdf_ms"], 1) if n["pdf_ms"] else 0.0
    n["pdf_cobertura"] = (round(100.0 * n["pdf_lidas"] / n["pdf_total"], 1)
                          if n["pdf_total"] else 0.0)
    # série histórica do DQS
    with db.connect() as c:
        linhas = [dict(r) for r in c.execute(
            "SELECT periodo, AVG(dqs) dqs, COUNT(*) n FROM tb_qualidade_historico"
            " GROUP BY periodo ORDER BY periodo").fetchall()]
        por_empresa = [dict(r) for r in c.execute(
            """SELECT nome_empresa,
                      (SELECT dqs FROM tb_qualidade_historico h WHERE h.nome_empresa = e.nome_empresa
                        ORDER BY h.periodo, h.gerado_em LIMIT 1) inicio,
                      (SELECT dqs FROM tb_qualidade_historico h WHERE h.nome_empresa = e.nome_empresa
                        ORDER BY h.periodo DESC, h.gerado_em DESC LIMIT 1) fim
               FROM (SELECT DISTINCT nome_empresa FROM tb_qualidade_historico) e
               ORDER BY nome_empresa""").fetchall()]
    n["serie_dqs"] = linhas
    n["dqs_empresas"] = por_empresa
    n["dqs_ini"] = round(linhas[0]["dqs"], 1) if linhas else 0.0
    n["dqs_fim"] = round(linhas[-1]["dqs"], 1) if linhas else 0.0
    n["dqs_var"] = round(n["dqs_fim"] - n["dqs_ini"], 1)
    # matriz do último trimestre com fato
    with db.connect() as c:
        ultimo = c.execute("SELECT MAX(periodo) p FROM tb_fato_financeiro").fetchone()["p"]
    n["periodo_matriz"] = ultimo
    matriz: dict[str, dict[str, float]] = {}
    for r in FatoRepository(db).matriz(ultimo):
        matriz.setdefault(r["rubrica_padronizada"], {})[r["nome_empresa"]] = r["valor"]
    n["matriz"] = matriz
    return n


# ------------------------------------------------------------------ helpers de layout
def _slide(prs, fundo: str = BRANCO):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    fundo_obj = s.background.fill
    fundo_obj.solid()
    fundo_obj.fore_color.rgb = _rgb(fundo)
    return s


def _rgb(hexa: str):
    from pptx.dml.color import RGBColor
    return RGBColor.from_string(hexa)


def _caixa(slide, x, y, w, h, texto="", tamanho=14, cor=PRETO, negrito=False,
           align=None, fill=None, line=None, espaco=4, ancora=None):
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    forma = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = forma.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.06)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    if ancora:
        tf.vertical_anchor = {MSO_ANCHOR.TOP: MSO_ANCHOR.TOP,
                              "meio": MSO_ANCHOR.MIDDLE,
                              MSO_ANCHOR.BOTTOM: MSO_ANCHOR.BOTTOM}[ancora]
    linhas = texto.split("\n") if isinstance(texto, str) else list(texto)
    for i, linha in enumerate(linhas):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(espaco)
        if align:
            p.alignment = {"meio": PP_ALIGN.CENTER, "esq": PP_ALIGN.LEFT,
                           "dir": PP_ALIGN.RIGHT}[align]
        run = p.add_run()
        run.text = linha
        run.font.size = Pt(tamanho)
        run.font.bold = negrito
        run.font.color.rgb = _rgb(cor)
        run.font.name = "Segoe UI"
    if fill or line:
        from pptx.enum.shapes import MSO_SHAPE
        rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y),
                                      Inches(w), Inches(h))
        rect.fill.solid()
        rect.fill.fore_color.rgb = _rgb(fill or BRANCO)
        if line:
            rect.line.color.rgb = _rgb(line)
            rect.line.width = Pt(1)
        else:
            rect.line.fill.background()
        rect.shadow.inherit = False
        slide.shapes._spTree.remove(rect._element)
        slide.shapes._spTree.insert(2, rect._element)
    return forma


def _cabecalho(slide, titulo: str, subtitulo: str = "", numero: int = 0):
    from pptx.util import Inches, Pt
    barra = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(1.02))
    barra.fill.solid()
    barra.fill.fore_color.rgb = _rgb(VERDE)
    barra.line.fill.background()
    barra.shadow.inherit = False
    faixa = slide.shapes.add_shape(1, Inches(0), Inches(1.02), Inches(13.333), Inches(0.09))
    faixa.fill.solid()
    faixa.fill.fore_color.rgb = _rgb(AMARELO)
    faixa.line.fill.background()
    faixa.shadow.inherit = False
    _caixa(slide, 0.45, 0.14, 11.5, 0.5, titulo, 24, BRANCO, True)
    if subtitulo:
        _caixa(slide, 0.47, 0.63, 11.5, 0.32, subtitulo, 11.5, "D7E9DF")
    if numero:
        _caixa(slide, 12.35, 0.3, 0.7, 0.4, f"{numero:02d}", 18, AMARELO, True, "meio")
    _ = Pt


def _rodape(slide, texto: str = "PetroAnalytics PoC · benchmark Petrobras vs pares"):
    _caixa(slide, 0.45, 7.06, 9.0, 0.3, texto, 8.5, CINZA)


def _kpis(slide, itens: list[tuple[Any, str, str]], y=1.35, x0=0.45, larg=12.45, h=1.0):
    """Faixa de indicadores: (VALOR, rótulo, cor do valor).

    Tupla na ordem **valor primeiro**, conferida aqui e não por olho: numa faixa só,
    (rótulo, valor) invertia o par e o slide mostrava "empresas comparadas / 7" —
    o número virava legenda e a legenda virava número.

    O rótulo tem caixa própria, mais baixa que o valor: com a mesma altura, um
    rótulo de duas linhas cresce para dentro da caixa de cima e some atrás do número.
    """
    from pptx.util import Inches as In, Pt
    from pptx.enum.text import PP_ALIGN
    n = len(itens)
    w = larg / n
    for i, (val, rot, cor) in enumerate(itens):
        if isinstance(val, str) and val.isdigit() and len(val) > 8:
            raise ValueError(f"_kpis: parece rótulo no lugar do valor: {val!r}")
        x = x0 + i * w
        _caixa(slide, x + 0.03, y, w - 0.06, h, "", fill=CINZA_CLARO, line="D8E2DC")
        _caixa(slide, x + 0.03, y + 0.06, w - 0.06, 0.45, str(val), 21, cor, True, "meio")
        rotulo = slide.shapes.add_textbox(In(x + 0.03), In(y + 0.54),
                                          In(w - 0.06), In(h - 0.58))
        tf = rotulo.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = In(0.02)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = rot
        run.font.size = Pt(9.5)
        run.font.color.rgb = _rgb(CINZA)
        run.font.name = "Segoe UI"


def _tabela(slide, cabecalho: list[str], linhas: list[list], x, y, w, larg_col: list[float],
            h_linha=0.3, tamanho=10, cor_cab=VERDE, destaque: set[int] | None = None):
    from pptx.util import Inches, Pt
    n_l, n_c = len(linhas) + 1, len(cabecalho)
    alt = h_linha * (n_l)
    forma = slide.shapes.add_table(n_l, n_c, Inches(x), Inches(y), Inches(w), Inches(alt))
    tbl = forma.table
    tot = sum(larg_col)
    for i, frac in enumerate(larg_col):
        tbl.columns[i].width = Inches(w * frac / tot)
    for j, tit in enumerate(cabecalho):
        cel = tbl.cell(0, j)
        cel.text = str(tit)
        cel.fill.solid()
        cel.fill.fore_color.rgb = _rgb(cor_cab)
        p = cel.text_frame.paragraphs[0]
        p.font.size = Pt(tamanho)
        p.font.bold = True
        p.font.color.rgb = _rgb(BRANCO)
        p.font.name = "Segoe UI"
        p.alignment = 2 if j else 1
        cel.margin_left = cel.margin_right = Inches(0.04)
    for i, linha in enumerate(linhas, start=1):
        for j, val in enumerate(linha):
            cel = tbl.cell(i, j)
            cel.text = "" if val is None else str(val)
            cel.fill.solid()
            cel.fill.fore_color.rgb = _rgb(BRANCO if i % 2 else CINZA_CLARO)
            p = cel.text_frame.paragraphs[0]
            p.font.size = Pt(tamanho)
            p.font.name = "Segoe UI"
            if destaque and i - 1 in destaque:
                p.font.bold = True
                p.font.color.rgb = _rgb(VERDE)
            p.alignment = 2 if j else 1
            cel.margin_left = cel.margin_right = Inches(0.04)
    return forma


def _bullets(slide, itens: list[str], x, y, w, h, tamanho=13, cor=PRETO, espaco=7):
    from pptx.util import Inches, Pt
    forma = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = forma.text_frame
    tf.word_wrap = True
    for i, item in enumerate(itens):
        if isinstance(item, tuple):
            texto, negrito = item
        else:
            texto, negrito = item, False
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(espaco)
        run = p.add_run()
        run.text = f"▪  {texto}"
        run.font.size = Pt(tamanho)
        run.font.color.rgb = _rgb(cor)
        run.font.name = "Segoe UI"
        run.font.bold = negrito
    return forma


def _figura(slide, caminho: Path, x: float, y: float, max_w: float, max_h: float,
            legenda: str = "", rodape: str = "") -> bool:
    """Coloca a tela do produto, cabendo inteira (nunca esticando/distorcendo).

    Mantém a proporção do PNG e centraliza na área pedida. Sem o arquivo, devolve
    False: o slide continua com o texto, em vez de virar um buraco.
    """
    from PIL import Image
    from pptx.util import Inches as In
    if not caminho.exists():
        return False
    largura_px, altura_px = Image.open(caminho).size
    escala = min(max_w / largura_px, max_h / altura_px)
    larg, alt = largura_px * escala, altura_px * escala
    px = x + (max_w - larg) / 2
    py = y + (max_h - alt) / 2
    # moldura fina: separa a figura do fundo branco sem pesar
    slide.shapes.add_picture(str(caminho), In(px), In(py), In(larg), In(alt))
    if legenda:
        _caixa(slide, px, py + alt + 0.06, larg, 0.3, legenda, 9.5, CINZA, align="meio")
    if rodape:
        _caixa(slide, px, py + alt + (0.34 if legenda else 0.06), larg, 0.3,
               rodape, 10.5, VERDE_ESCURO, True, "meio")
    return True


# ------------------------------------------------------------------ os slides
def construir(destino: Path | None = None, n: dict[str, Any] | None = None) -> str:
    from pptx import Presentation
    from pptx.util import Inches, Pt

    n = n or _numeros()
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    num = 0

    def prox(titulo, subtitulo=""):
        nonlocal num
        num += 1
        s = _slide(prs)
        _cabecalho(s, titulo, subtitulo, num)
        _rodape(s)
        return s

    # 1 — capa
    s = _slide(prs, VERDE_ESCURO)
    faixa = s.shapes.add_shape(1, Inches(0), Inches(5.6), Inches(13.333), Inches(0.22))
    faixa.fill.solid()
    faixa.fill.fore_color.rgb = _rgb(AMARELO)
    faixa.line.fill.background()
    faixa.shadow.inherit = False
    _caixa(s, 0.9, 1.5, 11.5, 1.1, "PetroAnalytics", 54, BRANCO, True)
    _caixa(s, 0.95, 2.6, 11.5, 0.6,
           "Benchmark Petrobras vs 6 pares · intelligence financière et opérationnelle",
           19, AMARELO)
    _caixa(s, 0.95, 3.35, 11.5, 1.4,
           f"{n['empresas']} empresas  ·  {n['periodos']} trimestres (2023Q1–2026Q2)  ·  "
           f"{n['fontes']} fontes catalogadas  ·  {n['fatos']} fatos com fonte, data,\n"
           f"unidade e confiança  ·  DQS {n['dqs']}  ·  {n['projecoes']} projeções",
           14, "E8F5EE")
    _caixa(s, 0.95, 6.0, 11.5, 0.5,
           "MVC-W · SQLite · Python · painel web + GUI desktop · relatório de auditoria em PDF",
           12.5, "BFD9CC")

    # 2 — agenda
    s = prox("Roteiro", "12 blocos — problema, cadeia, arquitetura, evidência e limites")
    _bullets(s, [
        ("O problema e a utilidade", True), "Quem usa e como usa", "A cadeia de ponta a ponta",
        "Arquitetura e tecnologia (e o que foi descartado por medição)",
        "Resultados medidos · matriz do último trimestre",
        "Qualidade: DQS, evolução no tempo, fila priorizada, alerta cross-sectional",
        "Projeção estatística e auditoria de governança",
        "Descoberta do que foi anunciado · relatório de auditoria",
        "Limites assumidos · próximos passos",
    ], 0.8, 1.5, 11.8, 5.2, 14, espaco=10)

    # 3 — problema
    s = prox("1. O problema", "Sete empresas, sete formatos — e nenhum número comparável")
    _bullets(s, [
        ("O mesmo fato é publicado de formas incompatíveis:", True),
        "PDF com layout a perder · planilha com três separadores · release em inglês",
        "Valor em dólar ou em real · trimestre rotulado de formas diferentes entre RI e SEC",
        ("Comparar Petrobras com seis pares exige planilha na mão — e gera erro de versão.",
         True),
        ("O problema de governança:", True),
        "Um número sem procedência não pode ir para decisão. Aqui todo fato carrega "
        "fonte, data, unidade e confiança.",
        ("E o que não tem confiança suficiente vai para revisão humana — nunca para o "
         "gráfico como se fosse verdade.", True),
    ], 0.8, 1.5, 11.8, 5.0, 14, espaco=9)
    _kpis(s, [(str(n["empresas"]), "empresas comparadas", VERDE),
              ("7", "formatos distintos", VERDE),
              (str(n["erros"]), "erros de carga", VERDE)], y=6.0)

    # 4 — utilidade
    s = prox("2. A utilidade", "O que o sistema entrega que uma planilha não entrega")
    _kpis(s, [(str(n["fontes"]), "fontes catalogadas", VERDE),
              (str(n["fatos"]), "fatos financeiros", VERDE),
              (str(n["operacionais"]), "fatos operacionais", VERDE),
              (f"{n['dqs']}", "DQS médio", VERDE),
              (str(n["projecoes"]), "projeções", VERDE)], y=1.4)
    _bullets(s, [
        ("Comparabilidade — mesmo indicador, mesma unidade, mesma moeda em toda a série."),
        ("Descoberta — saber o que foi anunciado e ainda não está no acervo."),
        ("Confiança — DQS por empresa×trimestre e fila priorizada do que exige análise."),
        ("Projeção — 3 trimestres à frente, método escolhido por backtesting, com IC95."),
        ("Governança — relatório de auditoria em PDF com as decisões do período."),
    ], 0.8, 2.65, 11.8, 2.6, 14, espaco=8)
    _caixa(s, 0.8, 5.5, 11.8, 1.1,
           "Perguntas que o sistema responde sozinho:\n"
           "de onde veio este número · ele é confiável · o que ainda precisa de olho humano · "
           "o próximo trimestre já saiu?",
           13, VERDE_ESCURO, True)

    # 5 — quem usa
    s = prox("3. Quem usa e como usa", "Fluxo trimestral de verdade: soltar o arquivo e rodar um comando")
    _tabela(s, ["Passo", "Comando", "Quem faz", "O que entrega"],
            [["1. Atualizar o acervo", "app_main.py etl --novos", "Analista",
              "varre o Container e processa só o que é novo"],
             ["2. Conferir novidade", "app_main.py descoberta", "Analista",
              "o 3T26 já foi protocolado? o número estruturado já existe?"],
             ["3. Ler", "app_main.py web --serve · gui", "Gestor",
              "painel de 11 abas (web) ou 8 (desktop)"],
             ["4. Distribuir", "app_main.py email --para ...", "Analista/Gestor",
              "e-mail com HTML + PNG + CSV anexados"],
             ["5. Auditar", "app_main.py auditoria relatorio", "Auditor",
              "PDF com as decisões do período"]],
            0.5, 1.45, 12.35, [1.5, 2.4, 1.4, 4.6], 0.52, 11)
    _caixa(s, 0.8, 4.6, 11.8, 0.7,
           "O incremental é idempotente: rodar de novo processa 0 arquivos. "
           "Carga inicial 108 arquivos em 353 s → 1 arquivo novo em 4,3 s.",
           13, VERDE_ESCURO, True)

    # 6 — cadeia
    s = prox("4. Como funciona — a cadeia", "Cada etapa tem uma garantia; nenhuma delas é opcional")
    etapas = ["Inventário", "Varredura\nSHA-256", "Classificação\ndo documento",
              "Parser\nPyMuPDF/planilha", "De-Para\nPT/EN", "Plausibilidade",
              "Carga com\nfonte+confiança", "Auditoria", "DQS", "Projeção", "Painel"]
    larg = 12.4 / len(etapas)
    for i, etapa in enumerate(etapas):
        x = 0.45 + i * larg
        cor = VERDE if i in (0, 6, 10) else "3F7F5F"
        _caixa(s, x + 0.02, 1.6, larg - 0.06, 0.95, etapa, 10, BRANCO, True, "meio",
               fill=cor, line=cor, espaco=0, ancora="meio")
        if i < len(etapas) - 1:
            _caixa(s, x + larg - 0.045, 1.9, 0.06, 0.3, "›", 16, AMARELO, True, "meio")
    _bullets(s, [
        ("Idempotência", True), "reexecutar não duplica nem regrada fato (SHA-256 + "
        "prioridade de confiança);",
        ("Rastreabilidade", True), "todo fato tem id_fonte — sem fonte ele vai para a fila "
        "de revisão, não para a matriz;",
        ("Projeção ≠ fato", True), "projeção vive em tb_projecao, fora da matriz, "
        "sempre rotulada.",
    ], 0.8, 3.0, 11.8, 2.2, 14, espaco=9)
    _kpis(s, [(str(n["execucoes"]), "execuções do ETL registradas", VERDE),
              (str(n["erros"]), "erros de carga", VERDE),
              (str(n["tabelas"]), "tabelas no banco", VERDE)], y=5.6)

    # 7 — arquitetura
    s = prox("5. Arquitetura", "MVC-W com responsabilidade única e injeção por construtor")
    _tabela(s, ["Camada", "Pasta", "Papel", "Exemplos"],
            [["Model", "models/", "12 tabelas SQLite, De-Para, glossário, repositórios",
              "database · repositories · depara · glossario"],
             ["Worker", "workers/", "todo o processamento; nenhuma escrita de tela",
              "scanner · parse_pdf · parse_tab · etl · quality_score · forecast · sec_edgar"],
             ["Controller", "controllers/", "casos de uso finos, sem regra de negócio",
              "Pipeline · Analytics · Source · Forecast · Mail"],
             ["View", "views/", "web (Plotly + JS), desktop (PySide6), servidor REST",
              "web_app · gui_app · web_server"]],
            0.5, 1.4, 12.35, [1.3, 1.3, 4.2, 5.5], 0.72, 10.5)
    _bullets(s, [
        ("Padrões:", True), "MVC-W · repositório · injeção por construtor · SRP · type hints",
        ("Migrações idempotentes:", True), "ALTER TABLE ADD COLUMN em bancos antigos, "
        "sem rebuild — por isso a base de 3 meses atrás ainda abre.",
    ], 0.8, 4.6, 11.8, 1.6, 13.5, espaco=9)

    # 8 — tecnologia
    s = prox("6. Tecnologia — e por quê", "Escolha medida, não preferência")
    _tabela(s, ["Tecnologia", "Onde", "Por quê"],
            [["Python 3.12+", "back-end", "ecossistema de dados pronto para PDF e rede"],
             ["SQLite", "persistência", "arquivo único, transacional, auditável — adequado a PoC"],
             ["PyMuPDF", "extração de PDF", "o mais rápido no acervo (2,2 s vs 6–23 s) e acha tabelas"],
             ["pdfplumber", "fallback de tabela", "quando o MuPDF não acha tabela válida"],
             ["Plotly", "Web", "interativo e exporta PNG sem navegador extra"],
             ["PySide6 + pyqtgraph", "GUI", "desktop nativo com gráficos de alta performance"],
             ["reportlab + Kaleido", "PDF e PNG", "entregáveis sem depender de navegador"],
             ["python-pptx", "esta apresentação", "deck gerado do banco — não pode divergir do painel"],
             ["pytest", "testes", "regressão real: 20 bugs encontrados por teste"]],
            0.5, 1.4, 12.35, [2.6, 2.2, 7.5], 0.42, 11)
    _caixa(s, 0.8, 5.5, 11.8, 1.2,
           "Destaque honesto: as bibliotecas Rust de PDF (PDFOxide, pdf-inspector) foram "
           "benchmarkadas e NÃO adotadas — são redundantes com o MuPDF (mesmas extrações) "
           "e 2,8× mais lentas.",
           13, VERDE_ESCURO, True)

    # 9 — benchmark de PDF
    s = prox("7. Benchmark de leitura de PDF", "Medido no acervo real (11 PDFs, DFs Petrobras + BP + Total)")
    _tabela(s, ["Biblioteca", "Texto", "MB/s", "Tabelas", "Veredito"],
            [["PyMuPDF 1.28", "2,2 s", "5,3", "31", "PRINCIPAL"],
             ["pdf-inspector (Rust)", "2,5 s", "4,6", "—", "não adotado"],
             ["PDFOxide 0.3 (Rust)", "6,2 s", "1,9", "0 nos DFs", "só fallback"],
             ["pypdf 6.19", "16,3 s", "0,7", "—", "7× mais lento"],
             ["pdfminer.six", "22,8 s", "0,5", "—", "10× mais lento"]],
            0.5, 1.4, 12.35, [3.0, 1.6, 1.4, 2.0, 2.4], 0.42, 11.5, destaque={0})
    _caixa(s, 0.8, 4.1, 11.8, 1.3,
           "Conclusão medida: as libs Rust são redundantes, não melhores — as extrações "
           "caem nas mesmas chaves (rubrica, período). Trocar a biblioteca principal não "
           "ganharia um único fato e custaria velocidade e detecção de tabelas.",
           13, VERDE_ESCURO, True)
    _kpis(s, [(str(n["pdf_docs"]), "PDFs medidos", VERDE),
              (f"{n['pdf_lidas']:,}".replace(",", "."), "páginas lidas", VERDE),
              (f"{n['pdf_pps']}", "páginas/seg", VERDE),
              (f"{n['pdf_tabelas']:,}".replace(",", "."), "tabelas detectadas", VERDE),
              (f"{n['pdf_cobertura']}%", "cobertura do acervo", VERDE)], y=5.7)

    # 10 — resultados / matriz
    s = prox("8. Resultados medidos", f"Matriz {n['periodo_matriz']} (USD bi) — 7 empresas, mesma unidade")
    rubricas = [("RECEITA_LIQUIDA", "Receita líquida"), ("EBITDA_AJUSTADO", "EBITDA ajustado"),
                ("LUCRO_LIQUIDO", "Lucro líquido"), ("FCO", "Fluxo de caixa oper."),
                ("CAPEX", "Investimentos (CAPEX)"), ("DIVIDA_LIQUIDA", "Dívida líquida")]
    linhas = []
    for cod, rot in rubricas:
        vals = n["matriz"].get(cod, {})
        # 2 casas no CAPEX: a 1 casa o valor do defeito de extração (0,01) viraria
        # "0,0" — exatamente o número que o slide seguinte denuncia.
        casas = 2 if cod == "CAPEX" else 1
        linhas.append([rot] + [f"{vals[e]:,.{casas}f}".replace(",", "X").replace(".", ",")
                               .replace("X", ".") if e in vals else "—" for e in EMPS])
    _tabela(s, ["Indicador"] + [CURTA[e] for e in EMPS], linhas,
            0.5, 1.35, 12.35, [2.6] + [1.4] * 7, 0.36, 10.5, destaque={0})
    _caixa(s, 0.8, 4.15, 11.8, 0.55,
           "Unidade: USD bilhões, com a moeda de origem detectada por regex no nome do "
           "arquivo e conversão BRL→USD pela PTAX de fechamento do trimestre.",
           11.5, CINZA)
    _bullets(s, [
        ("O CAPEX da Petrobras aparece como 0,01 — e está errado.", True),
        "A comparação com os pares denunciou o defeito de extração: a aba "
        "\"Investimentos\" da planilha tem linhas de projeto, não o consolidado. "
        "O alerta cross-sectional isolou como P1 sem ninguém comparar tabelas à mão.",
    ], 0.8, 4.8, 11.8, 1.3, 13, espaco=6)

    # 11 — números do acervo
    s = prox("9. Estado do acervo", "O que existe hoje, com o status de cada documento")
    _kpis(s, [(str(n["fontes"]), "fontes catalogadas", VERDE),
              (str(n["fontes_local"]), "com arquivo local", VERDE),
              (str(n["processadas"]), "processadas", VERDE),
              (str(n["sem_dados"]), "sem dado", LARANJA),
              (str(n["nao_processadas"]), "não processadas", LARANJA),
              (str(n["erros"]), "erros", VERDE)], y=1.4)
    _bullets(s, [
        ("Documento sem carga tem motivo gravado", True),
        "\"não achou número no documento\" ≠ \"perdeu para um fato já gravado com confiança "
        "maior\" — o painel diz qual dos dois foi.",
        ("PDF narrativo não entra no ETL numérico", True),
        "transcrição, slides, remarks e webcast são catalogados mas pulados — no acervo, "
        "51 dos 52 pulados são narrativos.",
        ("Idempotência real", True),
        "SHA-256 por arquivo; um fato existente com confiança maior nunca é rebaixado por "
        "uma extração pior.",
    ], 0.8, 2.75, 11.8, 3.2, 13.5, espaco=8)

    # 12 — qualidade: DQS
    s = prox("10. Qualidade — o DQS", "Cada empresa × trimestre recebe uma nota 0–100 auditável")
    dims = [("Completude", "completude", "30%"), ("Plausibilidade", "plausibilidade", "25%"),
            ("Consistência", "consistencia", "15%"), ("Rastreabilidade", "rastreabilidade", "15%"),
            ("Tempestividade", "tempestividade", "15%")]
    linhas = [[rot, peso, f"{n['dims'].get(cod, 0):.1f}"] for rot, cod, peso in dims]
    linhas.append(["DQS médio ponderado", "—", f"{n['dqs']}"])
    _tabela(s, ["Dimensão", "Peso", "Média da base"], linhas,
            0.5, 1.4, 6.1, [3.0, 1.2, 1.8], 0.38, 11.5, destaque={5})
    _bullets(s, [
        ("Classificação", True), "CONFIÁVEL ≥ 80 · REVISAR 60–79 · NÃO CONFIÁVEL < 60",
        f"Hoje: {n['classe'].get('CONFIÁVEL', 0)} CONFIÁVEL · "
        f"{n['classe'].get('REVISAR', 0)} REVISAR · "
        f"{n['classe'].get('NÃO CONFIÁVEL', 0)} NÃO CONFIÁVEL",
        ("Rastreabilidade 100,0 é real", True),
        "todos os fatos financeiros têm id_fonte válido — e integridade referencial "
        "confere 0 órfãos.",
        ("DQS baixo é mapa de trabalho", True),
        "tempestividade 64,2 diz \"faltou o 2T26 de alguém\" (é data de publicação); "
        "completude 40,6 diz \"falta rubrica\" — e aí é ação.",
    ], 6.9, 1.45, 5.9, 4.6, 12.5, espaco=7)
    _caixa(s, 0.8, 5.3, 6.0, 1.2,
           "Regra de ouro:\nconfiança baixa vai para revisão humana, nunca para o painel "
           "como se fosse verdade.", 13, VERDE_ESCURO, True)

    # 13 — evolução do DQS
    s = prox("11. Evolução da qualidade no tempo", "O scorecard guardava só o último estado — a história se perdia")
    serie = n["serie_dqs"]
    # Gráfico de largura CHEIA no topo: com 14 períodos o passo cai para ~0,9in e
    # nenhum lado cabe 14 barras legíveis. A tabela vem abaixo, ao lado do texto.
    if serie:
        minv = min(x["dqs"] for x in serie)
        maxv = max(x["dqs"] for x in serie)
        faixa = (maxv - minv) or 1
        x0, y0, largura, altura_g = 0.85, 3.35, 11.7, 1.65
        passo = largura / max(1, len(serie) - 1)
        from pptx.util import Inches as In
        for i, ponto in enumerate(serie):
            x = x0 + i * passo
            h = 0.22 + (ponto["dqs"] - minv) / faixa * (altura_g - 0.45)
            ultimo = i == len(serie) - 1
            barra = s.shapes.add_shape(1, In(x - 0.22), In(y0 - h), In(0.44), In(h))
            barra.fill.solid()
            barra.fill.fore_color.rgb = _rgb(VERDE if ultimo else "6FA98C")
            barra.line.fill.background()
            barra.shadow.inherit = False
            _caixa(s, x - 0.45, y0 + 0.04, 0.9, 0.26, ponto["periodo"], 8.5,
                   VERDE if ultimo else CINZA, ultimo, "meio")
            _caixa(s, x - 0.45, y0 - h - 0.3, 0.9, 0.28, f"{ponto['dqs']:.0f}", 10.5,
                   VERDE if ultimo else CINZA, ultimo, "meio")
        # Uma LINHA só: em duas linhas o título crescia para baixo e cobria o
        # parágrafo explicativo que vem logo abaixo.
        _caixa(s, 0.45, 1.4, 12.4, 0.45,
               f"DQS médio da base: {n['dqs_ini']} → {n['dqs_fim']} "
               f"({n['dqs_var']:+}) em {len(serie)} períodos", 21, VERDE, True)
        _caixa(s, 0.45, 1.95, 12.4, 0.75,
               "A virada em 2025Q4 coincide com a carga SEC completa daquele trimestre. "
               "Antes disso os trimestres eram SEC parciais, com completude baixa — a "
               "qualidade subiu por mais dados, não por método mais frouxo.",
               13, CINZA)
    linhas = [[CURTA.get(r["nome_empresa"], r["nome_empresa"]),
               f"{r['inicio']:.1f}" if r["inicio"] is not None else "—",
               f"{r['fim']:.1f}" if r["fim"] is not None else "—",
               f"{r['fim'] - r['inicio']:+.1f}" if r["inicio"] is not None and
               r["fim"] is not None else "—"]
              for r in n["dqs_empresas"]]
    _tabela(s, ["Empresa", "DQS inicial", "DQS atual", "Variação"], linhas,
            7.55, 4.05, 5.3, [2.4, 1.2, 1.2, 1.2], 0.29, 10.5)
    _bullets(s, [
        ("Um ponto por empresa × período, gravado só quando o DQS muda de verdade:", True),
        "a série mostra evolução da qualidade, não log de execução.",
        ("Maior evolução: Petrobras", True),
        "75,4 → 99,8. Ainda em REVISAR: Equinor, 66,5 → 76,3.",
        ("Quem melhorou mais não é quem tem mais dado —", True),
        "é quem tem dado completo nos dois extremos da série.",
    ], 0.45, 4.05, 6.8, 2.5, 12.5, espaco=7)

    # 14 — fila e regras
    s = prox("12. Fila de análise priorizada", "O que exige olho humano, em ordem de urgência")
    _kpis(s, [(str(n["fila"]), "itens na fila", VERDE),
              (str(n["fila_aberta"]), "abertos", LARANJA),
              (str(n["alertas"]), "alertas ativos", VERDE),
              ("9", "regras de desvio", VERDE),
              (str(n["decisoes"]), "decisões registradas", VERDE)], y=1.4)
    _bullets(s, [
        ("P1 urgente · P2 revisar · P3 completar — sempre com o código do motivo.", True),
        ("Escalonamento automático por repetição:", True),
        "um código de alerta que se repete mais de 3 vezes sobe um nível (P3→P2→P1). "
        "O DRIFT_ZSCORE da BP apareceu 39 vezes e foi para o topo em vez de se diluir.",
        ("As 9 regras, com limiar calibrável em tb_regra_alerta (sem tocar em código):", True),
        "DRIFT_ZSCORE · QUEBRA_ESTRUTURAL · CONTAGEM_PERIODO · REVISAO_ENTRE_EXECUCOES · "
        "ATRASO_TRIMESTRE · BAIXA_CONFIANCA · SEM_FONTE · RUBRICA_AUSENTE · "
        "OUTLIER_CROSS_SECTIONAL",
        ("Contrato de dados:", True),
        "tipos, obrigatoriedade, domínio e convenção de sinal verificados ao fim de cada "
        "execução — aponta a linha exata. 393 fatos verificados, 0 violações.",
    ], 0.8, 2.7, 11.8, 3.9, 13, espaco=8)

    # 15 — cross-sectional
    s = prox("13. Alerta cross-sectional", "As outras 8 regras comparam com a própria história; esta compara com os pares")
    _bullets(s, [
        ("Pergunta:", True), "\"esta empresa está fora da curva dos pares neste trimestre?\"",
        ("Cálculo", True), "grupo = (trimestre, rubrica); z = (valor − média) ÷ desvio do grupo.",
        ("Limiar |z| ≥ 1,8, gravado em tb_regra_alerta (calibrável sem código).", True),
        ("Piso de 4 empresas por grupo", True),
        "sem ele, num grupo de 2 ou 3 qualquer diferença vira z alto.",
        ("Só entra o que é comparável entre oil & gas", True),
        "receita, EBITDA, lucro, FCO, CAPEX e dívida. Efetivo fica de fora: efetivo "
        "menor é o esperado numa empresa com menos employees — não é anomalia.",
    ], 0.8, 1.45, 6.3, 4.6, 13, espaco=8)
    _tabela(s, ["Empresa", "Trimestre", "Métrica", "Posição no grupo"],
            [["CHEVRON", "2026Q2", "FCO 45,32", "+2,0σ (7 empresas, média 20,35)"],
             ["CHEVRON", "2026Q1", "FCO 29,85", "+2,4σ (7 empresas, média 9,21)"],
             ["CHEVRON", "2025Q4", "FCO 33,94", "+2,3σ (7 empresas, média 12,35)"],
             ["BP", "2025Q4", "Lucro −3,42", "−2,1σ (6 empresas, média 1,78)"],
             ["PETROBRAS", "2026Q2", "CAPEX 0,01", "−1,9σ (5 empresas, média 3,02)"],
             ["PETROBRAS", "2026Q1", "CAPEX 0,01", "−1,9σ (6 empresas, média 3,61)"]],
            7.3, 1.45, 5.5, [1.3, 1.2, 1.5, 2.6], 0.36, 10)
    _caixa(s, 0.8, 5.5, 12.0, 1.15,
           "O achado que importa: CAPEX da Petrobras a 0,01 USD bi contra pares em 3,09 a "
           "4,54. A série não caiu 98% — o valor NÃO foi extraído (a planilha tem linhas de "
           "projeto, não o consolidado). A comparação com os pares foi o que revelou.",
           12.5, VERDE_ESCURO, True)

    # 16 — projeção
    s = prox("14. Projeção estatística", "O método é escolhido por medição, nunca por suposição")
    _tabela(s, ["Dados na série", "Método", "Intervalo de 95%"],
            [["1 ponto", "repete o último valor", "±15%"],
             ["2 a 5 pontos", "média da série", "± 2 desvios-padrão"],
             ["6 ou mais", "backtesting entre Sazonal-Naive, Holt-Winters amortecido "
              "(φ=0,85) e Última-Observação", "pela dispersão dos erros"]],
            0.5, 1.4, 12.35, [2.0, 6.4, 3.9], 0.55, 11.5)
    met = n["metodos"]
    linhas = [[m, str(met.get(m, 0)),
               {"REPETIR_15": "1 ponto na série", "MEDIA_2DP": "2 a 5 pontos",
                "ULTIMA_OBSERVACAO": "backtesting",
                "SAZONAL_NAIVE": "backtesting",
                "HOLT_WINTERS_DAMPED": "backtesting"}.get(m, "—")]
              for m in ("REPETIR_15", "MEDIA_2DP", "ULTIMA_OBSERVACAO",
                        "SAZONAL_NAIVE", "HOLT_WINTERS_DAMPED")]
    # y 3.45 e não 3.35: a tabela de cima tem 4 linhas de 0,55in (2,2in) desde 1,4in
    # e terminava em 3,6in — o texto da direita nascia DENTRO dela.
    _tabela(s, ["Método escolhido", "Pontos", "Critério"], linhas,
            0.5, 3.5, 7.0, [3.0, 1.2, 2.8], 0.32, 10.5)
    _bullets(s, [
        ("O intervalo alarga com o horizonte", True), "(√h, pela dispersão dos erros)",
        ("Projeção nunca vira fato", True),
        "vive em tb_projecao, fora da matriz, sempre rotulada.",
        ("Cobertura auditada", True),
        f"{n['series']} séries · {n['projecoes']} pontos · 10 de 10 rubricas com fato "
        "têm projeção.",
    ], 7.8, 3.5, 5.0, 2.4, 12.5, espaco=7)
    _caixa(s, 0.8, 5.75, 12.0, 1.0,
           f"Confiança média das projeções: {n['confianca_proj']}. Com poucos pontos o "
           "método e a confiança degradam de forma explícita — a projeção não se apresenta "
           "com a mesma segurança da série longa.",
           12.5, VERDE_ESCURO, True)

    # 17 — governança e descoberta
    s = prox("15. Governança — o que foi anunciado e ainda não está aqui", "O ETL responde o que eu tenho; a descoberta responde o que falta")
    _bullets(s, [
        ("SEC EDGAR como canal confiável:", True),
        "submissions diz o que foi protocolado (e a reportDate define o trimestre); "
        "companyfacts traz o número estruturado por tag XBRL, com frame trimestral.",
        ("A lacuna de XBRL é o sinal-chave:", True),
        "o trimestre foi comunicado, mas o frame CY20xxQn ainda não existe — é "
        "\"ainda não dá para fechar o trimestre\", dito explicitamente.",
        ("Documento principal de 6-K é só a capa:", True),
        "as demonstrações estão nos anexos (Shell: 48 · Chevron: 70) e o número vem do "
        "companyfacts.",
        ("Exceção declarada, nunca disfarçada:", True),
        "Chevron e BP devolvem HTTP 403 e Petrobras/Equinor usam página dinâmica — o "
        "relatório diz isso em vez de fingir cobertura.",
    ], 0.8, 1.45, 7.1, 4.9, 13, espaco=8)
    _tabela(s, ["Empresa", "CIK", "Formulário"],
            [["Petrobras", "0001119639", "6-K"], ["Shell", "0001306965", "6-K"],
             ["BP", "0000313807", "6-K"], ["Chevron", "0000093410", "10-Q · 8-K"],
             ["ExxonMobil", "0000034088", "10-Q · 8-K"], ["TotalEnergies", "0000879764", "6-K"],
             ["Equinor", "0001140625", "6-K"]],
            8.2, 1.45, 4.6, [1.6, 1.5, 1.5], 0.33, 10)
    _caixa(s, 8.2, 4.3, 4.6, 1.9,
           "Fontes primárias: release e demonstrações do RI de cada empresa (136 PDFs + "
           "27 planilhas).\nFontes secundárias: SEC XBRL, usada como conferência e "
           "preenchimento de lacuna — nunca sobrescreve o dado da RI.",
           12, VERDE_ESCURO, True)

    # 18 — auditoria
    s = prox("16. Auditoria e relatório em PDF", "Quem decidiu o quê, quando e com qual justificativa")
    _bullets(s, [
        ("Trilha de decisão append-only em tb_auditoria_decisao.", True),
        "aceitar → RESOLVIDO · rejeitar · ignorar · reabrir (volta para a fila sem apagar "
        "a decisão anterior).",
        ("Relatório em PDF com o período escolhido", True),
        "situação da auditoria · aging da fila · quem decidiu · a trilha do período com "
        "empresa, período e rubrica do item auditado · a fila no encerramento.",
        ("Gerado por três caminhos", True),
        "CLI: app_main.py auditoria relatorio --de … --ate …  ·  botão na aba Auditoria "
        "(web e desktop)  ·  GET /api/auditoria?pdf=1",
    ], 0.8, 1.45, 7.3, 3.6, 13, espaco=8)
    _kpis(s, [(str(n["alertas"]), "alertas", VERDE),
              (str(n["fila"]), "itens na fila", VERDE),
              (str(n["fila_aberta"]), "ainda abertos", LARANJA),
              (str(n["decisoes"]), "decisões registradas", VERDE)],
          y=1.45, x0=8.3, larg=4.5, h=1.05)
    _caixa(s, 8.3, 2.75, 4.5, 2.3,
           "Correção do próprio sistema:\na taxa de resolução anunciava 100% com 875 "
           "itens abertos — o denominador era o número de tipos de decisão, não o total. "
           "Agora são 50% (2 de 4), e o painel mostra os dois contadores.",
           12, VERDE_ESCURO, True)

    # 19 — glossário
    s = prox("17. Glossário de indicadores", "O que cada número significa, em que unidade e com que sinal")
    _tabela(s, ["Código", "Nome", "Unidade", "Sinal"],
            [["RECEITA_LIQUIDA", "Receita líquida", "USD bi", "positivo"],
             ["EBITDA_AJUSTADO", "EBITDA ajustado", "USD bi", "positivo"],
             ["LUCRO_LIQUIDO", "Lucro líquido (acionistas)", "USD bi", "positivo"],
             ["FCO", "Fluxo de caixa operacional", "USD bi", "positivo"],
             ["DIVIDA_LIQUIDA", "Dívida líquida", "USD bi", "positivo"],
             ["CAPEX", "Investimentos", "USD bi", "POSITIVO (saída de caixa)"],
             ["DESPESA_OPERACIONAL", "Despesas operacionais", "USD bi", "NEGATIVO (redutora)"],
             ["EFETIVO_TOTAL", "Total de efetivo", "pessoas", "positivo"],
             ["PRODUCAO_BOED", "Produção total", "kboed", "positivo"]],
            0.5, 1.4, 7.6, [2.6, 3.4, 1.2, 2.6], 0.35, 10.5, destaque={6})
    _bullets(s, [
        ("Por que importa:", True),
        "sem convenção de sinal explícita, despesa positiva e CAPEX negativo invertem a "
        "leitura de qualquer gráfico.",
        ("Inclui fórmula e dependências", True),
        "de quais rubricas cada indicador derivado depende.",
        ("Disponível na web, no desktop e no e-mail", True),
        "é a leitura necessária para interpretar os gráficos, não um apêndice.",
    ], 8.4, 1.45, 4.4, 4.4, 12.5, espaco=8)

    # 20 — testes
    s = prox("18. O que os testes encontraram", "20 bugs reais — e não por leitura de código")
    _tabela(s, ["#", "Bug", "Como apareceu"],
            [["1", "Transcrição 1T25.pdf era parseado (skip-list sem acento)",
              "teste de classificação de PDF"],
             ["2", "R$ lido como USD", "teste de moeda"],
             ["3", "IC95 invertido em série negativa", "teste de projeção"],
             ["4", "ZeroDivisionError na aba Qualidade com execução sem carga",
              "suíte completa, após o modo incremental"],
             ["5", "Duração medida antes do parse zerava a coluna do painel",
              "teste do painel de ETL"],
             ["6", "Taxa de resolução em 100% com 875 itens abertos",
              "auditoria resumo na base real"],
             ["7", "GUI quebrava com base vazia (API removida no pyqtgraph 0.14)",
              "teste da aba Projeções sem projeção"],
             ["8", "Lista fixa de rubricas deixava 3 indicadores sem projeção",
              "verificação pedida pelo usuário"]],
            0.5, 1.4, 12.35, [0.5, 6.6, 4.2], 0.44, 11)
    _caixa(s, 0.8, 5.5, 12.0, 1.15,
           "O mais honesto: a projeção não cobria FCL, DIVIDA_BRUTA e DESPESA_OPERACIONAL por "
           "causa de uma lista fixa no código, sem aviso na tela. Hoje é dirigida pelos "
           "dados e a aba mostra a cobertura — 10 de 10. Isso só apareceu porque alguém "
           "perguntou.", 12.5, VERDE_ESCURO, True)

    # 21 — limites
    s = prox("19. Limites e riscos assumidos", "Assumir o limite é o que dá credibilidade")
    _tabela(s, ["Limite", "Impacto", "Como está registrado"],
            [["RI dinâmico (Petrobras, Equinor) ou bloqueado (Chevron, BP: 403)",
              "sem canal primário automatizado", "relatório de descoberta mostra o erro por empresa"],
             ["Documento principal do 6-K é a capa", "comunicado é achado, número não",
              "anexos do index.json + companyfacts"],
             ["Histórico local concentrado em 2025–2026", "2023–2024 dependem da SEC",
              "2 testes marcados como skip, explicitamente"],
             ["Cobertura de rubricas desigual entre empresas", "LUCRO_BRUTO só na Petrobras",
              "DQS de completude torna visível em vez de esconder"],
             ["Cobertura de 36,5% das páginas no PDF", "parse lê 12 páginas (30 em DF)",
              "\"cobertura\" exibida ao lado do throughput"],
             ["Métrica de leitura em 133 PDFs", "581 fontes sem arquivo local",
              "ficam fora da média (não medido ≠ mediu zero)"],
             ["Série curta não é tendência", "projeção com intervalo largo",
              "método e confiança degradam explicitamente"],
             ["IFRS 16 não é homogeneizado", "CAPEX e EBITDA divergem entre empresas",
              "registrado como backlog"]],
            0.5, 1.4, 12.35, [4.4, 3.2, 4.75], 0.44, 10.5)

    # 22 — próximos passos
    s = prox("20. Próximos passos", "Do que é manutenção para o que é/value novo")
    _bullets(s, [
        ("Ler os anexos do arquivamento SEC em profundidade", True),
        "hoje eu entrego o arquivo, não a tabela que está dentro dele.",
        ("Rolling-origin", True),
        "recalcular o passado e medir o erro real das projeções — hoje tenho método por "
        "backtesting, ainda não backtest ao longo da história viva.",
        ("Cenários com Brent/FX", True),
        "e intervalo que responda à covariância dos fatores, não a uma soma de erros.",
        ("Método escolhido por rubrica", True),
        "dívida é nível, não sazonalidade — a escolha não pode ser global.",
        ("Cache de texto por hash de PDF", True),
        "mata o último custo do reprocessamento.",
        ("RI com render de JS", True),
        "fecha o canal primário, hoje bloqueado em 2 de 7 empresas.",
        ("Score de proveniência", True),
        "profundidade da cadeia: RI → SEC → derivada.",
    ], 0.8, 1.45, 11.8, 4.6, 13.5, espaco=6)

    # 23 — fecho
    s = _slide(prs, VERDE_ESCURO)
    _caixa(s, 0.9, 1.2, 11.5, 0.5, "O que eu quero que levem deste projeto", 15, AMARELO, True)
    _caixa(s, 0.9, 1.9, 11.5, 2.6,
           "\"Não é o dashboard. É a cadeia de decisões:\n"
           "de onde veio este número, ele é confiável, e o que ainda precisa de olho humano.\n\n"
           "O painel mostra o resultado. O que sustenta o resultado é a procedência, "
           "a régua de qualidade e a fila de quem precisa conferir.\"",
           20, BRANCO, espaco=10)
    # KPIs em faixa única, valor em cima e rótulo embaixo: numa faixa só, "7 empresas"
    # ia para o rótulo e "272 fatos" ficava sem legenda nenhuma.
    _kpis(s, [(str(n["fatos"]), "fatos", BRANCO),
                  (str(n["fontes"]), "fontes catalogadas", BRANCO),
                  (f"{n['dqs']}", "DQS médio", BRANCO),
                  (str(n["projecoes"]), f"projeções em {n['series']} séries", BRANCO),
                  ("0", "erros de carga", BRANCO),
                  ("110", "testes automatizados", BRANCO)],
          y=5.0, x0=0.9, larg=11.5, h=1.0)
    _caixa(s, 0.9, 6.3, 11.5, 0.4,
           "app_main.py web --serve · app_main.py auditoria relatorio --de … --ate …",
           12, "BFD9CC", align="meio")

    destino = Path(destino) if destino else DOCS_DIR / "APRESENTACAO_PETROBRAS.pptx"
    destino.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(destino))
    _ = Pt
    return str(destino)


# ============================================================================
# APRESENTAÇÃO VISUAL — uma tela do produto por slide
# ============================================================================
IMAGENS = DOCS_DIR / "ENTREGAVEIS" / "1_PAINEL_E_IMAGENS"

# (arquivo, título, subtítulo, o que a tela prova)
SLIDES_VISUAIS = [
    ("aba_00_visao_executiva", "Visão executiva", "Leitura do trimestre e gráficos de apoio",
     "O painel abre em uma pergunta, não em uma lista de tabelas: como está o "
     "benchmark neste trimestre."),
    ("aba_01_comparacao", "Comparação entre empresas", "Matriz do trimestre, mesma unidade",
     "Sete empresas em uma matriz só — receita, EBITDA, lucro, fluxo de caixa, "
     "investimento e dívida, em USD bilhões."),
    ("aba_03_evolucao_historica", "Evolução histórica", "Série temporal das empresas",
     "O gráfico é a resposta para “como foi a evolução”, não uma foto de hoje."),
    ("aba_02_expandidos", "Indicadores expandidos", "12 indicadores, com fórmula e dependências",
     "Cada indicador derivado declara de quais rubricas depende — o número não é "
     "uma caixa-preta."),
    ("aba_04_efetivo", "Efetivo", "Âncora anual de headcount",
     "Efetivo é o único indicador obrigatório de todo o setor, e é anual: vira "
     "âncora de conferência do resto."),
    ("aba_08_projecoes", "Projeções", "Real × projetado com IC 95%",
     "A projeção é desenhada separada do fato e sempre rotulada — nunca entra na "
     "matriz como se fosse número publicado."),
    ("aba_06_gestao_etl", "Gestão ETL — o que rodou e quanto leu", "M8.12",
     "O parser não é uma caixa-preta: cada PDF diz quantas páginas ele percorreu, "
     "quantas tabelas achou e qual o throughput."),
    ("aba_09_qualidade", "Evolução da qualidade no tempo", "M7.23",
     "O scorecard guardava só o último estado. A série mostra se a qualidade "
     "subiu, caiu ou estagnou — e quem mais mudou."),
    ("aba_07_auditoria", "Auditoria", "M2",
     "O que exige olho humano, com triagem: aceitar, rejeitar, ignorar. Cada "
     "decisão fica na trilha e pode virar relatório em PDF."),
    ("aba_05_fontes_gestao", "Gestão de fontes", "M1",
     "Cada documento catalogado com origem, hash e status — e o CRUD que permite "
     "corrigir o acervo."),
    ("aba_10_glossario", "Glossário", "12 indicadores definidos",
     "Por que a despesa é negativa e o CAPEX positivo está escrito, com a fórmula "
     "de cada derivado."),
]


def construir_visual(destino: Path | None = None,
                     n: dict[str, Any] | None = None) -> str:
    """Deck de telas do produto: uma imagem real por slide, com legenda curta."""
    from pptx import Presentation
    from pptx.util import Inches as In, Pt

    n = n or _numeros()
    prs = Presentation()
    prs.slide_width, prs.slide_height = In(13.333), In(7.5)
    num = 0
    sem_imagem: list[str] = []

    def prox(titulo: str, subtitulo: str = "") -> Any:
        nonlocal num
        num += 1
        s = _slide(prs)
        _cabecalho(s, titulo, subtitulo, num)
        _rodape(s)
        return s

    # capa
    s = _slide(prs, VERDE_ESCURO)
    faixa = s.shapes.add_shape(1, In(0), In(5.6), In(13.333), In(0.22))
    faixa.fill.solid()
    faixa.fill.fore_color.rgb = _rgb(AMARELO)
    faixa.line.fill.background()
    faixa.shadow.inherit = False
    _caixa(s, 0.9, 1.35, 11.5, 1.0, "PetroAnalytics", 50, BRANCO, True)
    _caixa(s, 0.95, 2.35, 11.5, 0.55,
           "Benchmark Petrobras vs 6 pares — o produto, tela por tela", 20, AMARELO)
    _caixa(s, 0.95, 3.1, 11.5, 1.5,
           f"{n['empresas']} empresas · {n['periodos']} trimestres (2023Q1–2026Q2) · "
           f"{n['fontes']} fontes catalogadas · {n['fatos']} fatos com fonte, data, "
           f"unidade e confiança\nDQS {n['dqs']} · {n['projecoes']} projeções · "
           f"{n['erros']} erros de carga", 15, "E8F5EE", espaco=8)
    _caixa(s, 0.95, 5.95, 11.5, 0.5,
           "Telas capturadas do painel rodando (Chrome headless) — nenhum mock-up",
           12.5, "BFD9CC")

    for arquivo, titulo, subtitulo, leitura in SLIDES_VISUAIS:
        s = prox(titulo, subtitulo)
        caminho = IMAGENS / f"{arquivo}.png"
        # max_h = 5.35 e não 4.85: a área útil vai de 1,25 a 6,6 (a legenda ocupa
        # 0,3 abaixo). Com 4.85 a figura de 1500x1000 saía com 8,5cm de margem
        # lateral vazia — o slide parecia "a foto pequena no meio do vazio".
        if not _figura(s, caminho, 0.3, 1.2, 12.73, 5.35,
                       legenda=leitura, rodape=""):
            sem_imagem.append(arquivo)
            _caixa(s, 0.45, 2.5, 12.45, 1.2,
                   f"(sem imagem: rode `python workers\\screenshots.py` para gerar "
                   f"{arquivo}.png)", 14, LARANJA, align="meio")
        _ = Pt

    # fecho com as telas de uma vez
    s = prox("O produto inteiro", "11 telas, um sistema")
    # 3x3 preenchendo a área: cada miniatura é centralizada na CÉLULA (não no
    # canto) e traz o nome da aba embaixo. Sem centralizar, as telas com proporção
    # mais baixa (ETL 1500x720) encostavam em cima e deixavam um vão embaixo.
    from PIL import Image
    cols, linhas = 3, 3
    larg = 12.45 / cols
    alt = (6.55 - 1.2) / linhas
    for i, (arquivo, titulo, _, _) in enumerate(SLIDES_VISUAIS[:9]):
        caminho = IMAGENS / f"{arquivo}.png"
        if not caminho.exists():
            continue
        cx = 0.45 + (i % cols) * larg
        cy = 1.2 + (i // cols) * alt
        w, h = Image.open(caminho).size
        cel_w, cel_h = larg - 0.16, alt - 0.42      # 0.42 = nome da aba + folga
        escala = min(cel_w / w, cel_h / h)
        larg_fig, alt_fig = w * escala, h * escala
        s.shapes.add_picture(str(caminho), In(cx + (larg - larg_fig) / 2),
                             In(cy + (alt - alt_fig - 0.28) / 2),
                             In(larg_fig), In(alt_fig))
        _caixa(s, cx, cy + alt - 0.3, larg, 0.28, titulo, 10, CINZA, align="meio")
    _caixa(s, 0.45, 6.55, 12.45, 0.4,
           f"{n['empresas']} empresas · {n['fatos']} fatos · DQS {n['dqs']} · "
           f"{n['projecoes']} projeções · {n['erros']} erros de carga · 114 testes",
           13, VERDE_ESCURO, True, "meio")

    destino = Path(destino) if destino else DOCS_DIR / "APRESENTACAO_VISUAL.pptx"
    destino.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(destino))
    if sem_imagem:
        print(f"  ! slides sem imagem: {', '.join(sem_imagem)}")
    return str(destino)


if __name__ == "__main__":
    print(construir_visual())