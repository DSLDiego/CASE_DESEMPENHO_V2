# PetroAnalytics PoC — Arquitetura MVC-W + ETL (v0 consolidada)

Origem: síntese dos dois históricos (`chat_history/`) + requisitos do case
(`00_requitos_gerais`) + skills (Clean Code/SOLID, Karparaj, BigString).

## 1. Visão geral

```
VIEW (web Plotly / GUI PySide6) ── eventos/filtros ──▶ CONTROLLER
  ▲                                                    ├─▶ MODEL (SQLite + repos + De-Para)
  └─────────────── leitura (matriz benchmark) ─────────┘
                                                          └─▶ WORKERS (scanner, parse_*, SEC, quality, cambio)
```

- **Model**: `models/database.py` (DDL + singleton thread-safe + `migrate()`),
  `models/repositories.py` (Fonte CRUD/DePara/Fato/Quality), `models/depara.py` (regras PT/EN).
- **Workers**: `workers/scanner.py`, `parse_tab.py`, `parse_pdf.py`, `parse_txt.py`,
  `sec_edgar.py`, `ri_collector.py`, `api_scan.py` (detecção de API JSON pública),
  `quality.py` (câmbio PTAX + auditoria), `derived.py`, `etl.py` (orquestrador),
  `deck_pdf.py`, `mailer.py`, `docsgen.py`.
- **Controller**: `controllers/__init__.py` (Pipeline/Analytics/Source/**Mail**).
- **Views**: `views/web_app.py` (Plotly estático, sidebar 25% + workarea 75%, tabs, grid NxM,
  temas), `views/gui_app.py` (QSplitter 25/75, QToolBox, QTabWidget, pyqtgraph) e
  `views/web_server.py` (estáticos + API REST do CRUD de fontes).
- **Entrada**: `app_main.py` (`full|etl|web|gui|sec|fontes|pdf|email|trimestre|status|reset`)
  + `main_vis.bat`.

## 2. Banco (SQLite `data/petro_analytics.db`)

- `tb_fonte_dados`: gestão das fontes (hash SHA-256 UNIQUE anti-duplicidade, status,
  `nome_documento`, `extensao`, `pasta_sistema`, `api_json`, `origem`).
- `tb_depara_rubrica`: De-Para aprendido pelo ETL (empresa, origem → canônica).
- `tb_fato_financeiro`: UNIQUE(empresa, rubrica, periodo); moeda padrão USD; confiança.
- `tb_fato_operacional`: efetivo/produção/FUT + derivados (margens, alavancagem).
- `tb_quality_alerts` + `tb_review_queue`: governança (NEGATIVE, SPIKE, cobertura, confiança).
- Migrações: `MIGRATIONS` aplica `ALTER TABLE ... ADD COLUMN` idempotente em bancos antigos.
- Catálogos espelho: `data/sources_catalog.json` + `.csv` (sincronizados a cada escrita).

## 2.1 Sub-sistema de gestão de fontes (CRUD)

| Operação | CLI | Web (REST) | GUI |
|---|---|---|---|
| Create | `fontes add --empresa .. --url .. --tipo ..` | `POST /api/fontes` | aba *Fontes (CRUD)* |
| Read | `fontes list` / `fontes show <id>` | `GET /api/fontes` | tabela + duplo clique |
| Update | `fontes edit <id> --status .. --api-json ..` | `PUT /api/fontes` | *Salvar* |
| Delete | `fontes del <id>` | `DELETE /api/fontes` | *Excluir* |

- `extensao` e `pasta_sistema` são derivadas do arquivo (evita digitação manual).
- `api_json` guarda o serviço JSON público detectado por `workers/api_scan.py`
  (`fontes api`): SEC `companyfacts` por CIK e Investidor10 (JSON-LD FAQ/`__NEXT_DATA__`).
- Delete preserva fatos: `id_fonte` vira NULL (rastreabilidade sem quebrar o histórico).

## 3. Indicadores (6, inclui EFETIVO_TOTAL obrigatório)

RECEITA_LIQUIDA, EBITDA_AJUSTADO, LUCRO_LIQUIDO, FCO, DIVIDA_LIQUIDA (USD bi) +
EFETIVO_TOTAL (pessoas) + extras operacionais (PRODUCAO_BOED, FCL, LUCRO_BRUTO...).

## 4. ETL

1. `scan_container` registra os 798 arquivos do Container (idempotente por hash).
2. `ParserFactory` por extensão; PDFs grandes/transcripts vão a `NAO_PROCESSADO`.
3. Detecção de período (`2T26→2026Q2`, `Q2 2026`, `2026Q2`...) e escala (milhões→/1000).
4. De-Para dinâmico com cache; carga upsert; status PROCESSADO/SEM_DADOS/ERRO.
5. Auditoria: negativos, spike QoQ >40%, confiança <0.70→review, cobertura ausente→review.
6. SEC EDGAR (`sec [--periodos ...]`): XBRL via CIK como fonte secundária p/ cross-check
   e para completar o histórico 2023-2024 (o Container local traz 2025-2026).
7. Novo trimestre: soltar arquivos na pasta + `python app_main.py etl` (sem rebuild), ou
   `python app_main.py trimestre --novo 2026Q3` (ETL → SEC → derivados → painel → docs).

## 5. Qualidade e rastreabilidade

Toda carga carrega `id_fonte`; painel exibe catálogo + alertas + fila de revisão;
`verificar_integridade()` acusa arquivo sumido do disco; hash impede re-download.

## 6. Views: decisões de UI/UX (anti-sobreposição)

Requisitos queforam medidos em tela (Edge headless 1600x900) e fixados por teste:

| Sintoma | Causa real | Correção |
|---|---|---|
| Gráfico cortado/vazando na célula | Plotly grava a largura **inline** no div; `Plots.resize()` não encolhe | `width:100%!important` + `relayout({width,height})` medindo a célula (`autoFit`) |
| Meia/"média" cortada na borda | `annotation_position="top right"` saía da área do plot | badge no cabeçalho (`#badge-<rub>`) |
| Tooltip/modebar sobre o vizinho | `hoverlayer`/`.modebar` pintam fora do div | `contain:layout paint`, `isolation:isolate`, `overflow:hidden` nas camadas, `displayModeBar:false` |
| Tema escuro só no HTML | `relayout('template', ...)` não é aplicado | cores explícitas (`temaPlot()`/`plotColors()`) + `template:'none'` |
| Grade 2x2 cortada na GUI | `PlotWidget`impõe sizeHint 640x480 | `setMinimumSize(200,170)` + `QSizePolicy.Expanding` |
| Barras gigantes na GUI | auto-range desligado deixava x-range padrão | `setXRange(-0.7, n-0.3)` memorizado em `_fit_x` |

Extras: tela cheia (web + GUI), deep-link `?tema=&tab=&cols=&q=`, atalhos de teclado,
`ResizeObserver` nas células, busca no catálogo, ordenação/zebra nas tabelas,
e-mail com HTML+PNG+CSV, estados vazios explícitos ("sem dados para este indicador").

## 6.1 Envio de e-mail com o gráfico

```
View (botão ✉ / modal)  ──POST /api/email──▶  MailController.enviar()
                                              ├─ preview()  → GET /api/email?rubrica&periodo
                                              └─ workers/mailer.montar_email()
                                                   ├─ .html  gráfico Plotly + tabela (sempre)
                                                   ├─ .png   Kaleido 1800x920 (se disponível)
                                                   └─ .csv   dados + URL da fonte
                                              └─ enviar(): SMTP (--enviar) ou .eml em data/outbox
```
Regras: e-mail inválido → 400 com mensagem; falha de SMTP → 500 com `TypeError: msg`;
sem Kaleido → segue com HTML+CSV (fallback testado). O gráfico enviado usa as cores do
tema (`plotColors()`), então o PNG e o HTML ficam legíveis nos dois temas.

## 6.2 Painel de gestão e controle do ETL

O requisito "informar o que foi processado, o que falhou, com erro/sem erro, com data e
duração" é atendido por duas estructuras novas:

```
tb_fonte_dados  += data_processamento, duracao_ms, n_extracoes, erro
tb_etl_execucao (id, inicio_em, fim_em, duracao_ms, arquivos_processados,
                 extracoes, cargas, pulados_pdf, revisao, erros, status, detalhe)
```

- `workers/etl.py` mede cada arquivo com `time.perf_counter()` e grava o desfecho
  (PROCESSADO / SEM_DADOS / ERRO / NAO_PROCESSADO / NAO_BAIXADO / SEM_PARSER) em
  `registrar_processamento()`; abre e fecha uma linha em `tb_etl_execucao` por execução.
- `SourceController.painel_etl()` devolve `{resumo, execucoes, fontes}` **ordenado por
  prioridade de intervenção** (ERRO → SEM_DADOS → NAO_PROCESSADO → PROCESSADO →
  NAO_BAIXADO) e, dentro do grupo, pelo tempo de processo.
- Web: aba **Gestão ETL** (`GET /api/etl`) com 12 KPIs, filtro por status, busca e o
  histórico de execuções. GUI: 5ª aba com os mesmos KPIs, filtro, busca e histórico.

**Semântica dos status** (importante para não ler errado):

| Status | Significado | Conta como erro? |
|---|---|---|
| PROCESSADO | parseou e gravou ao menos um fato | não |
| SEM_DADOS | parseou, mas nenhum período-alvo foi extraído | não |
| ERRO | falhou o parse (exceção) ou o arquivo local sumiu | **sim** (mensagem em `erro`) |
| NAO_PROCESSADO | PDF pulado por regra (transcript/slides) | não |
| NAO_BAIXADO | fonte web descoberta, ainda sem arquivo local | não |
| SEM_PARSER | extensão sem parser registrado | não |

Um teste garante que fonte web nunca entra em `erros`: o contador de erro é 0 mesmo com
668 fontes não baixadas.

## 7.1 Paleta de cores (fonte única em `config.PALETA`)

A paleta anterior tinha 4 azuis parecidos e as séries temporais ficavam indistinguíveis.
Agora `config.PALETA` (Okabe-Ito + roxo) é consumida pelo web, pela GUI e pelo e-mail, e
`config.ESTILO_SERIE` define **traço + marcador por empresa**:

| Empresa | Cor | Traço | Marcador |
|---|---|---|---|
| PETROBRAS | `#0072B2` | solid (3.5px, spline) | circle |
| SHELL | `#E69F00` | dash | square |
| BP | `#009E73` | dot | diamond |
| CHEVRON | `#CC79A7` | dashdot | triangle-up |
| EXXONMOBIL | `#7B2CBF` | longdash | triangle-down |
| TOTALENERGIES | `#B22222` | dashdot | hexagon |
| EQUINOR | `#66A61E` | longdashdot | star |

Um teste valida a distância mínima de matiz (≥0.08) entre quaisquer duas empresas — foi
ele que reprovou a primeira tentativa (`#0072B2` vs `#56B4E9`, ambos azuis). Barras usam
a mesma paleta com borda branca; séries ficam legíveis também em escala de cinza.

## 7.2 Gestão e Controle de Auditoria (M2) e Projeções (M3)

**Auditoria** — `tb_auditoria_decisao` guarda a trilha de triagem
(`ACEITO`→RESOLVIDO, `REJEITADO`, `IGNORADO) com comentário, autor e data.
`QualityRepository.resumo_auditoria()` devolve alertas por severidade, fila por status,
**aging** (0–7d / 8–30d / >30d), taxa de resolução e ranking por tipo. UI: botões por linha
na web e 3 botões por item na GUI; CLI `auditoria resumo|fila|decidir`; API `GET|POST
/api/auditoria`.

**Projeções** — `workers/forecast.py` decide o método por série:

```
1 dado            -> REPETIR_15        (repete o valor, IC ±15%)
2 a 5 dados       -> MEDIA_2DP         (média da série, IC ±2 desvios-padrão)
6+ dados          -> backtesting entre ULTIMA_OBSERVACAO / SAZONAL_NAIVE /
                     HOLT_WINTERS_DAMPED (Holt aditivo amortecido, sazonalidade k=4);
                     vence a de menor MAE; IC95 = ±1,96·σ·√h (σ dos erros de backtesting)
```
`workers/forecast_run.py` orquestra (lê fatos → projeta → grava), `ProjectionRepository`
persiste em `tb_projecao` com método, intervalo e confiança. Um teste garante que
`tb_fato_financeiro` fica intacto e que `run_forecast` é idempotente.

## 7.3 Qualidade e Rastreabilidade (M7)

```
avaliar_periodo()  -> 5 dimensoes + DQS 0-100 + classificacao  ->  tb_qualidade_score
detectar_desvios() -> DRIFT_ZSCORE | QUEBRA_ESTRUTURAL | CONTAGEM_PERIODO | ATRASO_TRIMESTRE
_revisao_entre_execucoes() -> REVISAO_ENTRE_EXECUCOES (mudaça de dados no tempo)
fila_analise()     -> P1/P2/P3 + codigo de motivo (+ RUBRICA_AUSENTE, SEM_FONTE)
run_quality_score()-> scorecard + alertas idempotentes + itens P1/P2 na fila de revisao
```

| Dimensão | Peso | Como é medida |
|---|---|---|
| Completude | 30% | rubricas financeiras presentes / 10 esperadas no trimestre |
| Plausibilidade | 25% | sinais impossíveis (fato negativo onde não cabe) |
| Consistência | 15% | confiança média dos fatos (normalizada por 0,95) |
| Rastreabilidade | 15% | fatos com `id_fonte` válido |
| Tempestividade | 15% | o período é o mais recente carregado? |

Classificação: `CONFIÁVEL ≥ 80` · `REVISAR 60–79` · `NÃO CONFIÁVEL < 60`. Os limiares das
regras de desvio vivem em `tb_regra_alerta` (calibráveis sem alterar código), o que
evita alarme falso. Estado real da base: DQS médio 75,4 · 67 scorecards · 449 itens de
fila (6 P1) — completude (40,4) é a dimensão que mais derruba a nota, coerente com a
cobertura parcial de rubricas nos trimestres SEC.

## 8. Escala (universo completo)

Adicionar empresa = 1 linha em `COMPANIES` (+CIK); novo indicador = 1 regra em
`depara.py` + entrada em `INDICATORS`. Parsers são genéricos (Strategy/Factory, OCP).
