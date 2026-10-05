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

## 3. Uso diário
| Comando | Efeito |
|---|---|
| `python app_main.py etl` | varre o Container, processa só o novo (hash), recarrega fatos, roda auditoria |
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
| `python app_main.py fontes list` | catálogo de fontes (extensão, pasta do sistema, API JSON, download) |
| `python app_main.py fontes add --empresa BP --url https://... --tipo PDF --caminho data/downloads/x.pdf` | CRUD: cria fonte |
| `python app_main.py fontes edit 1234 --status PROCESSADO --api-json https://...` | CRUD: altera |
| `python app_main.py fontes del 1234` | CRUD: exclui (fatos ficam com `id_fonte` NULL) |
| `python app_main.py fontes api` | detecta serviço JSON público por empresa (SEC companyfacts / Investidor10) |
| `python app_main.py fontes check` | acusa arquivos locais ausentes |
| `python app_main.py sec --periodos 2023Q1 2024Q4` | completa o histórico 4 anos via XBRL |
| `python -m pytest tests/ -q` | suíte de testes (55 testes: 53 passam, 2 skip por Container sem 2023/2024) |

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
   (ou `main_vis.bat` → opção 9).

O que vai anexado: `*.html` (gráfico Plotly interativo + tabela), `*.png` (imagem 1800x920,
via Kaleido) e `*.csv` (dados com a URL da fonte de cada empresa).
Sem `SMTP_HOST/USER/PASS` no ambiente, o app **não tenta enviar**: gera o `.eml` em
`data/outbox/` para você abrir, revisar e enviar. Com as variáveis presentes, `--enviar`
faz o envio real (TLS na porta 587).

## 4. Atualização trimestral (ex.: chegada do 3T26)
1. Copie os novos PDFs/XLSXs para `03_Conteiner\<EMPRESA>\2026_3T\`.
2. Rode `python app_main.py etl` — o scanner ignora os 130 já catalogados (SHA-256) e
   processa só os novos; `PERIODS` em `config.py` pode ganhar `"2026Q3"`.
3. Confira `python app_main.py status` e a aba **Auditoria** do painel
   (spikes esperados no 1º trimestre de cada ano por sazonalidade).
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

Por fonte: status, nº de extrações, **duração** do parse, data de download, data de
processamento e a **mensagem de erro**. No topo, 12 KPIs (fontes, processadas, com erro,
sem dados, não processadas, não baixadas, duração total/média, extrações, última
execução, cargas da última) e abaixo o **histórico de execuções** (início, fim, duração,
arquivos, extrações, cargas, PDFs pulados, revisão, erros).

Filtros: seletor de status + busca por empresa/documento/erro. A tabela vem ordenada por
**prioridade de intervenção** (erro → sem dados → não processado → processado → não
baixado) e, dentro do grupo, pelo tempo de processo — o que exige ação aparece primeiro.

Status possíveis: `PROCESSADO`, `SEM_DADOS`, `ERRO`, `NAO_PROCESSADO`, `NAO_BAIXADO`
(fonte web descoberta e ainda não baixada), `SEM_PARSER`. **Só `ERRO` conta como falha.**

Endpoints usados pelo painel: `GET /api/etl`, `GET /api/fontes`, `GET|POST /api/email`.

## 6. Onde está cada entregável do case- Painel: `data/painel_benchmark.html`
- Catálogo de fontes: `docs/CATALOGO_FONTES.md` + `data/sources_catalog.{json,csv}`
- Evidências de qualidade: `docs/EVIDENCIAS_QUALIDADE.md` (alertas + fila de revisão)
- Premissas/limitações: `docs/PREMISSAS_E_LIMITACOES.md`
- Roteiro 15 min: `docs/ROTEIRO_APRESENTACAO_15MIN.md` · Slides: `docs/SLIDES_APRESENTACAO.md`
- Arquitetura: `docs/DOCUMENTACAO_ARQUITETURA.md` · Planos: `docs/PLANO_TAREFAS_500.md` e
  `docs/PLANO_TAREFAS_2000.md` · DAX: `docs/MEDIDAS_DAX.md`
