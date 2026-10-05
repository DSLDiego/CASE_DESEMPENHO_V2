"""Configuracao central do PetroAnalytics PoC (MVC-W + SQLite).

Premissas:
- Moeda padrao do painel: USD bilhoes (conversao via PTAX com fallback).
- Periodos PoC: 2025Q4, 2026Q1, 2026Q2 (pastas 2025_4T, 2026_1T, 2026_2T do Container).
- Empresas: Petrobras + 6 pares (universo completo do case).
"""
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
DOWNLOADS_DIR = DATA_DIR / "downloads"
DB_PATH = DATA_DIR / "petro_analytics.db"
CATALOG_JSON = DATA_DIR / "sources_catalog.json"
CATALOG_CSV = DATA_DIR / "sources_catalog.csv"
WEB_HTML = DATA_DIR / "painel_benchmark.html"

CONTAINER_DIR = Path(r"C:\Users\diego\Downloads\CASE_DESEMPENHO\03_Conteiner")

USER_AGENT = "PetroAnalytics-PoC diego.silva@exemplo.com"

COMPANIES: dict[str, dict[str, str]] = {
    "PETROBRAS": {"codigo": "PETR4", "pais": "Brasil", "cik": "0001119639", "moeda_relato": "USD"},
    "SHELL": {"codigo": "SHEL", "pais": "Reino Unido", "cik": "0001306965", "moeda_relato": "USD"},
    "BP": {"codigo": "BP", "pais": "Reino Unido", "cik": "0000313807", "moeda_relato": "USD"},
    "CHEVRON": {"codigo": "CVX", "pais": "EUA", "cik": "0000093410", "moeda_relato": "USD"},
    "EXXONMOBIL": {"codigo": "XOM", "pais": "EUA", "cik": "0000034088", "moeda_relato": "USD"},
    "TOTALENERGIES": {"codigo": "TTE", "pais": "Franca", "cik": "0000879764", "moeda_relato": "USD"},
    "EQUINOR": {"codigo": "EQNR", "pais": "Noruega", "cik": "0001140625", "moeda_relato": "USD"},
}

# Indicadores canonicos da PoC (4-6 financeiros + efetivo obrigatorio).
INDICATORS: list[dict[str, str]] = [
    {"codigo": "RECEITA_LIQUIDA", "nome": "Receita liquida", "unidade": "USD bi", "categoria": "Financeiro"},
    {"codigo": "EBITDA_AJUSTADO", "nome": "EBITDA ajustado", "unidade": "USD bi", "categoria": "Financeiro"},
    {"codigo": "LUCRO_LIQUIDO", "nome": "Lucro liquido (acionistas)", "unidade": "USD bi", "categoria": "Financeiro"},
    {"codigo": "FCO", "nome": "Fluxo de caixa operacional", "unidade": "USD bi", "categoria": "Financeiro"},
    {"codigo": "DIVIDA_LIQUIDA", "nome": "Divida liquida", "unidade": "USD bi", "categoria": "Financeiro"},
    {"codigo": "EFETIVO_TOTAL", "nome": "Total de efetivo", "unidade": "pessoas", "categoria": "Operacional"},
    {"codigo": "PRODUCAO_BOED", "nome": "Producao total", "unidade": "kboed", "categoria": "Operacional"},
    # --- expandidos (2a leva, Matriz Comparativa) ---
    {"codigo": "CAPEX", "nome": "Investimentos (CAPEX)", "unidade": "USD bi", "categoria": "Financeiro"},
    {"codigo": "DIVIDA_BRUTA", "nome": "Divida bruta", "unidade": "USD bi", "categoria": "Financeiro"},
    {"codigo": "LUCRO_BRUTO", "nome": "Lucro bruto", "unidade": "USD bi", "categoria": "Financeiro"},
    {"codigo": "FCL", "nome": "Fluxo de caixa livre", "unidade": "USD bi", "categoria": "Financeiro"},
    {"codigo": "DESPESA_OPERACIONAL", "nome": "Despesas operacionais", "unidade": "USD bi", "categoria": "Financeiro"},
]

PERIODS = ["2025Q4", "2026Q1", "2026Q2"]

# --- Paleta unica de cores (fonte de verdade para web, GUI e e-mail) ----------
# Okabe-Ito (colorblind-safe) + roxo para a 7a empresa. Cores anteriores eram
# 4 azuis parecidos: series temporais ficavam indistinguiveis no grafico de linha.
PALETA: dict[str, str] = {
    "PETROBRAS": "#0072B2",       # azul (destacado como referencia do case)
    "SHELL": "#E69F00",           # ambar
    "BP": "#009E73",              # verde-azulado
    "CHEVRON": "#CC79A7",         # magenta
    "EXXONMOBIL": "#7B2CBF",      # roxo
    "TOTALENERGIES": "#B22222",   # vermelho-fogo
    "EQUINOR": "#66A61E",         # verde-amarelo
}
# Traço e marcador por empresa: garante leitura mesmo em escala de cinza
# (Plotly nao repete estilo quando so a cor muda).
ESTILO_SERIE: dict[str, dict[str, object]] = {
    "PETROBRAS": {"dash": "solid", "symbol": "circle", "width": 3.5},
    "SHELL": {"dash": "dash", "symbol": "square", "width": 2.2},
    "BP": {"dash": "dot", "symbol": "diamond", "width": 2.2},
    "CHEVRON": {"dash": "dashdot", "symbol": "triangle-up", "width": 2.2},
    "EXXONMOBIL": {"dash": "longdash", "symbol": "triangle-down", "width": 2.2},
    "TOTALENERGIES": {"dash": "dashdot", "symbol": "hexagon", "width": 2.2},
    "EQUINOR": {"dash": "longdashdot", "symbol": "star", "width": 2.2},
}

# PTAX fallback (BRL por USD, fechamento do trimestre) p/ conversao BRL->USD.
PTAX_FALLBACK = {"2025Q4": 5.40, "2026Q1": 5.26, "2026Q2": 5.05}

# Arquivos PDF que valem parsing profundo (releases/resultados). Transcripts e
# slides vao para o catalogo mas nao bloqueiam o pipeline.
PDF_PARSE_ALLOW = ("release", "result", "desempenho", "qra", "accounts", "press",
                     "financial-statement", "statements-and-review")
PDF_PARSE_SKIP = ("transcript", "slides", "presentation", "speech", "webcast", "transcricao")

CONFIDENCE_MIN = 0.70
QOQ_SPIKE_PCT = 40.0
