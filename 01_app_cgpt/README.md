# Benchmarking Financeiro Trimestral — PoC v0 (Python + SQLite + PySide6)

PoC funcional do case: compara Petrobras vs Equinor/Shell/TotalEnergies em 4T2025–2T2026,
com ETL de coleta em alta velocidade, qualidade/rastreabilidade e painel próprio.

## Premissas (regras rígidas §9.1)
- **Correto > reprodutível > auditável > rápido** (nessa ordem).
- Download primeiro, extração depois (evidência local imutável + SHA-256).
- Total de Efetivo é operacional/capital humano, mantido por exigência do case.
- 2T2026 = trimestre mais recente (verificado 02/10/2026 no histórico v0).
- Base `data/demo_metrics.csv` é DEMO (`is_demo=1`); produção usa CSV oficial ou coleta web.

## Quickstart
```bat
pip install -r requirements.txt
python app_main.py --init
python app_main.py
```
- CLI: `python app_main.py --cli status` · ETL: `python app_main.py --etl data/raw --mode PROCESS --batch 10 --scheduler SJF`
- Testes: `python app_main.py --test` ou `pytest -q`

## Estrutura
```
app_main.py  config/  database/schema.sql  data/demo_metrics.csv  docs/
scripts/{bootstrap,collect_web,import_csv,demo_quality}.py
src/models/  src/utils/{hardware,period,bigstring}.py
src/etl/{acquisition,parsers,extractors,quality,scheduler,batch}.py
src/repositories/sqlite_repo.py  src/services/app_services.py
src/controllers/app_controllers.py  src/views/main_window.py  tests/
```

## Painel (12 abas)
Layout: sidebar 25% (fora das tabs, accordions QToolBox, scroll H+V, botão ❮/❯ de
colapso) + ChartArea 75% com as tabs em grid, fontes/botões compactos, temas light/dark.
Abas: Executiva · Benchmark · Evolução · Produtividade · Dados · Qualidade · Fontes ·
ETL/Batch · Hardware · **Gráficos Qt (pyqtgraph)** · Fontes Web (CRUD) · Fontes (Painel).

## Interface web (Plotly)
```bash
python scripts/web_dashboard.py            # gera docs/dashboard_web.html (autocontido)
python app_web.py --port 8000              # regenera + serve em http://localhost:8000
```
Benchmark com filtro por período, evolução 2×3, produtividade, dados e qualidade.
Template em `web/html_template.html`: sidebar 25% + ChartArea 75%, accordions,
scroll, botão de colapso, tabs, grid NxM, temas light/dark (página + relayout Plotly),
filtros da sidebar atuando nas tabelas.

## Atualização trimestral
1. Baixar releases de RI → `data/raw/<EMPRESA>/<TRIM>` (`scripts/collect_web.py` ou aba ETL).
2. Rodar batch ETL (incremental, idempotente por SHA).
3. Revisar aba Qualidade (confiança<0.70, desvios, reconciliação).
4. Painel atualiza sem reconstrução (nova linha em `observation`).
Escala 4→7 empresas e 6→N indicadores por parametrização (`config/*.json`).

## Gestão de fontes públicas (subsistema ETL)
- `config/ri_registry.json` — cadastro das páginas de RI (CRUD); `data/source_downloads.csv` —
  cada arquivo baixado (datetime, fonte, URL, path, SHA, status); `data/ri_registry.csv` — export.
- `python scripts/manage_sources.py list|add|update|on|off|rm|export`
- `python scripts/check_new.py [--download] [--min-score 50] [--id FONTE]` — rotina que
  detecta documentos novos (compara com o CSV; score<50 vai p/ revisão, não baixa).
- Aba **"Fontes Web (CRUD)"** na GUI: grade, adicionar/editar/on-off/remover, verificar e baixar.
- **Painel das fontes (web + GUI)**: site, documento, extensão (.pdf/.xls/.xlsm/.csv/.docx…),
  pasta no sistema, data do download — aba **"Fontes (Painel)"** e seção no HTML.
- **Mapeamento da internet** (`python scripts/map_sources.py`): páginas de RI + sitemap
  das 4 da PoC + BP/Chevron/Exxon (descoberta) → `data/source_map.json`/`.csv` +
  `docs/mapa_fontes.md` (site, título, URL, extensão, período, score, autoridade, via).
  Último mapa real: 469 docs (Equinor 60, Shell 122, TotalEnergies 287).
- **Coleta por formato** (`python scripts/collect_format.py URL | --from-map --ext .pdf ...`):
  `PdfHandler` (%PDF, nº páginas, escaneado?), `SheetHandler` (.xls/xlsx/xlsm/csv,
  sheets, alerta macro), `DocHandler` (docx/doc, conversão isolada p/ .doc),
  `TxtHandler` (encoding em streaming). Sidecar `.meta.json` + log no CSV.
- **Teste trimestral** (`scripts/fetch_quarters.py` + `tests/test_pdf_quarters.py`):
  14 PDFs reais 2023–2026, relatório em `docs/test_pdf_quarters.md`.
- **APIs JSON**: sonda `.model.json` + links `.json` da página (`src/etl/api_probe.py`,
  botão "🔌 Verificar APIs" na GUI); ex.: Shell expõe `/.shelli18n.json` válido.
- Análise de erros do caminho buscar→download→ETL: `docs/etl_caminho_analise.md`.

## Qualidade (evidências)
- Completude (matriz esperada), valores inválidos, desvio histórico por indicador,
  SOURCE_CHANGE (10→20 = WARNING 100%), reconciliação entre fontes, quarentena/DLQ,
  confiança + evidência (trecho/página/planilha) por extração.
