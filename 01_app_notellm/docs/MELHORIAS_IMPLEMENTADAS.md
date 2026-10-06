# Melhorias implementadas — registro detalhado

Documento de referência: o que foi feito, **por que**, como foi validado e o que
mudou em números. Cada item só entra aqui se tiver sido medido ou verificado.

TL;DR: o PoC saiu de "um script que lê PDF" para uma plataforma auditável —
7 empresas, 871 fontes catalogadas, 272 fatos financeiros, DQS 75,5 que subiu
17,6 pontos desde 2023, 147 projeções com intervalo, ETL incremental em segundos,
relatório de auditoria em PDF e um glossário que define cada indicador. Nenhum fato
entra no banco sem fonte, data, unidade e confiança.

---

## 0. Fundação — MVC-W, ETL e rastreabilidade

| Item | Antes | Depois |
|---|---|---|
| Arquitetura | script monolítico | MVC-W: `models/` · `workers/` · `controllers/` · `views/` |
| Banco | CSV | SQLite com 12 tabelas e migrações idempotentes |
| Rastreabilidade | não existia | todo fato tem `id_fonte`, `confianca`, `data_atualizacao` |
| Idempotência | não existia | SHA-256 por arquivo; reexecutar não duplica nem regrada fato |

Tabelas criadas: `tb_fonte_dados`, `tb_depara_rubrica`, `tb_fato_financeiro`,
`tb_fato_operacional`, `tb_quality_alerts`, `tb_review_queue`, `tb_etl_execucao`,
`tb_projecao`, `tb_auditoria_decisao`, `tb_qualidade_score`,
`tb_qualidade_historico` (série do DQS no tempo), `tb_regra_alerta`.

---

## 1. M1 — Gestão e controle de fontes

**Problema:** não dava para saber de onde veio cada número nem corrigir a fonte.

- CRUD completo de fontes em **CLI, Web, GUI e API** (`GET/POST/PUT/DELETE /api/fontes`).
- Campos de proveniência added: documento, extensão, pasta do sistema, API JSON,
  origem, data de processamento, duração em ms, mensagem de erro e nº de extrações.
- Aba **Fontes (gestão)** no painel com filtros dedicados: empresa, status,
  extensão, origem, API JSON, baixadas, busca e ordenação.
- **Renderiza as 798+ fontes** com paginação (antes a tabela era truncada).
- Migração idempotente de `extensao`/`pasta_sistema`/`nome_documento` para bases antigas.
- Auditoria de integridade: fonte web sem arquivo = `NAO_BAIXADO` (**não é erro**);
  arquivo local que sumiu = `ERRO` com caminho na mensagem.

**Ganho:** de "caixa preta" para catálogo auditável de 871 fontes.

## 2. M2 — Gestão e controle da auditoria

- Fila de revisão com **triagem** (aceitar / rejeitar / ignorar) e trilha de decisão
  em `tb_auditoria_decisao` (decisão, comentário, data).
- Reabertura de item decidido (`auditoria reabrir --id 12`): volta para a fila sem
  apagar a decisão anterior, que fica registrada como `REABERTO` na trilha.
- **Relatório de auditoria em PDF (M2.10)** — `workers/relatorio_auditoria.py`, com
  situação da auditoria, aging, quem decidiu, a trilha do período (com
  empresa/período/rubrica resolvidos por JOIN) e a fila no encerramento. Janela
  `--de`/`--ate`; sem elas o relatório cobre a base inteira. Gerado pelo CLI, pelo
  botão da aba Auditoria (web e GUI) ou por `GET /api/auditoria?pdf=1`.
  Comentário com `<`/`&` é escapado — quebraria o XML do PDF.
- **Correção do KPI de taxa de resolução:** o denominador era `len(decisoes)`, que é
  o número de **tipos** distintos (`GROUP BY decisao`) — 2 ACEITO + 2 REABERTO dava
  2/2 = **100%** com **875** itens ainda abertos. Agora divide pelo total de decisões
  (base real: **50%**, 2 de 4) e expõe `total_decisoes` / `itens_resolvidos`.
- API `/api/auditoria` + aba **Auditoria** no painel e na GUI.

## 3. M3 — Projeção estatística (até 3 trimestres)

Metodologia implementada, com escolha de método **por backtesting** (menor MAE na
janela de validação), nunca por suposição:

| Dados da série | Método | Intervalo |
|---|---|---|
| 1 ponto | `REPETIR_15` (repete o valor) | ±15% |
| 2 a 5 pontos | `MEDIA_2DP` (média da série) | ±2 desvios-padrão |
| ≥ 6 pontos | backtesting entre `ULTIMA_OBSERVACAO`, `SAZONAL_NAIVE` (k=4) e `HOLT_WINTERS_DAMPED` (φ=0,85) | IC95 pela dispersão dos erros, alargando com o horizonte |

- Projeção vive em `tb_projecao` e **nunca** entra na matriz comparativa: é sempre
  rotulada como projeção.
- Métricas de erro por série (MAE e MAPE) gravadas para auditoria do método.

## 4. M4 — UX dos gráficos (sobreposição e vazamento)

- `contain: layout paint` + `isolation: isolate` + `width: 100%!important` +
  `ResizeObserver` no Web; `setClipToView(True)` no `PlotItem` do pyqtgraph.
- Modo tela cheia com refit ao fechar; temas; prevenção de vazamento de estado entre
  gráficos (a causa de gráficos "fantasma" ao trocar de aba).
- Paleta centralizada em `config.PALETA` (Okabe-Ito, colorblind-safe) consumida por
  Web, GUI e e-mail — antes eram 4 azuis parecidos e as séries temporais ficavam
  indistinguíveis.

## 5. M5 — E-mail com gráfico

- `.eml` com **HTML interativo + PNG (Kaleido) + CSV**, com a URL da fonte de cada
  empresa no CSV.
- Três caminhos: Web (modal), GUI (botão) e CLI (`app_main.py email`).
- Sem `SMTP_*` no ambiente o app **não tenta enviar**: gera o `.eml` em
  `data/outbox/` para revisão humana (decisão deliberada de segurança).

## 6. M6 — Robustez do ETL

- Status, duração, erro e nº de extrações **por arquivo** + histórico de execuções.
- `parse_csv` passou a detectar `;`, vírgula, tab e pipe (bug: extração silenciosamente vazia).
- **Diagnóstico honesto de `SEM_DADOS`** (achado no teste completo do ETL): antes
  toda fonte sem carga recebia "parser não extraiu periods de {...}", o que era
  falso em metade dos casos. Hoje distingue: 42 não achou número · 16 fora de
  período-alvo · 14 perderam para fato já gravado · 10 foram para revisão.
- Motivo do PDF pulado passou a ser gravado (`PDF pulado: narrativo ('presentation')`);
  antes a coluna Erro ficava vazia e não dava para saber o motivo.

### 6.0 Paralelismo do parse (M6.6)

O parse de PDF e planilha é a parte cara e **não toca no banco**, então foi para
processos separados (`workers/parse_task.py`); a carga continua **sequencial no
processo principal**, na ordem de prioridade das fontes. Isso é o que preserva a
regra "fato bom nunca é rebaixado" e faz o resultado não depender da ordem de
conclusão das tarefas.

| Modo | Tempo (124 arquivos) | Cargas | Revisões | Erros |
|---|---|---|---|---|
| serial (`--jobs 1`) | 169,9 s | 269 | 52 | 0 |
| **4 processos** | **102,3 s** | 269 | 52 | 0 |
| automático (3 nesta máquina) | 103,5 s | 269 | 52 | 0 |

**Ganho de 1,66x** com resultado **idêntico** (mesmas cargas, mesmas revisões,
zero erros). Se o pool morrer, o ETL cai para serial em vez de marcar os arquivos
como ERRO. Uso: `app_main.py etl --jobs 4` (1 = serial).

Bug corrigido no caminho: a duração do arquivo era medida **antes** do parse
(`return (None, tempo(), parser(x)` — Python avalia da esquerda para a direita),
então a coluna `duracao_ms` do painel ficava **zerada**. Agora mede em ms com uma
casa decimal: média 1.711 ms, pior 33,2 s (`2Q26 Supplement Data.pdf`).

### 6.1 ETL incremental (opção 3 do `.bat`)

- `run_etl(only_new=True)`: varre o Container, coleta os ids novos e parseia **só eles**.
- `scan_container` passa a devolver os ids descobertos; downloads da SEC também são
  varridos (`data/downloads/<EMPRESA>/`), fechando o ciclo descoberta → download → fato.
- Idempotente por SHA-256 e, quando o conteúdo é igual, fica o arquivo de nome
  **mais descritivo** (não a cópia) — no Windows a ordenação de `Path` ignora
  maiúsculas e a cópia acabava catalogada.
- **Medido:** carga inicial 108 arquivos em **252 s**; incremental sem mudança
  **4,7 s**; incremental com 1 arquivo novo **2,0 s**.

## 7. M7 — Qualidade e rastreabilidade

- **DQS 0–100** por empresa×período, com 5 dimensões ponderadas:
  completude 30% · plausibilidade 25% · consistência 15% · rastreabilidade 15% ·
  tempestividade 15%.
- Classificação automática: CONFIÁVEL ≥ 80 · REVISAR 60–79 · NÃO CONFIÁVEL < 60.
- Fila priorizada **P1/P2/P3** com código de motivo (458 itens).
- **Escalonamento automático por repetição (M2.11):** um código de alerta que se
  repete mais de 3 vezes sobe um nível (P3→P2→P1). Na base real, o
  `DRIFT_ZSCORE` da BP (39 ocorrências) passou de P2 para P1 — os problemas
  recorrentes ficam no topo em vez de se diluírem na fila.
- **Outlier cross-sectional (M7.24):** regra que compara a empresa com os **pares
  do mesmo trimestre** (z-score ≥ 1,8σ, mínimo de 4 empresas no grupo), enquanto as
  demais comparam com a própria série histórica. Achado real: **CAPEX da Petrobras
  a 0,01 USD bi em 1T26 e 2T26** contra pares em 3–6 bi — defeito de extração na
  aba "Investimentos" da planilha (fonte 2067) isolado automaticamente como P1.
- **Contrato de dados (M7.26):** tipos, obrigatoriedade, domínio e convenção de
  sinal das tabelas de fato, verificados ao fim de cada execução. Aponta a linha
  exata (`tabela.linha.coluna`). Na base real: 393 fatos verificados, 0 violações.
- 9 regras de desvio configuráveis em `tb_regra_alerta`: `DRIFT_ZSCORE`,
  `QUEBRA_ESTRUTURAL`, `CONTAGEM_PERIODO`, `REVISAO_ENTRE_EXECUCOES`,
  `ATRASO_TRIMESTRE`, `BAIXA_CONFIANCA`, `SEM_FONTE`, `RUBRICA_AUSENTE`,
  `OUTLIER_CROSS_SECTIONAL`.
- API `/api/qualidade`, CLI `qualidade`, abas Qualidade no Web e na GUI.
- **Scorecard histórico (M7.23):** `tb_qualidade_score` guarda o **último** estado de
  cada empresa×período (chave única, sobrescrita a cada recálculo), então a evolução
  da qualidade se perdia. `tb_qualidade_historico` grava um ponto por empresa×período
  **quando o DQS muda de verdade** — rerodar sem mudança não cria ponto, senão a
  série seria log de execução e não evolução. Exposto em `historico_scorecard()`,
  no `/api/qualidade`, no CLI (`qualidade historico [--empresa]`) e na aba Qualidade
  (gráfico por período + tabela com a variação de cada trimestre).

**Leitura real da base:** DQS médio **75,5** em 67 scorecards — completude 40,6 ·
plausibilidade 98,5 · consistência 93,8 · rastreabilidade 100 · tempestividade 64,2.
A série histórica (14 períodos, 2023Q1→2026Q2) mostra **70,7 → 88,3 (+17,6)**; a
virada em 2025Q4 (72,5 → 80,5) coincide com a carga SEC completa daquele trimestre —
antes disso os trimestres eram SEC parciais, com completude baixa. Maior evolução:
PETROBRAS 75,4 → 99,8. Ainda em REVISAR: EQUINOR 66,5 → 76,3.

## 8. M8 — Leitura de PDF (performance e cobertura)

Benchmark real no acervo (11 PDFs, 136 no total):

| Biblioteca | Texto | Tabelas | Veredito |
|---|---|---|---|
| **PyMuPDF 1.28** | **2,2 s** | 31 (≈ pdfplumber) | **PRINCIPAL** |
| PDFOxide 0.3 (Rust) | 6,2 s | **0** nos DFs Petrobras | só fallback |
| pdf-inspector (Rust) | 2,5 s | — | não adotado |
| pypdf | 16,3 s | — | 7× mais lento |
| pdfminer.six | 22,8 s | — | 10× mais lento |

**Conclusão medida:** as libs Rust são *redundantes*, não melhores — as extrações
caem nas mesmas chaves `(rubrica, período)` (35 = 35; 19 = 19 triplas). Trocar a
biblioteca principal não ganharia um único fato e custaria 2,8× de velocidade e a
detecção de tabelas. MinerU e PDF-Extract-Kit foram descartados por análise (OCR
com GB de PyTorch para um acervo que já tem camada de texto).

Outras entregas do M8:
- Classificação de PDF por **regex sobre nome normalizado** (`workers/naming.py`):
  acento, espaço duplo, hífen, cifrão, plural e abreviação. Corrigiu o caso em que
  `Transcrição 1T25.pdf` **era parseado** (skip-list sem acento) e em que
  `_Demonstrações Financeiras 1T26  - US$.pdf` não casava na allow-list.
  Resultado no acervo: 84 entram, 52 pulam — **51 dos 52 por serem narrativos**.
- Hints de período tolerantes (`1T26`, `3Q25`, `q2-2026`, `2025 3T`, `fourth-quarter-2025`).
- Moeda por regex (`US$`, `R$`, "em dólar") para priorizar a fonte em dólar — BRL é
  processado por último e nunca sobrescreve USD.
- PDFOxide como **fallback de resiliência** para PDF corrompido, com tratamento de
  pânico pyo3 (`BaseException`), que derrubaria o ETL inteiro num arquivo truncado.
- **Métrica de leitura do PDF (M8.12):** o parse passa a medir **quanto leu**, não só
  o que extraiu. Por documento grava `n_paginas` (tamanho), `n_paginas_lidas` (o que
  o parse percorreu) e `n_tabelas` (detectadas, reaproveitando a detecção que o
  parse já fez — sem segunda passagem); a execução soma em `tb_etl_execucao`.
  A painel mostra por documento e em KPIs: **páginas/seg**, cobertura e tabelas por
  documento, com destaque para o PDF mais demorado.

  Duas decisões para o número não mentir: o throughput divide **páginas lidas pelo
  tempo de parse** (dividir as 37 páginas de um DF lido até a 12ª inflaria o número
  em mais de 3×; dividir pelo tempo total da fonte mediria o disco, não o leitor), e
  **não medido (NULL) é diferente de mediu zero** — as 581 fontes sem arquivo local
  ficam fora da média em vez de puxá-la para baixo.

  **Medido no acervo:** 133 PDFs · 3.743 páginas de arquivo · **1.366 lidas**
  (cobertura 36,5%) · **6,7 pág/s** · **1.205 tabelas** (9,1 por documento).
  `app_main.py fontes metrica` (`workers/pdf_metrics.py`) preenche o acervo já
  processado **sem reprocessar** — só conta e detecta, ~0,2 s por documento, em
  processos paralelos; idempotente e pula o que já tem métrica.

## 9. M9 — Descoberta de informação anunciada

Responde *o que foi anunciado e ainda não está no acervo* — o ETL responde *o que eu tenho*.

- Descoberta na SEC via `submissions/CIK*.json`: formulário, `reportDate`, `items`,
  flag de XBRL numérico. O `reportDate` define o trimestre (30/09 → 2026Q3).
- **Classificação de relevância** com motivo do descarte: sem ela o mesmo trimestre
  devolvia 67 itens, sendo a maioria "BATCH FILING", "TOTAL VOTING RIGHTS" e
  "IAN TYLER APPOINTED BP CHAIR". Hoje são 9 itens relevantes na Petrobras.
- Janela de 45 dias após o fim do trimestre (a SEC usa data de balanço em
  administrativos, o que inflava a Petrobras de 3 para 36 itens).
- **Detecção de lacuna**: se o frame `CY20xxQn` não existe no `companyfacts`, o
  relatório diz que o trimestre foi comunicado mas o número estruturado não foi
  publicado — o sinal de "ainda não dá para fechar o trimestre".
- Achados entram no catálogo como `DESCOBERTO` (aba Fontes); com `--baixar` o arquivo
  cai em `data/downloads/<EMPRESA>/` e o `etl --novos` o transforma em fato.
- Parser de HTML para comunicados 6-K, reaproveitando a heurística de frase do PDF.
- **Anexos do arquivamento** (`index.json` da pasta do filing): o documento principal de
  um 6-K é a capa, e a demonstração vem como anexo. Medido: o 6-K da Shell de 2T26 tem
  **48 anexos, 20 prováveis demonstrações** — incluindo `shel-20260630.htm` (2,1 MB);
  o 10-Q da Chevron tem 70 anexos (41 prováveis). Os maiores (≥ 20 KB) viram fontes
  `SEC:6-K/anexo` e entram no download.
- O incremental agora processa também o que foi **baixado e nunca processado** — sem
  isso o anexo, já catalogado como `DESCOBERTO`, recebia o arquivo e continuava
  fora do parse para sempre (o ciclo não fechava).

**Medição em 05/10/2026 (alvo 2026Q3):** 9 documentos SEC relevantes para a Petrobras
e **nenhum frame `CY2026Q3`** nas 7 empresas — o 3T26 ainda não foi publicado
(Petrobras reporta em novembro). Limite conhecido: Chevron e BP bloqueiam acesso
automatizado (HTTP 403) e as páginas do Petrobras/Equinor são dinâmicas — por isso a
SEC é o canal confiável (é onde a Petrobras protocola o 6-K do resultado).
Os anexos dos arquivamentos passaram a ser lidos; no 2T26 (já publicado) a Shell
tem 48 anexos e a Chevron 70 — os maiores viram fontes e baixam. Eles são
**inline XBRL** (tabela em tag, não frase), então o número estruturado continua
vindo do `companyfacts`.

## 10. M10 — Glossário e cobertura das projeções

**Glossário de indicadores** (`models/glossario.py`): 19 indicadores com código,
nome, categoria, unidade, **definição**, **fórmula** quando derivado (com as
rubricas de que depende), **convenção de sinal** e fonte. 6 têm fórmula:

| Indicador | Unidade | Fórmula |
|---|---|---|
| `FCL` | USD bi | `FCO − CAPEX` |
| `MARGEM_EBITDA` | % | `EBITDA_AJUSTADO ÷ RECEITA_LIQUIDA × 100` |
| `MARGEM_LIQUIDA` | % | `LUCRO_LIQUIDO ÷ RECEITA_LIQUIDA × 100` |
| `DIVIDA_LIQUIDA_EBITDA` | x | `DIVIDA_LIQUIDA ÷ EBITDA_AJUSTADO` |
| `DIVIDEND_YIELD` | % | `dividendos por ação ÷ preço da ação × 100` |
| `P_L` | x | `COTACAO ÷ lucro por ação` |

Os demais são valores publicados pela companhia e o glossário **diz isso** em vez de
inventar uma conta. As convenções de sinal explicadas são as que mais geram dúvida:
`DESPESA_OPERACIONAL` é negativa (custo reduz resultado) e `CAPEX` é positiva (uso
de caixa). Disponível na aba **Glossário** do Web, na aba **Glossário** da GUI e em
`GET /api/glossario`.

**Cobertura das projeções (achado do usuário, confirmado):** `RUBRICAS_PROJETAveis`
era uma lista fixa de 7 rubricas e deixava `FCL`, `DIVIDA_BRUTA` e
`DESPESA_OPERACIONAL` sem projeção, sem aviso na tela. Agora a projeção é
**dirigida pelos dados** (toda rubrica de `tb_fato_financeiro`), com exclusão sempre
justificada, e a aba mostra a tabela de cobertura.

Além disso, o IC95 da `REPETIR_15` era **invertido em séries negativas**
(`inf = v×0,85 > sup = v×1,15` para v < 0) — latente porque nenhuma série negativa
era projetada antes.

**Resultado:** de 7 rubricas / 34 séries / 102 projeções para
**10 rubricas / 49 séries / 147 projeções**, com `sem cobertura = 0`.

---

## 11. Engenharia de interface que vale registrar

- **Apresentação executiva em PPTX** (`workers/apresentacao_pptx.py`, 23 slides nas
  cores da Petrobras): gerada do banco, com `workers/validar_pptx.py` conferindo
  layout (nenhum elemento fora do slide) e a presença dos números — um deck escrito
  à mão divergiria do painel no primeiro trimestre novo, que é o defeito que o
  projeto existe para evitar. Detalhes em `docs/APRESENTACAO_PPTX.md`.
- **Paginação das tabelas grandes** (Fontes, Auditoria, Projeções, ETL, Qualidade):
  as tabelas preenchidas por JS recebiam o paginador antes de terem linhas, então a
  fila de 458 itens renderizava inteira. `paginate()` passou a ser idempotente e há
  `rePaginar()` para as tabelas dinâmicas.
- **Filtro com debounce** e ordenação por coluna nas tabelas de gestão.
- Layout com `clamp()` para não estourar em telas menores.
- Testes de não-sobreposição de gráficos em Web e GUI.

## 12. Bugs reais encontrados pelos testes (e não por leitura de código)

| # | Bug | Como apareceu |
|---|---|---|
| 1 | `Transcrição 1T25.pdf` era **parseado** | teste de classificação de PDF |
| 2 | `R$` lido como **USD** | teste de moeda |
| 3 | `fourth-quarter-2025` não virava período | teste de hints |
| 4 | IC95 invertido em série negativa | teste de projeção |
| 5 | `ZeroDivisionError` na aba Qualidade quando a execução anterior teve `cargas = 0` | suíte completa, após criar o modo incremental |
| 6 | `moeda_origem` recebia um `dict` (argumento posicional errado) | leitura do dado extraído |
| 7 | Lista fixa de rubricas deixando 3 indicadores sem projeção | verificação pedida pelo usuário |
| 8 | Planilha com **uma única coluna de período** não extraía nada | teste de ETL completo |
| 9 | Cópia do arquivo catalogada no lugar do original | teste de ETL completo |
| 10 | ETL sem varredir `data/downloads` (ciclo não fechava) | teste do ciclo descoberta → fato |
| 11 | Pânico pyo3 do PDFOxide derrubaria o ETL em PDF truncado | teste de fallback |
| 12 | Vazamento de stub entre testes (`scan_container` sem monkeypatch) | suíte completa |
| 13 | Dupla extensão `.htm.html` e validação de conteúdo antes de gravar | teste de download |
| 14 | `(20\d{2})` em regex de período rejeitava `3Q26` (ano de 2 dígitos) | teste do parser HTML |
| 15 | Duração do arquivo medida **antes** do parse zerava a coluna `duracao_ms` | teste do painel de ETL |
| 16 | Aba Glossário renderizava fora de posição (2 `</div>` a mais na aba de Qualidade fechavam o container) | inspeção visual + parser de DOM |
| 17 | **Taxa de resolução da auditoria em 100%** com 875 itens abertos (denominador era o nº de *tipos* de decisão) | `auditoria resumo` na base real |
| 18 | `PlotItem.addTextItem` removido no pyqtgraph 0.14 quebrava a GUI com base vazia | teste da aba Projeções sem projeção |
| 19 | Métrica de páginas/seg inflada em 3× (contava o total do arquivo, não o lido) | revisão da métrica antes de documentar |
| 20 | `historico_scorecard(empresa=...)` devolvia a base inteira em vez de série vazia | teste do filtro por empresa |
| 21 | Faixa de KPI com o par (rótulo, valor) invertido: o slide mostrava "empresas comparadas / 7" | renderização do PPTX em PNG |

---

## 13. Estado atual medido

| Métrica | Valor |
|---|---|
| Empresas | 7 (Petrobras, Shell, BP, Chevron, ExxonMobil, TotalEnergies, Equinor) |
| Fontes catalogadas | 871 (183 com arquivo local, 688 apenas com URL de origem) |
| Fatos financeiros | 272 · operacionais 121 |
| Períodos com dado | 14 trimestres (2023Q1 a 2026Q2) |
| Processadas / sem dado / puladas | 26 / 82 / 52 (erros: 0) |
| DQS médio | 75,5 em 67 scorecards |
| Evolução do DQS | 70,7 → 88,3 (+17,6) em 14 períodos · PETROBRAS 75,4 → 99,8 |
| Fila de análise | 458 itens (60 P1, 398 P3) |
| Auditoria | 134 alertas · 877 na fila (875 abertas) · taxa de resolução 50,0% (2 de 4) |
| Projeções | 147 pontos, 49 séries, 10 rubricas, confiança média 0,58 |
| Leitura de PDF | 133 PDFs · 1.366 páginas lidas · 6,7 pág/s · 1.205 tabelas |
| Testes | 114 passando, 2 skips (2023/2024 sem pasta no Container) |
| ETL completo | 252 s serial → **135 s** com 3 processos (1,87x) |
| ETL incremental | 2–5 s (só o que é novo) |
