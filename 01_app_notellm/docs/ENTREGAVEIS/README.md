# Entregáveis — PetroAnalytics PoC

Benchmark Petrobras vs pares · 7 empresas · MVC-W + SQLite + Python.
Gerado em 06/10/2026 contra a base real (`data/petro_analytics.db`).

| # | Entregável | Arquivo | Como ver |
|---|---|---|---|
| 1 | **Painel + fotos de todas as abas** | `1_PAINEL_E_IMAGENS/` | `painel_benchmark.html` (abrir no navegador) e 11 PNGs |
| 2 | **Catálogo das fontes de informação** | `2_CATALOGO_DE_FONTES.csv` + [`../FONTES_DADOS_ETL.md`](../FONTES_DADOS_ETL.md) | 871 fontes com empresa, tipo, hash, origem, URL e status |
| 3 | **Instruções de execução/atualização** | `3_INSTRUCOES_DE_EXECUCAO.md` | guia rápido; completo em [`../INSTRUCOES_EXECUCAO.md`](../INSTRUCOES_EXECUCAO.md) |
| 4 | **Evidências dos controles de qualidade** | `4_EVIDENCIAS_DE_QUALIDADE.md` | DQS, contrato de dados, fila priorizada, testes |
| 5 | **Premissas, decisões e limitações** | `5_PREMISSAS_DECISOES_LIMITACOES.md` | 5.1 tecnológicas · 5.2 financeiras |
| 6 | **Apresentação da construção (entrevista, 15 min)** | `6_APRESENTACAO_ENTREVISTA_15MIN.md` | roteiro por blocos, com as perguntas e as respostas |
| 7 | **Alertas cross-sectional (análise fora da curva)** | `7_ALERTAS_CROSS_SECTIONAL.md` | os 10 achados e a causa do CAPEX da Petrobras |
| 8 | **Relatório de auditoria em PDF** | `RELATORIO_AUDITORIA.pdf` | gerado do banco: situação, aging, quem decidiu e a trilha do período |

Complementares: [`../MELHORIAS_IMPLEMENTADAS.md`](../MELHORIAS_IMPLEMENTADAS.md) ·
[`../APRESENTACAO_EXECUTIVA.md`](../APRESENTACAO_EXECUTIVA.md) ·
[`../SLIDES_APRESENTACAO.pdf`](../SLIDES_APRESENTACAO.pdf) ·
[`../LISTA_TAREFAS.md`](../LISTA_TAREFAS.md)

## 1. Fotos do painel

`1_PAINEL_E_IMAGENS/` com uma imagem por aba:

| Arquivo | Aba |
|---|---|
| `aba_00_visao_executiva.png` | Visão executiva (leitura + gráficos) |
| `aba_01_comparação.png` | Comparação (matriz entre empresas) |
| `aba_02_expandidos.png` | Indicadores expandidos |
| `aba_03_evolucao_historica.png` | Evolução histórica |
| `aba_04_efetivo.png` | Efetivo (âncora anual) |
| `aba_05_fontes_gestão.png` | Fontes (gestão e CRUD) |
| `aba_06_gestão_etl.png` | Gestão ETL (métrica de leitura do PDF + descoberta) |
| `aba_07_auditoria.png` | Auditoria (fila priorizada, triagem e relatório em PDF) |
| `aba_08_projeções.png` | Projeções (real × projetado + cobertura) |
| `aba_09_qualidade.png` | Qualidade (DQS, evolução no tempo, contrato, regras) |
| `aba_10_glossario.png` | Glossário de indicadores |

O painel abre **offline**: `painel_benchmark.html` é um arquivo único com os gráficos
embutidos. Para versão interativa com dados ao vivo:
`python app_main.py web --periodo 2026Q2 --serve` → http://localhost:8080

## Números da entrega

| Métrica | Valor |
|---|---|
| Empresas / períodos | 7 · 14 trimestres (2023Q1–2026Q2) |
| Fontes catalogadas | 871 (183 com arquivo local) |
| Fatos | 272 financeiros + 121 operacionais |
| DQS médio | 75,5 (67 scorecards) · rastreabilidade 100,0 |
| Evolução do DQS (M7.23) | 70,7 → 88,3 (+17,6) em 14 períodos · PETROBRAS 75,4 → 99,8 |
| Fila priorizada | 458 itens (60 P1, 398 P3) |
| Auditoria | 134 alertas · 877 na fila (875 abertas) · taxa de resolução 50,0 % |
| Projeções | 147 pontos · 49 séries · **10 de 10 rubricas** |
| ETL completo / incremental | 135 s (3 processos) / 2–5 s |
| Leitura de PDF (M8.12) | 133 PDFs · 1.366 páginas lidas · 6,7 pág/s · 1.205 tabelas |
| Testes | **110 passam**, 2 skips |
| Erros de carga | 0 · contrato de dados: 393 fatos verificados, 0 violações |

## Como reproduzir tudo

```bat
python -m pytest tests/ -q                        :: 110 passam
python app_main.py etl --jobs 4                    :: ETL completo (102s)
python app_main.py etl --novos                     :: incremental (2-5s)
python app_main.py fontes metrica                  :: mede páginas/tabelas do acervo
python app_main.py qualidade rodar                 :: scorecard + alertas + contrato
python app_main.py qualidade historico             :: evolução do DQS por período/empresa
python app_main.py auditoria relatorio --de 2025-01-01 --ate 2026-12-31
python app_main.py projecao                        :: 147 projeções
python app_main.py web --periodo 2026Q2 --serve    :: painel em http://localhost:8080
python app_main.py descoberta                      :: o que foi anunciado (SEC/RI)
python app_main.py pdf --periodo 2026Q2            :: deck executivo em PDF
```