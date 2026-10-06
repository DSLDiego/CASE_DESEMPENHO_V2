"""Glossario de indicadores: definicao, unidade, formula e como e calculado.

Fonte unica de verdade para o painel Web, a GUI e o PDF. Cada entrada diz o que o
indicador significa, a unidade, a formula quando ele e DERIVADO (e de quais
rubricas depende) e a observacao de sinal — que e o ponto que mais gera duvida
na leitura ("por que despesa e negativa?", "por que CAPEX e positivo?").

Rubricas sem formula saookies de balanco/resultado: vem do documento de origem
(RI ou SEC XBRL) e por isso a coluna `formula` fica vazia de proposito.
"""
from __future__ import annotations

from typing import Any

# categoria: Financeiro | Operacional | Mercado | Derivado
GLOSSARIO: list[dict[str, Any]] = [
    # ---------------------------------------------------------------- resultado
    {"codigo": "RECEITA_LIQUIDA", "nome": "Receita líquida", "categoria": "Financeiro",
     "unidade": "USD bi",
     "definicao": "Faturamento bruto menos deduções de impostos sobre vendas, devoluções "
                  "e abatimentos. É a receita efetivamente reconhecida no trimestre.",
     "formula": None, "depende": [], "sinal": "Positivo",
     "fonte": "Demonstrativo de resultado (RI) ou tag us-gaap:Revenues / ifrs-full:Revenue (SEC)"},
    {"codigo": "EBITDA_AJUSTADO", "nome": "EBITDA ajustado", "categoria": "Financeiro",
     "unidade": "USD bi",
     "definicao": "Lucro antes de juros, impostos, depreciação e amortização, já sem itens "
                  "considerados não recorrentes pela companhia (ganhos e perdas não "
                  "recorrentes, non-recurring charges).",
     "formula": None, "depende": [], "sinal": "Positivo",
     "fonte": "Release de resultados (RI/SEC)"},
    {"codigo": "LUCRO_BRUTO", "nome": "Lucro bruto", "categoria": "Financeiro",
     "unidade": "USD bi",
     "definicao": "Resultado após custos e despesas diretas, antes das despesas "
                  "operacionais, financeiras e de imposto.",
     "formula": None, "depende": [], "sinal": "Positivo",
     "fonte": "Demonstrativo de resultado (RI) ou tag us-gaap:GrossProfit"},
    {"codigo": "LUCRO_LIQUIDO", "nome": "Lucro líquido", "categoria": "Financeiro",
     "unidade": "USD bi",
     "definicao": "Resultado do período após todos os custos, despesas, juros, "
                  "impostos e participações de não controladores, atribuível aos acionistas.",
     "formula": None, "depende": [], "sinal": "Positivo (negativo = prejuízo)",
     "fonte": "Demonstrativo de resultado (RI) ou tag us-gaap:NetIncomeLoss"},
    {"codigo": "DESPESA_OPERACIONAL", "nome": "Despesas operacionais", "categoria": "Financeiro",
     "unidade": "USD bi",
     "definicao": "Custo e despesa de operação do trimestre (selling, G&A, logística, "
                  "materiais), já excluídos dos itens específicos de cada rubrica.",
     "formula": None, "depende": [], "sinal": "NEGATIVO por convenção (custo reduz resultado)",
     "fonte": "Demonstrativo de resultado (RI)"},
    # ---------------------------------------------------------------- caixa
    {"codigo": "FCO", "nome": "Fluxo de caixa operacional", "categoria": "Financeiro",
     "unidade": "USD bi",
     "definicao": "Caixa gerado pela operação no trimestre: lucro ajustado por itens não "
                  "monetários e ajustado pelas mudanças no capital de giro.",
     "formula": None, "depende": [], "sinal": "Positivo",
     "fonte": "Fluxo de caixa (RI) ou tag us-gaap:NetCashProvidedByUsedInOperatingActivities"},
    {"codigo": "FCL", "nome": "Fluxo de caixa livre", "categoria": "Financeiro",
     "unidade": "USD bi",
     "definicao": "Caixa que sobra da operação depois do investimento em projetos "
                  "(capex). É o dinheiro disponível para dívida, dividendos e caixa.",
     "formula": "FCO − CAPEX", "depende": ["FCO", "CAPEX"], "sinal": "Positivo",
     "fonte": "Derivado (release costuma publicar, mas o painel calcula para padronizar)"},
    {"codigo": "CAPEX", "nome": "Investimentos (CAPEX)", "categoria": "Financeiro",
     "unidade": "USD bi",
     "definicao": "Investimentos em projetos e programas no período (exploração, "
                  "produção, refino e outros).",
     "formula": None, "depende": [], "sinal": "POSITIVO por convenção (entrada de caixa = uso), "
                  "mesmo sendo despesa",
     "fonte": "Fluxo de caixa / release de resultados"},
    # ---------------------------------------------------------------- estrutura
    {"codigo": "DIVIDA_BRUTA", "nome": "Dívida bruta", "categoria": "Financeiro",
     "unidade": "USD bi",
     "definicao": "Soma de empréstimos, financiamentos e títulos de dívida, sem desconto "
                  "do caixa e equivalentes.",
     "formula": None, "depende": [], "sinal": "Positivo (passivo)",
     "fonte": "Demonstrativo de posição financeira (RI)"},
    {"codigo": "DIVIDA_LIQUIDA", "nome": "Dívida líquida", "categoria": "Financeiro",
     "unidade": "USD bi",
     "definicao": "Dívida bruta menos caixa e equivalentes de caixa.",
     "formula": None, "depende": [], "sinal": "Positivo (passivo); negativo = caixa líquido",
     "fonte": "Demonstrativo de posição financeira (RI)"},
    # ---------------------------------------------------------------- operacional
    {"codigo": "PRODUCAO_BOED", "nome": "Produção total", "categoria": "Operacional",
     "unidade": "kboed",
     "definicao": "Produção de petróleo e gás em milhares de barris de petróleo por dia "
                  "equivalente (médios barris de óleo).",
     "formula": None, "depende": [], "sinal": "Positivo",
     "fonte": "Release de resultados / relatório de produção (RI)"},
    {"codigo": "FUT_REFINO", "nome": "Capacidade de refino", "categoria": "Operacional",
     "unidade": "kboed",
     "definicao": "Capacidade nominal das refinarias, em milhares de barris por dia.",
     "formula": None, "depende": [], "sinal": "Positivo",
     "fonte": "Planilha de capacidade (RI)"},
    {"codigo": "EFETIVO_TOTAL", "nome": "Total de efetivo", "categoria": "Operacional",
     "unidade": "pessoas",
     "definicao": "Número de empregados no fim do trimestre (mão de obra própria).",
     "formula": None, "depende": [], "sinal": "Positivo",
     "fonte": "DF / release (RI); no painel, âncoras anuais (comando efetivo)"},
    # ---------------------------------------------------------------- derivados
    {"codigo": "MARGEM_EBITDA", "nome": "Margem EBITDA", "categoria": "Derivado",
     "unidade": "%",
     "definicao": "Quanto de cada dólar de receita vira EBITDA. Mede rentabilidade "
                  "operacional antes de capital e estrutura financeira.",
     "formula": "EBITDA_AJUSTADO ÷ RECEITA_LIQUIDA × 100", "depende": ["EBITDA_AJUSTADO", "RECEITA_LIQUIDA"],
     "sinal": "Positivo", "fonte": "Calculado (`app_main.py derivados`)"},
    {"codigo": "MARGEM_LIQUIDA", "nome": "Margem líquida", "categoria": "Derivado",
     "unidade": "%",
     "definicao": "Quanto de cada dólar de receita sobra como lucro líquido.",
     "formula": "LUCRO_LIQUIDO ÷ RECEITA_LIQUIDA × 100", "depende": ["LUCRO_LIQUIDO", "RECEITA_LIQUIDA"],
     "sinal": "Negativo = prejuízo", "fonte": "Calculado (`app_main.py derivados`)"},
    {"codigo": "DIVIDA_LIQUIDA_EBITDA", "nome": "Alavancagem (dívida líquida/EBITDA)",
     "categoria": "Derivado", "unidade": "x",
     "definicao": "Quantos anos de EBITDA seriam necessários para quitar a dívida líquida. "
                  "Principal medidor de risco de crédito do setor.",
     "formula": "DIVIDA_LIQUIDA ÷ EBITDA_AJUSTADO", "depende": ["DIVIDA_LIQUIDA", "EBITDA_AJUSTADO"],
     "sinal": "Positivo", "fonte": "Calculado (`app_main.py derivados`)"},
    {"codigo": "DIVIDEND_YIELD", "nome": "Dividend yield", "categoria": "Derivado",
     "unidade": "%",
     "definicao": "Proporção dos dividendos de um período sobre o preço da ação.",
     "formula": "dividendos por ação ÷ preço da ação × 100",
     "depende": ["COTACAO"],
     "sinal": "Positivo", "fonte": "Derivado de cotação + proventos"},
    {"codigo": "COTACAO", "nome": "Cotação", "categoria": "Mercado",
     "unidade": "USD/ação",
     "definicao": "Preço de fechamento da ação no fim do trimestre.",
     "formula": None, "depende": [], "sinal": "Positivo",
     "fonte": "Snapshot de mercado (Investidor10)"},
    {"codigo": "P_L", "nome": "P/L", "categoria": "Derivado",
     "unidade": "x",
     "definicao": "Múltiplo preço/lucro: quanto se paga por unidade de lucro.",
     "formula": "COTACAO ÷ lucro por ação",
     "depende": ["COTACAO", "LUCRO_LIQUIDO"],
     "sinal": "Positivo", "fonte": "Derivado"},
]

# Indice por codigo
POR_CODIGO: dict[str, dict[str, Any]] = {g["codigo"]: g for g in GLOSSARIO}


def obter(codigo: str) -> dict[str, Any]:
    """Glossario de um indicador; se nao catalogado, devolve um stub explicito."""
    if codigo in POR_CODIGO:
        return dict(POR_CODIGO[codigo])
    return {"codigo": codigo, "nome": codigo, "categoria": "Nao catalogado",
            "unidade": "", "definicao": "Indicador sem definicao no glossario "
            "(gerado pelo De-Para automatico).", "formula": None,
            "depende": [], "sinal": "", "fonte": "De-Para automatico (aprendido)"}


def buscar(termo: str) -> list[dict[str, Any]]:
    """Glossario filtrado por codigo, nome ou definicao."""
    alvo = (termo or "").strip().lower()
    if not alvo:
        return list(GLOSSARIO)
    achados = []
    for g in GLOSSARIO:
        if alvo in g["codigo"].lower() or alvo in g["nome"].lower() \
                or alvo in g["definicao"].lower() \
                or alvo in (g.get("formula") or "").lower():
            achados.append(dict(g))
    return achados


def por_categoria() -> list[dict[str, Any]]:
    """Glossario agrupado por categoria, na ordem em que os indicadores aparecem."""
    ordem = ["Financeiro", "Operacional", "Derivado", "Mercado", "Nao catalogado"]
    grupos: dict[str, list[dict[str, Any]]] = {}
    for g in GLOSSARIO:
        grupos.setdefault(g["categoria"], []).append(dict(g))
    return [{"categoria": c, "indicadores": grupos[c]}
            for c in ordem if c in grupos]


def resumo() -> dict[str, Any]:
    """Payload usado pela API e pela aba Glossario (Web e GUI)."""
    return {"total": len(GLOSSARIO),
            "com_formula": sum(1 for g in GLOSSARIO if g.get("formula")),
            "categorias": por_categoria(),
            "indicadores": [dict(g) for g in GLOSSARIO]}
