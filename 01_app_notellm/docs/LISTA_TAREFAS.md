# Lista de Tarefas — Melhorias M1 a M6

Status: ✅ implementado e testado · 🔄 em andamento · ⬜ planejado
Validação: `python -m pytest tests/ -q` (155 testes: 153 passam, 2 skip) · harness Node do painel (35 asserções)

## M1 — Aba Fontes: Gestão e Controle de Fontes ✅

| # | Tarefa | Onde | Status |
|---|---|---|---|
| M1.1 | KPIs consolidados na aba (fontes, processadas, com erro, não baixadas, API JSON, arquivo ausente, lacunas, duração do parse) | `SourceController.painel_fontes()` | ✅ |
| M1.2 | Matriz de cobertura **empresa × período** (✓ = existe fonte no trimestre) | `painel_fontes.cobertura` | ✅ |
| M1.3 | Lista de **lacunas**: períodos sem nenhuma fonte (o que falta vs. o que existe) | `painel_fontes.lacunas` | ✅ |
| M1.4 | Integridade: arquivo local ausente, fonte sem URL, sem data de download | `painel_fontes.integridade` | ✅ |
| M1.5 | Filtros dedicados (empresa, status, extensão, origem, só c/ API JSON, só baixadas) + busca textual + contador de resultados | aba Fontes (web) | ✅ |
| M1.6 | Ordenação por coluna (clique no cabeçalho) | `fOrdenar()` | ✅ |
| M1.7 | Renderizar **todas** as fontes (antes cortava em 300 de 798) | `views/web_app.py` | ✅ |
| M1.8 | Ações em lote documentadas (re-processar, integridade, baixar pendentes) | barra da aba | ✅ |
| M1.9 | Painel equivalente na GUI (KPIs + matriz de cobertura) | 2ª aba da GUI | ✅ |
| M1.10 | CRUD completo (create/read/update/delete) com API REST e trilha | `views/web_server.py` | ✅ |
| M1.11 | Export do catálogo em JSON + CSV + DAX para Power BI | `data/sources_catalog.*`, `docs/MEDIDAS_DAX.md` | ✅ |
| M1.12 | Detecção de API/serviço JSON público por fonte (SEC companyfacts, Investidor10) | `workers/api_scan.py` | ✅ |
| M1.13 | Fila de download com deduplicação por SHA-256 e prevention de re-download | `workers/ri_collector.py` | ✅ |
| M1.14 | Alerta de URL quebrada (HTTP 404/403) com re-tentativa automática | `workers/api_scan.checar_url` + `fontes urls` | ✅ |
| M1.15 | Aprovação em lote de fontes com status PENDENTE (seleção múltipla + botão) | `controllers.SourceController.aprovar_lote`, `POST /api/fontes/lote`, `fontes aprovar`, web + GUI | ✅ |

## M2 — Aba Auditoria: Gestão e Controle da Auditoria ✅

| # | Tarefa | Onde | Status |
|---|---|---|---|
| M2.1 | KPIs: alertas totais, fila, abertas, severidade alta/média | `QualityRepository.resumo_auditoria()` | ✅ |
| M2.2 | **Aging** da fila (0–7d, 8–30d, >30d) | `resumo_auditoria.aging` | ✅ |
| M2.3 | Triagem: **aceitar / rejeitar / ignorar** com comentário | `QualityRepository.decidir()` | ✅ |
| M2.4 | Trilha de decisão em `tb_auditoria_decisao` (quem, quando, decisão) | `models/database.py` | ✅ |
| M2.5 | Decisão reflete no status do item (RESOLVIDO / REJEITADO / IGNORADO) | `decidir()` | ✅ |
| M2.6 | Taxa de resolução e contador por tipo de alerta | `resumo_auditoria()` | ✅ |
| M2.7 | Triagem pela web (botões por linha) e pela GUI (3 botões por item) | abas Auditoria | ✅ |
| M2.8 | API `GET/POST /api/auditoria` + CLI `auditoria resumo\|fila\|decidir\|decisoes\|relatorio` | `views/web_server.py`, `app_main.py` | ✅ |
| M2.9 | Reabertura de item decidido (desfazer triagem) | `QualityRepository.reabrir()` | ✅ |
| M2.10 | Relatório de auditoria em PDF com as decisões do período | `workers/relatorio_auditoria.py` | ✅ |
 | M2.11 | Regra automática: alerta crítico repetido >3× escala para prioridade alta | `fila_analise()` | ✅ |

**Relatório de auditoria (M2.10, dados reais):** PDF de 7 páginas com situação da
auditoria, aging, quem decidiu, trilha de decisão do período (com empresa/período/
rubrica resolvidos por JOIN — sem ele o relatório mostraria só "#12 ACEITO") e a
fila no encerramento. Gerado por `app_main.py auditoria relatorio --de --ate`,
pelo botão da aba Auditoria (web e GUI) ou por `GET /api/auditoria?pdf=1`.
Comentário com `<`/`&` é escapado — quebraria o XML do PDF.

**Método por rubrica (M10.7, dados reais):** dívida líquida e CAPEX são **estoque** (saldo acumulado) — Sazonal-Naive pressupõe que o trimestre se repete ano a ano, o que descreve fluxo e não saldo. Antes o sazonal disputava com todo mundo e às vezes vencia por acaso, misturando dois regimes numa série só. Agora o backtesting só considera os métodos do perfil: fluxo (receita, EBITDA, lucro, FCO) disputa os três; estoque disputa nível e tendência. Na base real: 12 séries de estoque, nenhuma com método sazonal.

**Limiar por empresa/rubrica (M7.22):** nova tabela `tb_regra_limiar` guarda a exceção de limiar por empresa e/ou rubrica; a resolução vai do mais específico ao global (empresa+rubrica → rubrica → empresa → padrão do código). Serve porque CAPEX tem outra variabilidade entre empresas que receita, e o outlier cross-sectional da Petrobras era ruído de extração. Exemplo: `python app_main.py qualidade limiar --codigo DRIFT_ZSCORE --limiar 3.0 --rubrica RECEITA_LIQUIDA`. O alerta sai marcado como `calibrado` quando o limiar em vigor não é o global.

**URL quebrada x bloqueio (M1.14):** `fontes urls` varre o catálogo e **separa link morto de bloqueio de automação** — 404/410 é URL removida, 403/401/429 é bloqueio de robô, e a recomendação é outra. 403 não é retentado de propósito: três requisições seguidas só transformam um bloqueio temporário em permanente (é o caso de Chevron e BP no acervo).

**Aprovação em lote (M1.15):** marcar 300 linhas uma a uma era o único jeito de aprovar. Agora a tabela de Fontes tem coluna de seleção (web com checkbox, GUI com célula marcável), botão **marcar PENDENTES** e **aprovar selecionadas**; também existe `fontes aprovar --ids 12,13` e `POST /api/fontes/lote`. O padrão é **só mexer no que está PENDENTE** — "aprovar tudo" sobre um catálogo com 26 pendentes entre 500 linhas mudaria o estado de 474 sem o operador pedir; o que é recusado volta na resposta com o motivo (`status atual PROCESSADO`), e só muda de status com pedido explícito (`--incluir-nao-pendentes` / `apenas_pendentes=false`). O lote muda o **catálogo**, não os números: quem decide se o documento tem dado continuam sendo os parsers do ETL.

**Correção em M2.6 (taxa de resolução):** o denominador era `len(decisoes)`, que é
o número de **tipos** distintos (`GROUP BY decisao`). Com ACEITO=2 e REABERTO=2 dava
2/2 = **100%** enquanto **875** itens seguiam abertos. Agora divide pelo total de
decisões: a base real mostra **50%** (2 de 4). Regressão coberta por teste.

## M3 — Metodologia estatística de projeção (até 3 trimestres) ✅

| # | Tarefa | Onde | Status |
|---|---|---|---|
| M3.1 | Holt-Winters aditivo com tendência **amortecida** (φ=0.85) e sazonalidade k=4 | `workers/forecast.py` | ✅ |
| M3.2 | Sazonal-Naive e Última-Observação como alternativas | `METODOS` | ✅ |
| M3.3 | **Seleção do método por backtesting** (MAE e MAPE na janela de validação) | `backtest()` | ✅ |
| M3.4 | Intervalo de predição 95% que alarga com o horizonte (√h) | `_intervalos()` | ✅ |
| M3.5 | Interpolação de lacunas + desconto de confiança | `_completar()` | ✅ |
| M3.6 | **Poucos dados (2–5 pontos): média da série ± 2 desvios-padrão** | `m_media_2dp()` | ✅ |
| M3.7 | **Um único dado: repete o valor com intervalo ±15%** | `m_repetir_15()` | ✅ |
| M3.8 | Confiança baixa declarada quando < 6 pontos ou σ alto | `projetar()` | ✅ |
| M3.9 | Persistência isolada em `tb_projecao` (nunca sobrescreve fato real) | `ProjectionRepository` | ✅ |
| M3.10 | Aba Projeções no web: KPIs, cenário real×projetado com banda de IC, tabela completa | `views/web_app.py` | ✅ |
| M3.11 | Aba Projeções na GUI (pyqtgraph com FillBetweenItem) | `views/gui_app.py` | ✅ |
| M2.12 | API `GET/POST /api/projecao` + CLI `projecao --horizonte 3` | `views/web_server.py`, `app_main.py` | ✅ |
| M3.13 | Cenários com premissa de preço do Brent / taxa de câmbio | `workers/macro.py::cenarios`, CLI `projecao --cenarios`, web | ✅ |
| M3.14 | Comparar método x MSE em janela maior (rolling-origin) | `workers/rolling_eval.py`, CLI `projecao --avaliar` | ✅ |
| M3.15 | Publicar intervalo em `.eml` junto do gráfico | `workers/mailer.py` (texto + CSV + barra de erro `error_y` no HTML) | ✅ |

**Intervalo no e-mail (M3.15):** o `.eml` publicava o número projetado sem o
intervalo — quem recebia não tinha como saber o quanto ele pode variar, e é o
intervalo que diz se ele serve para decidir. Agora o IC 95% vai nos três lugares:
no **texto** (com método e confiança), no **CSV** (colunas `intervalo_inf` /
`intervalo_sup`) e no **HTML**, como barra de erro `error_y` sobre o gráfico real
com `customdata` no tooltip. O bloco repete "projeção não é fato publicado" para
que a leitura fora do sistema não trate o número como número da Petrobras. Vale
registrar o bug que isso expôs: a vírgula da lista de traces ficou fora do array e
o HTML do e-mail — que é o entregável — abria com erro de sintaxe; agora há teste
que roda `node --check` no JS dos dois caminhos (com e sem projeção).

## M4 — UX dos gráficos (sobreposição/vazamento) ✅

| # | Tarefa | Status |
|---|---|---|
| M4.1 | `contain: layout paint` + `isolation: isolate` na célula (anti-vazamento) | ✅ |
| M4.2 | `Plots.resize` não encolhe o SVG → `relayout({width,height})` medindo a célula | ✅ |
| M4.3 | `width:100%!important` (o Plotly grava largura inline) | ✅ |
| M4.4 | Tela cheia (web + GUI), atalhos `1–9`/`F`/`T`, `⤢ ajustar` | ✅ |
| M4.5 | Tema aplicado aos gráficos por cores explícitas (`relayout('template')` não funciona) | ✅ |
| M4.6 | `setClipToView(True)` na GUI (é método do PlotItem, não do ViewBox) | ✅ |
| M4.7 | Paleta única em `config.PALETA` + traço/marcador por empresa | ✅ |
| M4.8 | Grade NxM com `ResizeObserver` e skip de células ocultas | ✅ |

## M5 — E-mail com gráfico ✅

| # | Tarefa | Status |
|---|---|---|
| M5.1 | Anexos HTML (Plotly interativo) + PNG (Kaleido) + CSV | ✅ |
| M5.2 | Modal web com prévia e `POST /api/email` | ✅ |
| M5.3 | Botão na GUI + CLI (`--enviar`, `--abrir`, `--sem-grafico`) | ✅ |
| M5.4 | Nome amigável do indicador no assunto/HTML/PNG | ✅ |
| M5.5 | Envio real via SMTP com TLS; sem credencial gera `.eml` | ✅ |

## M6 — Robustez do ETL ✅

| # | Tarefa | Status |
|---|---|---|
| M6.1 | Status/duração/erro/extracões por arquivo + histórico de execuções | ✅ |
| M6.2 | `NAO_BAIXADO` ≠ erro (fonte web descoberta não conta como falha) | ✅ |
| M6.3 | CSV com separador `;` detectado (bug: extração silenciosamente vazia) | ✅ |
| M6.4 | API `/api/etl` com resumo, execuções e fontes priorizadas | ✅ |
| M6.5 | Backfill de `extensao`/`pasta_sistema`/`nome_documento` + migração idempotente | ✅ |
| M6.6 | Paralelismo do parse (multiprocessing) por arquivo | `workers/parse_task.py` | ✅ |
| M6.7 | Fila de reprocessamento (retry) para fontes com erro | `run_etl(only_new=True)` | ✅ |

## M7 — Qualidade e Rastreabilidade (gestão e controle) ✅

| # | Tarefa | Onde | Status |
|---|---|---|---|
| M7.1 | **Scorecard de qualidade/confiabilidade**: DQS 0–100 por empresa×período | `workers/quality_score.py` | ✅ |
| M7.2 | Dimensão **Completude** (30%): rubricas esperadas presentes no trimestre | `avaliar_periodo()` | ✅ |
| M7.3 | Dimensão **Plausibilidade** (25%): sinais e outliers impossíveis | `avaliar_periodo()` | ✅ |
| M7.4 | Dimensão **Consistência** (15%): confiança média dos fatos | `avaliar_periodo()` | ✅ |
| M7.5 | Dimensão **Rastreabilidade** (15%): todo fato com `id_fonte` válido | `avaliar_periodo()` | ✅ |
| M7.6 | Dimensão **Tempestividade** (15%): o período é o mais recente disponível | `avaliar_periodo()` | ✅ |
| M7.7 | Classificação automática: CONFIÁVEL ≥80 · REVISAR 60–79 · NÃO CONFIÁVEL <60 | `_classificar()` | ✅ |
| M7.8 | Persistência do scorecard em `tb_qualidade_score` (idempotente) | `salvar_scorecard()` | ✅ |
| M7.9 | **Registros incompletos**: rubricas ausentes por período com % de completude | `fila_analise()` | ✅ |
| M7.10 | **Registros que exigem análise**: fila priorizada P1/P2/P3 com código de motivo | `fila_analise()` | ✅ |
| M7.11 | Desvio **DRIFT_ZSCORE**: valor fora de 2σ da própria série | `detectar_desvios()` | ✅ |
| M7.12 | Desvio **QUEBRA_ESTRUTURAL**: mudança de nível (metade 1 vs metade 2) ≥40% | `detectar_desvios()` | ✅ |
| M7.13 | Desvio **CONTAGEM_PERIODO**: queda >40% de fatos (pipeline quebrado) | `detectar_desvios()` | ✅ |
| M7.14 | Mudança **REVISAO_ENTRE_EXECUCOES**: nº de cargas mudou >30% entre execuções | `_revisao_entre_execucoes()` | ✅ |
| M7.15 | Alerta **ATRASO_TRIMESTRE**: o trimestre mais recente não avançou | `detectar_desvios()` | ✅ |
| M7.16 | **Registro de regras** com limiar/severidade configuráveis (anti-alarme) | `tb_regra_alerta` | ✅ |
| M7.17 | Alertas idempotentes + item na fila de revisão para P1/P2 | `run_quality_score()` | ✅ |
| M7.18 | Aba **Qualidade** no web (KPIs, barras das dimensões, mapa de classificação, fila, regras) | `views/web_app.py` | ✅ |
| M7.19 | Aba **Qualidade** na GUI (KPIs, pyqtgraph, scorecards, fila paginada) | `views/gui_app.py` | ✅ |
| M7.20 | CLI `qualidade rodar\|resumo\|fila\|regras\|historico` + API `/api/qualidade` | `app_main.py`, `views/web_server.py` | ✅ |
| M7.21 | Alertas por tipo e status da fila de revisão no painel | `painel_qualidade()` | ✅ |
| M7.22 | Threshold configurável por empresa/indicador (não só global) | `tb_regra_limiar` + `qualidade limiar --codigo --limiar` | ✅ |
| M7.23 | Scorecard histórico (DQS ao longo do tempo) para ver a evolução da qualidade | `historico_scorecard()` + `tb_qualidade_historico` | ✅ |
| M7.24 | Regra de outlier **cross-sectional** (z-score vs. pares do mesmo trimestre) | `detectar_cross_sectional` em `workers/quality_score.py` | ✅ |
| M7.25 | Alerta automático no e-mail/slack quando entra um P1 | `mailer.alertar_p1` + `email --alerta` | ✅ |
| M7.26 | Contrato de dados (schema check: tipos, nulos, domínios, sinal) por execução | `workers/data_contract.py` | ✅ |
| M7.27 | Score de proveniência (profundidade da cadeia: RI → SEC → derivada) | `workers/provenance.py`, CLI `qualidade proveniencia`, web + GUI | ✅ |

**Leitura atual da base (dados reais):** DQS médio **75,5** em 67 scorecards —
Completude 40,6 · Plausibilidade 98,5 · Consistência 93,8 · Rastreabilidade 100 ·
Tempestividade 64,2. Nenhum scorecard "NÃO CONFIÁVEL"; 16 CONFIÁVEL e 51 REVISAR.
Fila com **458 itens** (60 P1, 398 P3) — o P1 é dominado por
`CONTAGEM_PERIODO` (queda de volume em trimestres SEC parciais) e `ATRASO_TRIMESTRE`.

**Evolução do DQS (M7.23, dados reais):** a série histórica cobre **14 períodos**
(2023Q1→2026Q2) e o DQS médio da base sai de **70,7** para **88,3 (+17,6)**.
Melhores: PETROBRAS 75,4→99,8 (+24,4), SHELL 72,5→95,4 e TOTALENERGIES 69,5→92,4
(+22,9). Pior ainda em REVISAR: EQUINOR 66,5→76,3. A leitura: a completude cresceu
com a carga SEC de 2025Q4 em diante — antes disso os trimestres eram SEC parciais.
Comando: `python app_main.py qualidade historico`.

## M8 — Leitura de PDF (performance e cobertura) ✅ backlog

Benchmark real executado no acervo (`03_Conteiner`, 12 PDFs, DFs Petrobras + BP + Total).
Veredito: **PyMuPDF vira o caminho primário de detecção de tabelas**, mas o
`find_tables()` sozinho **não substitui** o pdfplumber — em `4Q25 Earnings Slides`
ele achou 0 tabelas contra 3 do pdfplumber, e o tempo ficou empatado (1,0x).
Por isso a implementação é PyMuPDF → fallback pdfplumber, e a aceleração real
depende do paralelismo (M6.6) e do cache de texto, não da troca de biblioteca.

| # | Tarefa | Onde | Status |
|---|---|---|---|
| M8.1 | Detecção de tabelas **PyMuPDF** (`page.find_tables`) como caminho primário | `_tables_pymupdf()` | ✅ |
| M8.2 | Fallback **pdfplumber** quando o MuPDF não acha tabela válida | `_tables_pdfplumber()` | ✅ |
| M8.3 | Classificação de PDF por **regex sobre nome normalizado** (acento/espaço/hífen/cifrão) | `workers/naming.py` | ✅ |
| M8.4 | Moeda por regex (`US$`, `R$`, "em dólar", "reais") para priorizar fonte | `moeda_do_nome()` | ✅ |
| M8.5 | Hints de período tolerantes a `1T26`, `3Q25`, `q2-2026`, `2025 3T` | `periodo_do_nome()` | ✅ |
| M8.6 | Modo **incremental** do ETL (`etl --novos` / opção 3 do `.bat`) | `run_etl(only_new=True)` | ✅ |
| M8.13 | Diagnóstico honesto de `SEM_DADOS`: distingue "parser não extraiu" de "fato existente é melhor" | `resumo["descartados"]` | ✅ |
| M8.7 | Teste de regressão do parser de PDF por classe de documento (narrativo vs numérico) | `tests/test_poc.py` | ✅ |
| M8.8 | Avaliar **PDFOxide** (Rust, bindings Python) contra PyMuPDF no acervo | pesquisa | ✅ |
| M8.9 | Avaliar **FlaxPDF** (viewer multithread) como painel de conferência visual | pesquisa | ✅ |
| M8.10 | Avaliar **Speeedy** (RSVP/ORP) e **QuickReaderPDF** (leitura biónica) para revisão de DFs | pesquisa | ✅ |
| M8.14 | PDFOxide como **fallback** de texto quando o MuPDF falha (panic pyo3 tratado) | `page_texts_alternativo()` | ✅ |
| M8.11 | Cache de texto por hash de PDF (evita re-parse em reprocessamento) | `parse_pdf.cache_ler/gravar` + `fontes cache` | ✅ |
| M8.12 | Métrica de PDF no painel de ETL: páginas/seg por documento e tabelas detectadas | `parse_pdf.metricas()` + `n_paginas_lidas`/`n_tabelas` | ✅ |

**Ganho medido do incremental (M8.6):** carga inicial 108 arquivos em **353s**;
`etl --novos` com 1 arquivo novo em **4,3s** — e idempotente (rodar de novo processa 0).

**Cache de texto (M8.11, medido):** o texto extraído do PDF é cacheado por SHA-256 em `data/cache_pdf`, com a profundidade no nome da chave. No DF da Petrobras: **0,488 s na primeira leitura e 0,029 s na segunda — 17× mais rápido, com texto idêntico**. O caso que justifica é o reprocessamento: um `etl` completo relê o acervo inteiro e o texto do arquivo não mudou. O cache nunca muda o resultado (há teste comparando com e sem), sobrevive a arquivo corrompido, respeita teto de 512 MB (sai o mais antigo) e pode ser desligado com `PETRO_CACHE_PDF=0`. `python app_main.py fontes cache` mostra o tamanho.

**Métrica de leitura (M8.12, dados reais):** o parse grava por documento o tamanho
(`n_paginas`), quanto percorreu (`n_paginas_lidas`) e quantas tabelas achou
(`n_tabelas`), e a execução soma em `tb_etl_execucao`. O throughput usa **páginas
lidas ÷ tempo de parse** — nunca o total do arquivo, que inflaria o número, nem o
tempo total da fonte, que mediria o disco em vez do leitor. No acervo: **133 PDFs
medidos, 1.366 páginas lidas, 6,7 pág/s, 1.205 tabelas**. `python app_main.py
fontes metrica` preenche o acervo antigo sem reprocessar (só conta e detecta;
581 fontes sem arquivo local são puladas, não zeradas).

### Benchmark de leitura de PDF (M8.8–M8.10) — 11 PDFs do acervo real

| Biblioteca | Texto (11 docs) | MB/s | Tabelas | Triplas novas | Veredito |
|---|---|---|---|---|---|
| **PyMuPDF 1.28** | **2,2 s** | **5,3** | 31 (≈ pdfplumber) | 6 | **PRINCIPAL** |
| PDFOxide 0.3 (Rust) | 6,2 s | 1,9 | **0** nos DFs Petrobras | 14 | só fallback |
| pdf-inspector 1.25 (Rust) | 2,5 s | 4,6 | — | 11 | não adotado |
| pypdf 6.19 | 16,3 s | 0,7 | — | 15 | 7x mais lento |
| pdfminer.six | 22,8 s | 0,5 | — | 7 | 10x mais lento |

**Conclusão (por que PyMuPDF continua principal):** as libs **não são concorrentes,
são redundantes** — rodando as duas, as extrações do PDFOxide caem nas mesmas
chaves `(rubrica, período)` das do PyMuPDF (35 = 35 extrações, 19 = 19 triplas).
Trocando a biblioteca principal não se ganha fato nenhum e se perde 2,8x de
velocidade e a detecção de tabelas (0 contra 2 nos DFs da Petrobras).
O gargalo de qualidade **não é a biblioteca**: é a heurística de frase
(acumulado 6M versus trimestre) — 0% das extrações por frase bate com a base
para *todas* as libs. Prioridade real: M8.11 (cache) e M6.6 (paralelismo).

- **MinerU** e **PDF-Extract-Kit** foram descartados por análise, sem instalar:
  são modelos de OCR/layout que puxam múltiplos GB de PyTorch, e o acervo já tem
  camada de texto (é por isso que o MuPDF extrai 285 mil caracteres). OCR aqui
  custaria GB para zero ganho.
- **FlaxPDF / Xournal++** são viewers/annotadores, não extratores: servem para
  conferência visual de PDF, não para alimentar o ETL.
- **Speeedy / QuickReaderPDF** são ferramentas de leitura humana (RSVP, biónica):
  não extraem dado estruturado, servem para revisão qualitativa de DFs.
- PDFOxide entrou como **dependência opcional** (fallback de resiliência). Para
  desligar: `set PETRO_NO_ALTERNATIVO=1`.

**Referências externas (avaliadas em M8.8–M8.10):**
1. FlaxPDF — <https://github.com/clbr/flaxpdf>
2. PDFOxide — <https://github.com/yfedoseev/pdf_oxide>
3. Speeedy — <https://github.com/sami-29/speeedy>
4. QuickReaderPDF — <https://github.com/Sbhat92/QuickReaderPDF>

## M9 — Descoberta de informação anunciada ✅

Resposta ao "o que acabou de ser publicado?". O ETL responde *o que eu tenho*; a
descoberta responde *o que foi anunciado e ainda não está no acervo*.

| # | Tarefa | Onde | Status |
|---|---|---|---|
| M9.1 | Descoberta na SEC via `submissions/CIK*.json` (formulário, `reportDate`, `items`, flag XBRL) | `discover_sec()` | ✅ |
| M9.2 | Classificação de **relevância** (resultado × comunicado administrativo) com motivo do descarte | `classificar_relevancia()` | ✅ |
| M9.3 | Janela de 45 dias após o fim do trimestre (evita inflar com 6-K de capa) | `_janela_resultado()` | ✅ |
| M9.4 | Detecção de **lacuna**: o frame `CY20xxQn` não existe no companyfacts | `_lacunas_xbrl()` | ✅ |
| M9.5 | Descoberta em RI (links da página, período pelo nome, filtro de narrativo) | `discover_ri()` | ✅ |
| M9.6 | Registro automático no catálogo como `DESCOBERTO` (aparece na aba Fontes) | `_registrar()` | ✅ |
| M9.7 | Download dos achados para `data/downloads/<EMPRESA>/` com validação de conteúdo | `baixar_achados()` | ✅ |
| M9.8 | Varredura do `data/downloads` pelo ETL (fecha o ciclo descoberta→download→fato) | `scan_container()` | ✅ |
| M9.9 | Parser de HTML de comunicado, reaproveitando a heurística de frase do PDF | `workers/parse_html.py` | ✅ |
| M9.10 | CLI `descoberta` (+ `--site`, `--empresa`, `--baixar`, `--json`) | `app_main.py` | ✅ |
| M9.11 | Painel de descoberta na aba Gestão ETL (Web) | `views/web_app.py` | ✅ |
| M9.15 | **Glossário de indicadores**: definição, unidade, fórmula e sinal (Web + GUI) | `models/glossario.py` | ✅ |
| M9.12 | Ler os **anexos** do arquivamento (`index.json`) e não só o documento principal | `anexos_sec()` | ✅ |
| M9.15 | Incremental também processa o que foi **baixado e nunca processado** (fecha o ciclo) | `run_etl(only_new=True)` | ✅ |
| M9.13 | RI com render de JS (playwright) para Chevron/BP/Petrobras | `workers/jsrender.py` + CLI `fontes render`, `http-fallback` sem playwright | ✅ |
| M9.14 | Alerta automático ("3T26 publicado") no e-mail | `workers/publicacao.py`, CLI `email --publicacao` | ✅ |

**Medição real em 05/10/2026 (alvo 2026Q3):** 9 documentos SEC relevantes para a
Petrobras e **nenhum frame `CY2026Q3`** em nenhuma das 7 empresas — ou seja, o 3T26
ainda **não foi publicado** (Petrobras reporta em novembro). Sem a regra de relevância
o mesmo trimestre retornava 67 itens, sendo a maioria "BATCH FILING", "TOTAL VOTING
RIGHTS" e "IAN TYLER APPOINTED BP CHAIR".

**Limite conhecido (M9.12):** o documento principal de um 6-K da Petrobras é a
**capa**; as demonstrações estão nos anexos, e o número estruturado chega pelo
`companyfacts` (XBRL) — que é justamente o que o M9.4 reporta como lacuna.

## M10 — Melhoria da aba Projeções ✅

| # | Tarefa | Onde | Status |
|---|---|---|---|
| M10.1 | **Verificar se a projeção cobre todos os indicadores/rubricas** — achado: `RUBRICAS_PROJETAveis` era lista fixa de 7 e deixava `FCL`, `DIVIDA_BRUTA` e `DESPESA_OPERACIONAL` sem projeção, sem aviso na tela | `workers/forecast_run.py` | ✅ |
| M10.2 | Projeção **dirigida pelos dados**: toda rubrica de `tb_fato_financeiro` entra, com exclusão sempre justificada em `RUBRICAS_EXCLUIDAS` | `rubricas_do_banco()` | ✅ |
| M10.3 | Corrigir IC95 invertido em série negativa (`REPETIR_15` devolvia `inf > sup` em despesa) | `_intervalos()` | ✅ |
| M10.4 | Tabela de **cobertura** na aba Projeções (Web): rubrica × séries projetadas × fórmula, com aviso quando falta | `views/web_app.py` + `/api/projecao?cobertura=1` | ✅ |
| M10.5 | Teste de que toda rubrica com fato tem projeção (impede voltar à lista fixa) | `tests/test_poc.py` | ✅ |
| M10.6 | Aba Projeções na GUI mostrando a mesma cobertura | `views/gui_app.py` | ✅ |
| M10.7 | Escolher o método por rubrica (ex.: dívida com nível, não com sazonalidade) | `forecast.perfil_rubrica` | ✅ |
| M10.8 | Cenários com Brent/FX e intervalo que responda à covariância dos fatores | `workers/macro.py::sensibilidade` (β + 2ββΣ_cov) | ✅ |
| M10.9 | Rolling-origin: recalcular o histórico de projeções e medir erro real | `workers/rolling_eval.py::erro_real_das_projecoes` | ✅ |
| M10.10 | Aba Projeções: revisar os cálculos da série e corrigir a renderização conforme os filtros (o gráfico sumia e não voltava) | `serie_com_projezcao(horizonte)`, `_prGraf` (purge + catch do react + filtro de horizonte) | ✅ |

**Renderização da aba Projeções (M10.10):** o gráfico "sumia e não aparecia mais"
por dois defeitos combinados. (1) Quando a combinação empresa×rubrica não tinha
projeção, o código trocava o `innerHTML` da div **sem `Plotly.purge`** — o Plotly
deixa estado interno (`_fullLayout`, `_context`) no elemento; o `Plotly.react`
seguinte tentava editar um grafo que não existia mais, a **promise rejeitava** e
ninguém capturava (2) — a div ficava vazia para sempre, sem mensagem. Agora:
`purge` antes de qualquer troca, `Promise.resolve(...).catch()` com fallback
visível ("sem projeção para…", com a dica do botão recalcular) e o **filtro de
horizonte passou a valer** — antes o seletor existia mas não tinha `onchange`,
então trocar 3→1 não redesenhava nada; a série é cortada pelos horizontes reais
gravados (linhas de rodadas anteriores com horizontes misturados não poluem o
gráfico). A nota de cobertura não acumula mais a cada troca de filtro
(`innerHTML +=` duplicava o texto).

**Resultado medido:** antes 7 rubricas / 34 séries / 102 projeções; agora
**10 rubricas / 49 séries / 147 projeções**, com `sem cobertura = 0`.

## M11 — Documentação executiva ✅

| # | Tarefa | Arquivo | Status |
|---|---|---|---|
| M11.1 | Registro detalhado de **todas** as melhorias (o quê, por quê, medição) | `docs/MELHORIAS_IMPLEMENTADAS.md` | ✅ |
| M11.2 | Inventário das **fontes de informação** usadas no ETL (com CIK, tags XBRL e o que não é usado) | `docs/FONTES_DADOS_ETL.md` | ✅ |
| M11.3 | Roteiro de apresentação executiva em 12 tópicos (utilidade → uso → arquitetura → tecnologia → resultados → limites → próximos passos) | `docs/APRESENTACAO_EXECUTIVA.md` | ✅ |
| M11.4 | Deck PDF executivo de 13 páginas gerado do banco (números não divergem do painel) | `workers/deck_pdf.py` | ✅ |
| M11.6 | Apresentação executiva em **PPTX** (23 slides, cores Petrobras, gerada do banco + validador de layout) | `workers/apresentacao_pptx.py` | ✅ |
| M11.7 | Apresentação **visual**: uma tela real do painel por slide (13 slides), capturada por Chrome headless | `workers/screenshots.py` | ✅ |
| M11.5 | Glossário consolidado nos guias de execução | `docs/INSTRUCOES_EXECUCAO.md` | ✅ |

## Ordem sugerida de execução (próximos)
1. M1.15 aprovação em lote de fontes · M3.13 cenários com Brent/FX
2. M3.14 rolling-origin · M10.9 erro real das projeções
3. M7.27 score de proveniência · M9.13 RI com render de JS
4. M3.15 intervalo no .eml · M10.8 covariância dos fatores · M8.7 parser por classe
