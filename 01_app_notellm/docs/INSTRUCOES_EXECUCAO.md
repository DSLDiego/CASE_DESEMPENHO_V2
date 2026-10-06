# Instruções de execução e atualização trimestral

## 1. Pré-requisitos
- Python 3.12+ e `pip install -r requirements.txt`
- Pasta do Container em `C:\Users\diego\Downloads\CASE_DESEMPENHO\03_Conteiner`
  (caminho configurável em `CONTAINER_DIR`, `config.py`)

## 2. Primeira execução (do zero)
```bat
cd C:\Users\diego\Downloads\CASE_DESEMPENHO\01_app_notellm
python app_main.py reset     :: limpa o banco (opcional)
python app_main.py full      :: ETL completo + painel 2T26
```
Ou pelo menu: `main_vis.bat` → opção 1.

### Menu do `main_vis.bat` (12 opções)
| # | O que faz |
|---|---|
| 1 | Pipeline ETL completo + efetivo + painel Web |
| 2 | Gerar e servir o painel Web (http://localhost:8080) |
| **3** | **Refazer ETL: varre o Container e processa SÓ os arquivos novos** (`etl --novos`) |
| **4** | **Descobrir o que foi anunciado (SEC/RI) e ainda falta no acervo** (`descoberta`) |
| 5 | Interface Desktop GUI (PySide6) |
| 6 | Status do banco |
| 7 | Coleta SEC EDGAR (XBRL, requer internet) |
| 8 | Âncoras anuais de efetivo |
| 9 | Coleta web RI + Investidor10 |
| 10 | Exportar slide deck em PDF |
| 11 | Enviar benchmark por e-mail (HTML + PNG + CSV) |
| 12 | Sair |

## 3. Uso diário
| Comando | Efeito |
|---|---|
| `python app_main.py etl` | ETL completo: varre o Container e reprocessa todas as fontes |
| **`python app_main.py etl --novos`** | **incremental: varre o Container e parseia só os arquivos novos** (medido: 353s → 4s) |
| `python app_main.py etl --jobs 4` | paralelismo do parse (medido: 169,9s → 102,3s com resultado idêntico; `1` = serial) |
| `python app_main.py etl --extra 2024Q2` | idem + preenche trimestres históricos (ex.: databooks com série longa) |
| `python app_main.py web --periodo 2026Q2` | regenera `data/painel_benchmark.html` |
| `python app_main.py web --periodo 2026Q2 --serve` | serve o painel em http://localhost:8080 |
| `python app_main.py gui` | abre o desktop PySide6 |
| `python app_main.py sec` | coleta XBRL da SEC EDGAR — só preenche lacunas, nunca sobrescreve o RI (requer internet) |
| `python app_main.py coleta --site all --mercado` | descobre docs nos RIs + snapshot Investidor10 (646 links na última run; `--baixar` p/ download) |
| `python app_main.py derivados` | margens e alavancagem a partir dos fatos (faixa Rentabilidade no painel) |
| `python app_main.py powerbi` | exporta 5 CSVs (`;`) em `data/powerbi/` prontos p/ import no Power BI |
| `python app_main.py pdf --periodo 2026Q2` | slide deck oficial em `docs/SLIDES_APRESENTACAO.pdf` |
| `python app_main.py email --para d@ex.com --rubrica RECEITA_LIQUIDA` | `.eml` em `data/outbox/` com **HTML + PNG + CSV**; `--enviar` usa SMTP_*, `--abrir` abre no cliente de e-mail, `--sem-grafico` só CSV |
| `python app_main.py trimestre --novo 2026Q3` | automação trimestral completa (ETL→SEC→painel→docs) |
| `python app_main.py efetivo` | aplica as 9 âncoras anuais de headcount (idempotente) |
| `python app_main.py status` | resumo + leitura executiva dos 3 trimestres |
| **`python app_main.py descoberta`** | **acha o que foi anunciado (SEC/RI) e ainda não está no acervo** || `python app_main.py fontes list` | catálogo de fontes (extensão, pasta do sistema, API JSON, download) |
| `python app_main.py fontes add --empresa BP --url https://... --tipo PDF --caminho data/downloads/x.pdf` | CRUD: cria fonte |
| `python app_main.py fontes edit 1234 --status PROCESSADO --api-json https://...` | CRUD: altera |
| `python app_main.py fontes del 1234` | CRUD: exclui (fatos ficam com `id_fonte` NULL) |
| `python app_main.py fontes api` | detecta serviço JSON público por empresa (SEC companyfacts / Investidor10) |
| `python app_main.py fontes check` | acusa arquivos locais ausentes |
| `python app_main.py fontes metrica` | mede páginas/tabelas dos PDFs sem métrica (M8.12), sem reprocessar |
| `python app_main.py auditoria resumo\|fila` | KPIs e fila priorizada da auditoria |
| `python app_main.py auditoria decidir --id 4245 --decisao ACEITO` | triagem (aceito/rejeitado/ignorado) |
| `python app_main.py auditoria reabrir --id 4245` | desfaz a triagem (item volta para a fila) |
| `python app_main.py auditoria decisoes --de 2026-07-01 --ate 2026-12-31` | trilha de decisão do período |
| `python app_main.py auditoria relatorio --de ... --ate ...` | relatório de auditoria em PDF (M2.10) |
| `python app_main.py qualidade rodar\|resumo\|fila\|regras\|historico` | scorecard, alertas, fila, limiares e evolução do DQS |
| `python app_main.py sec --periodos 2023Q1 2024Q4` | completa o histórico 4 anos via XBRL |
| `python -m pytest tests/ -q` | suíte de testes (**112 testes: 110 passam, 2 skip** por Container sem 2023/2024) |

## 3.1 CRUD de fontes pela interface
- **Web**: `python app_main.py web --periodo 2026Q2 --serve` → aba **Fontes (CRUD)**:
  formulário (empresa, documento, URL, tipo, pasta, API JSON, status) + botões
  Salvar/Excluir por linha. Persistência via REST: `GET/POST/PUT/DELETE /api/fontes`.
- **GUI**: `python app_main.py gui` → aba **Fontes (CRUD)**: mesmo formulário; duplo clique
  na linha carrega o registro para edição.

## 3.2 Enviar o gráfico por e-mail (3 caminhos)
1. **Web**: `python app_main.py web --periodo 2026Q2 --serve` → aba *Visão executiva* →
   botão **✉ Enviar por e-mail** → modal com **Para**, **Indicador** (rubrica) e a prévia
   das empresas → **Gerar e-mail com o gráfico**. A prévia e o envio usam a API
   (`GET/POST /api/email`).
2. **GUI**: `python app_main.py gui` → botão **✉ Enviar por e-mail** na barra (usa o período
   e a moeda da tela); o caminho do `.eml` aparece na barra de status.
3. **CLI / menu**: `python app_main.py email --para destino@empresa.com --abrir`
   (ou `main_vis.bat` → opção 10).

O que vai anexado: `*.html` (gráfico Plotly interativo + tabela), `*.png` (imagem 1800x920,
via Kaleido) e `*.csv` (dados com a URL da fonte de cada empresa).
Sem `SMTP_HOST/USER/PASS` no ambiente, o app **não tenta enviar**: gera o `.eml` em
`data/outbox/` para você abrir, revisar e enviar. Com as variáveis presentes, `--enviar`
faz o envio real (TLS na porta 587).

## 3.3 Descoberta de informação anunciada (3T26, novo relatório, etc.)

O ETL diz o que já foi carregado. A **descoberta** diz o que foi anunciado e ainda
não está no acervo, em duas frentes:

```bat
python app_main.py descoberta                          :: alvo = trimestre atual
python app_main.py descoberta --periodo 2026Q3 --json  :: saida estruturada
python app_main.py descoberta --site sec --empresa PETROBRAS BP
python app_main.py descoberta --baixar                 :: baixa e prepara p/ o ETL
```

| Saída | Significado |
|---|---|
| `ANUNCIADO` | documento novo do trimestre, já publicado |
| `ANUNCIADO_SEM_XBRL` | comunicado existe, mas o número estruturado ainda não |
| `NADA_ANUNCIADO` | nada publicado para o alvo ainda |
| `! sem frame XBRL CY2026Q3` | **lacuna**: o trimestre não foi publicado em XBRL |
| `x descartado: ...` | o que foi ignorado e por quê (comunicado administrativo) |

Como o documento entra no acervo: `--baixar` grava em
`data/downloads/<EMPRESA>/`, o `scan_container` também varre essa pasta, e então
```bat
python app_main.py etl --novos
```
transforma o que é novo em fato. Sem `--baixar`, o achado fica só catalogado
(status `DESCOBERTO`) e aparece na aba **Fontes** para revisão.

Limites conhecidos: Chevron/BP bloqueiam acesso automatizado (HTTP 403) e as
páginas do Petrobras/Equinor são dinâmicas — por isso a SEC é o canal confiável
(é onde a Petrobras protocola o 6-K com o resultado). A descoberta também lê os
**anexos** do arquivamento (`index.json`), porque o documento principal do 6-K é
só a capa: no 2T26 a Shell tem 48 anexos (20 prováveis demonstrações, o maior com
2,1 MB) e a Chevron tem 70. Esses arquivos são inline XBRL, então o número
estruturado continua vindo do `companyfacts` — é a lacuna que o relatório aponta.

### Contrato de dados (M7.26)
A cada execução do ETL, `workers/data_contract.py` verifica tipos, obrigatoriedade,
domínio e **convenção de sinal** das tabelas de fato, apontando a linha exata.
Resultado na aba **Qualidade** do painel e em `/api/qualidade` (`contrato`).
Estado atual: 393 fatos verificados, 0 violações.

## 3.4 Glossário de indicadores (Web e GUI)

Fonte única de verdade em `models/glossario.py`, consumida pelas duas interfaces e
pela API `GET /api/glossario` (aceita `?q=` para filtrar).

Cada indicador traz: **código**, nome, categoria (Financeiro · Operacional ·
Derivado · Mercado), **unidade**, **definição**, **fórmula** quando é derivado
(com as rubricas de que depende), **convenção de sinal** e a **fonte** de origem.

| Indicador | Unidade | Fórmula |
|---|---|---|
| `FCL` — Fluxo de caixa livre | USD bi | `FCO − CAPEX` |
| `MARGEM_EBITDA` | % | `EBITDA_AJUSTADO ÷ RECEITA_LIQUIDA × 100` |
| `MARGEM_LIQUIDA` | % | `LUCRO_LIQUIDO ÷ RECEITA_LIQUIDA × 100` |
| `DIVIDA_LIQUIDA_EBITDA` | x | `DIVIDA_LIQUIDA ÷ EBITDA_AJUSTADO` |
| `DIVIDEND_YIELD` | % | `dividendos por ação ÷ preço da ação × 100` |
| `P_L` | x | `COTACAO ÷ lucro por ação` |

Os demais (receita, EBITDA, lucro, FCO, CAPEX, dívida, produção, refino, efetivo,
cotação) **não têm fórmula**: são valores publicados pela companhia, e o glossário
diz isso explicitamente em vez de inventar uma conta. As convenções de sinal
explicadas são as que mais geram dúvida — por exemplo `DESPESA_OPERACIONAL` é
**negativa** (custo reduz resultado) e `CAPEX` é **positiva** (uso de caixa).

- **Web**: aba **Glossário** (11ª aba), com cartões, filtro ao vivo e contagem por
  categoria.
- **GUI**: aba **Glossário** (8ª aba), tabela com coluna de fórmula e painel de
  detalhe ao selecionar a linha.

## 4. Atualização trimestral (ex.: chegada do 3T26)
1. Copie os novos PDFs/XLSXs para `03_Conteiner\<EMPRESA>\2026_3T\`.
2. Rode `python app_main.py etl --novos` (ou `main_vis.bat` → **opção 3**) — o scanner
   ignora os já catalogados (SHA-256) e parseia **só os novos**; para reprocessar tudo,
   use `python app_main.py etl` sem `--novos`. `PERIODS` em `config.py` pode ganhar
   `"2026Q3"`.
3. Confira `python app_main.py status` e a aba **Auditoria** do painel
   (spikes esperados no 1º trimestre de cada ano por sazonalidade).

### 4.1 O que o ETL faz com cada PDF (nomes reais do Container)
Nomes no acervo têm acento, espaço duplo, hífen e cifrão
(`_Demonstrações Financeiras 1T26  - US$.pdf`, `Transcrição 1T25.pdf`, `DFS R$ Português.pdf`).
Por isso a decisão é **regex sobre o nome normalizado** (`workers/naming.py`):

| Classe | Exemplos | Entrada no ETL numérico |
|---|---|---|
| Narrativo (sem tabela) | `Transcrição`, `Webcast`, `presentation`, `slides`, `qa-transcript`, `Prepared Remarks`, `Conference Call` | ❌ `NAO_PROCESSADO` |
| Numérico (tem tabela) | `results`, `Demonstrações`, `Desempenho`, `ITR`, `DFS`, `Relatório Fiscal`, `supplemental-info`, `earnings`, `US$`/`R$` | ✅ parseado |

Sem sinal linguístico, decide por tamanho (< 3 MB entra). Também são inferidos
`moeda` (USD tem prioridade, BRL por último para não sobrescrever a fonte em dólar) e o
`período` (`1T26`, `3Q25`, `q2-2026`, `2025 3T`, `fourth-quarter-2025`).

**Tabela do PDF:** PyMuPDF (`find_tables`) é o caminho primário, com fallback para
pdfplumber quando o MuPDF não encontra tabela válida. No acervo os dois concordam
em contagem (31 tabelas em 12 PDFs) e empatam em tempo — a aceleração real depende
de paralelismo e cache (M6.6 / M8.11).

**Benchmark de leitura (11 PDFs do acervo, `docs/LISTA_TAREFAS.md` M8.8):**
PyMuPDF 2,2 s é o mais rápido (PDFOxide 6,2 s · pdf-inspector 2,5 s · pypdf 16,3 s ·
pdfminer 22,8 s). As libs Rust **não** ampliam os dados extraídos — as chaves
`(rubrica, período)` são as mesmas (35 = 35 extrações) — e o PDFOxide ainda erra as
tabelas dos DFs da Petrobras (0 contra 2). Portanto o **PyMuPDF é o principal** e o
PDFOxide fica só como fallback de resiliência (desliga com `PETRO_NO_ALTERNATIVO=1`).
O gargalo de qualidade não é a biblioteca: é a heurística de frase (acumulado 6M
versus trimestre) e o cache/ paralelismo.
4. Regenere o painel: `python app_main.py web --periodo 2026Q3`.
5. Sem rebuild, sem reprocessar o histórico.

## 5. Filtros do painel (client-side, sem servidor)
- **Trimestre** (sidebar): filtra barras, matriz comparativa e leitura executiva
  (2023Q1–2026Q2 — conforme cobertura no banco).
- **Empresas** (sidebar): mostra/oculta séries temporais (também pela legenda).
- **Moeda** USD ↔ BRL (PTAX do trimestre).
- **Tema** claro/escuro — aplicado também aos gráficos (cores explícitas, não só ao HTML).
- Abas: Executiva, Comparação+Matriz, Expandidos, Evolução (6 séries), Efetivo,
  Fontes (CRUD), **Gestão ETL**, Auditoria.

## 5.1 UX dos visualizadores
| Recurso | Web | GUI |
|---|---|---|
| Tela cheia de um gráfico | duplo clique no gráfico (ou `F`, ou botão `⤢ ajustar` + `Esc`) | duplo clique no gráfico (abre diálogo 1100x680, `Esc` fecha) |
| Atalhos | `1`–`8` abas · `F` tela cheia · `T` tema | duplo clique / botões da barra |
| Gráfico ocupa todo o espaço | `autoFit()` mede a célula e manda `width/height` explícitos (o `Plotly.resize` sozinho **não encolhe** o SVG) | `setMinimumSize(200,170)` + `_reajustar_todos()` ao redimensionar |
| Anti-sobreposição | `contain:layout paint` + `isolation:isolate` na célula, `hoverlayer/modebar` com `overflow:hidden`, modebar desligado | `setClipToView(True)` (PlotItem), sem menu, `enableAutoRange(False)` |
| Layout compartilhável | `?tema=dark&tab=3&cols=4&q=2026Q2` (deep-link; a URL é atualizada a cada mudança) | — |
| Enviar por e-mail | botão ✉ abre modal (prévia + gera `.eml` com HTML+PNG+CSV) e `app_main.py email` | botão ✉ na barra (gera `.eml` com HTML+PNG+CSV) |
| Busca no catálogo | 🔎 nas abas Fontes e Gestão ETL | busca na aba Gestão ETL |
| Cores das séries | `config.PALETA` + traço/marcador por empresa (`config.ESTILO_SERIE`) | mesma paleta (barras por empresa) |

## 5.2 Painel de gestão do ETL (o que rodou, o que falhou, quanto tempo)
- **Web**: `python app_main.py web --periodo 2026Q2 --serve` → aba **Gestão ETL** (atalho `7`).
- **GUI**: `python app_main.py gui` → 5ª aba **Gestão ETL**.

Por fonte: status, nº de extrações, **duração** do parse, **páginas/tabelas do PDF**
(M8.12), data de download, data de processamento e a **mensagem de erro**. No topo, 12
KPIs (fontes, processadas, com erro, sem dados, não processadas, não baixadas, duração
total/média, extrações, última execução, cargas da última) e uma **segunda faixa de
métrica de leitura do PDF**: PDFs medidos, páginas do arquivo, páginas lidas,
cobertura, tabelas detectadas, **páginas/seg**, tabelas por documento e o PDF mais
demorado. Abaixo, o **histórico de execuções** (início, fim, duração, arquivos,
extrações, cargas, PDFs pulados, revisão, erros, páginas, tabelas).

O throughput divide **páginas lidas pelo tempo de parse** — não o total do arquivo
(37 páginas num DF lido até a 12ª inflaria o número) nem o tempo total da fonte
(que mediria o disco). Documento sem métrica (CSV/XLSX) fica **fora** da média: não
medido ≠ mediu zero. Para preencher o acervo já processado:
`python app_main.py fontes metrica`.

Filtros: seletor de status + busca por empresa/documento/erro. A tabela vem ordenada por
**prioridade de intervenção** (erro → sem dados → não processado → processado → não
baixado) e, dentro do grupo, pelo tempo de processo — o que exige ação aparece primeiro.

Status possíveis: `PROCESSADO`, `SEM_DADOS`, `ERRO`, `NAO_PROCESSADO`, `NAO_BAIXADO`
(fonte web descoberta e ainda não baixada), `SEM_PARSER`. **Só `ERRO` conta como falha.**

Endpoints usados pelo painel: `GET /api/etl`, `GET /api/fontes`, `GET|POST /api/email`,
`GET|POST /api/projecao`, `GET|POST /api/auditoria`.

## 5.3 Projeções estatísticas (até 3 trimestres)
- **Web**: aba **Projeções** (atalho `9`) · **GUI**: aba **Projeções** · **CLI**:
  `python app_main.py projecao --horizonte 3 [--empresa PETROBRAS] [--rubrica RECEITA_LIQUIDA]`

Método por série (empresa × rubrica), na ordem de decisão:

| Situação | Método | Intervalo | Confiança |
|---|---|---|---|
| **1 único dado** | `REPETIR_15` — repete o valor | **±15%** do valor | 0,25 |
| **2 a 5 dados** | `MEDIA_2DP` — média da série | **média ± 2 desvios-padrão** | 0,35–0,50 |
| **6+ dados** | `ULTIMA_OBSERVACAO`, `SAZONAL_NAIVE` ou `HOLT_WINTERS_DAMPED`, escolhido por **backtesting** (menor MAE) | IC95 = erro ± 1,96·σ·√h (alarga com o horizonte) | 0,05–0,95 |

Projeção **nunca** vira fato: fica em `tb_projecao`, não entra na matriz comparativa e
aparece sempre rotulada. Lacunas na série são interpoladas e descontam confiança.

## 5.4 Triagem da auditoria
Web (botões por linha) ou CLI: `python app_main.py auditoria decidir --id 4245 --decisao aceito
Para **desfazer** uma triagem (o item volta para a fila e a decisão anterior fica registrada na trilha): `python app_main.py auditoria reabrir --id 4245`.
--comentario "conferido no release"`. Cada decisão fica em `tb_auditoria_decisao` e muda o
status do item para RESOLVIDO / REJEITADO / IGNORADO.

Para **conferir o que foi decidido no período**:

```bat
python app_main.py auditoria decisoes --de 2026-07-01 --ate 2026-12-31
python app_main.py auditoria relatorio --de 2026-07-01 --ate 2026-12-31 --saida docs\RELATORIO_AUDITORIA.pdf
```

O relatório em PDF traz situação da auditoria, aging, quem decidiu, a trilha do
período (com empresa/período/rubrica do item auditado) e a fila no encerramento.
Sem `--de`/`--ate` ele cobre tudo o que existe na base. Também dá para gerar pela
aba Auditoria (botão **📄 gerar relatório PDF**) ou por `GET /api/auditoria?pdf=1`.

## 5.6 Qualidade e Rastreabilidade (gestão e controle)
- **Web**: aba **Qualidade** (atalho `0`) · **GUI**: aba **Qualidade** ·
  **CLI**: `python app_main.py qualidade rodar|resumo|fila|regras|historico`

Cada **empresa × trimestre** recebe um **DQS 0–100** com cinco dimensões ponderadas:
Completude 30%, Plausibilidade 25%, Consistência 15%, Rastreabilidade 15% (todo fato com
`id_fonte`) e Tempestividade 15%. Classificação: **CONFIÁVEL ≥ 80** · REVISAR 60–79 ·
NÃO CONFIÁVEL < 60.

**Fila de análise priorizada** (registros incompletos ou que exigem análise):
P1 urgente · P2 revisar · P3 completar, sempre com o código do motivo.

**Evolução do DQS no tempo (M7.23):** `tb_qualidade_score` guarda só o último estado
de cada empresa × trimestre. `tb_qualidade_historico` grava a série, um ponto por
empresa × período **quando o DQS muda** — rerodar sem mudança não cria ponto, senão a
série viraria log de execução. Ver com `python app_main.py qualidade historico`
(ou `--empresa PETROBRAS`); no painel é o gráfico e a tabela logo abaixo das
dimensões.

**Regras de alerta de desvio histórico / mudança no tempo** (limiares em `tb_regra_alerta`):

| Código | O que detecta | Severidade |
|---|---|---|
| `ATRASO_TRIMESTRE` | último trimestre carregado não avançou | HIGH |
| `CONTAGEM_PERIODO` | volume de fatos caiu >40% vs. período anterior | HIGH |
| `SEM_FONTE` | fato sem vínculo de fonte (rastreabilidade quebrada) | HIGH |
| `DRIFT_ZSCORE` | valor a 2σ ou mais da própria distribuição | MEDIUM |
| `QUEBRA_ESTRUTURAL` | mudança de nível ≥40% na série | MEDIUM |
| `REVISAO_ENTRE_EXECUCOES` | nº de cargas mudou >30% entre execuções | MEDIUM |
| `BAIXA_CONFIANCA` | confiança < 0,70 | MEDIUM |
| `RUBRICA_AUSENTE` | rubrica esperada sem fato no período | LOW |

Rodar duas vezes não duplica alertas (idempotente por tabela+tipo+descrição).

## 5.7 Lista de tarefas
`docs/LISTA_TAREFAS.md` — M1 (Fontes), M2 (Auditoria), M3 (Projeções), M4 (UX),
M5 (E-mail), M6 (ETL) com ✅/⬜ e a ordem sugerida de execução.

## 6. Onde está cada entregável do case- Painel: `data/painel_benchmark.html`
- Catálogo de fontes: `docs/CATALOGO_FONTES.md` + `data/sources_catalog.{json,csv}`
- Evidências de qualidade: `docs/EVIDENCIAS_QUALIDADE.md` (alertas + fila de revisão)
- Premissas/limitações: `docs/PREMISSAS_E_LIMITACOES.md`
- Roteiro 15 min: `docs/ROTEIRO_APRESENTACAO_15MIN.md` · Slides: `docs/SLIDES_APRESENTACAO.md`
- Arquitetura: `docs/DOCUMENTACAO_ARQUITETURA.md` · Planos: `docs/PLANO_TAREFAS_500.md` e
  `docs/PLANO_TAREFAS_2000.md` · DAX: `docs/MEDIDAS_DAX.md`
