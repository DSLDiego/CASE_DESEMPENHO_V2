# Duas apresentações

| Arquivo | Tipo | Slides | Quando usar |
|---|---|---|---|
| APRESENTACAO_PETROBRAS.pptx | **conteúdo** | 23 | quando o número, o método e a decisão importam mais que a tela |
| APRESENTACAO_VISUAL.pptx | **visual** | 13 | quando mostrar o produto rodando importa mais que ler sobre ele |

`at
python app_main.py pdf --pptx                    :: deck de conteúdo (23 slides)
python app_main.py pdf --visual                  :: deck visual (13 slides)
python workers\screenshots.py                    :: recaptura as telas do painel
python workers\validar_pptx.py                   :: confere layout e números dos dois
python workers\render_pptx.py <arquivo.pptx>    :: converte em PDF/PNG (preview)
`

Ambos são **gerados do banco**: um slide escrito à mão divergiria do painel no
primeiro trimestre novo, que é exatamente o defeito que o projeto existe para evitar.

## O deck visual

Uma **tela real do produto** por slide, com legenda curta do que ela prova.
As imagens vêm de workers/screenshots.py — Chrome headless contra o painel
servindo de verdade, --headless --screenshot. Um mock-up desenhado à mão
provaria o quê? Nada.

Capa · 11 telas · fecho com grade 3×3 das telas.

| Tela | Slide | O que prova |
|---|---|---|
| ba_00_visao_executiva | 1 | o painel abre em uma pergunta, não numa lista de tabelas |
| ba_01_comparacao | 2 | 7 empresas numa matriz, mesma unidade |
| ba_03_evolucao_historica | 3 | evolução é resposta, não foto de hoje |
| ba_02_expandidos | 4 | indicador derivado declara de quais rubricas depende |
| ba_04_efetivo | 5 | efetivo é a âncora obrigatória do setor |
| ba_08_projecoes | 6 | projeção separada do fato e sempre rotulada |
| ba_06_gestao_etl | 7 | **M8.12** — o parser não é caixa-preta: páginas lidas, tabelas, pág/s |
| ba_09_qualidade | 8 | **M7.23** — DQS subiu, caiu ou estagnou, e quem mais mudou |
| ba_07_auditoria | 9 | **M2** — triagem com trilha de decisão |
| ba_05_fontes_gestao | 10 | catálogo com origem, hash e status + CRUD |
| ba_10_glossario | 11 | por que a despesa é negativa e o CAPEX positivo |

## Capturar as telas

`at
python workers\screenshots.py
`

Sobe o painel com --serve numa porta livre, espera /api/etl responder e
captura cada aba. **Precisa do servidor**: Gestão ETL, Auditoria e Qualidade
carregam por etch, e no HTML estático sairiam vazias — o print mostraria um
produto quebrado.

Dois cuidados que só apareceram no print:

- **Altura por aba.** O conteúdo novo das três abas de governança fica *abaixo da
  dobra*: numa janela de 1000px o print sai bonito e não mostra nem a métrica de
  PDF, nem a evolução do DQS. As abas 6/7/8/9 usam 1450–2350px.
- **--hide-scrollbars obrigatório.** Com a barra visível, a última coluna da
  tabela some do print (o recorte é da largura da barra) — na Auditoria o
  status saía cortado, sem ninguém perceber.

As abas 6 e 9 têm **recorte vertical**: o print mostra a faixa de métrica /
o gráfico e a tabela da feature, e larga a lista de 67 scorecards, que é ruído
para a apresentação. É o mesmo corte que o olho faria.

## O deck de conteúdo

23 slides: capa, roteiro, problema, utilidade, uso, cadeia, arquitetura,
tecnologia, benchmark de PDF, resultados, acervo, DQS, evolução no tempo, fila,
alerta cross-sectional, projeção, governança, auditoria, glossário, testes,
limites, próximos passos e fecho. Detalhes na tabela completa abaixo.

## Por que o deck é gerado e não escrito à mão

Todos os números vêm de `_numeros()`, que lê `data/petro_analytics.db`. Um slide
escrito à mão divergiria do painel no primeiro trimestre novo — exatamente o defeito
que o projeto existe para evitar. Se o banco mudar, o deck muda junto.

`workers/validar_pptx.py` confere duas coisas que a geração não garante sozinha:

| Checagem | O que pega |
|---|---|
| Nenhum elemento fora da área do slide | texto estourando a margem quando o número cresce |
| Números do banco presentes no deck | slide que "conta" uma métrica que o banco não tem |
| Cor da paleta presente no XML do .pptx | deck que perde a identidade visual (o XML é **zip**, então a busca é no descomprimido) |

`render_pptx.py` usa o LibreOffice/Office instalado para gerar um PDF e PNG de cada
slide — python-pptx escreve XML, não renderiza, então é o conversor que diz se o
layout fica de pé.

## Roteiro dos 23 slides

| # | Slide | Mensagem |
|---|---|---|
| 1 | Capa | PetroAnalytics · 7 empresas · 14 trimestres · DQS e projeções |
| 2 | Roteiro | 12 blocos, do problema aos próximos passos |
| 3 | O problema | 7 formatos incompatíveis; número sem procedência não vai para decisão |
| 4 | A utilidade | comparabilidade · descoberta · confiança · projeção · governança |
| 5 | Quem usa e como usa | 5 passos, cada um com o comando e quem faz |
| 6 | A cadeia | 11 etapas e as 3 garantias que sustentam o resto |
| 7 | Arquitetura | MVC-W: Model, Worker, Controller, View |
| 8 | Tecnologia | escolha medida — e o que foi descartado por benchmark |
| 9 | Benchmark de PDF | PyMuPDF principal; libs Rust não adotadas; métrica de leitura |
| 10 | Resultados medidos | matriz do último trimestre em USD bi |
| 11 | Estado do acervo | 871 fontes e o status de cada tipo de documento |
| 12 | O DQS | 5 dimensões ponderadas e o que cada uma diz |
| 13 | Evolução no tempo | DQS 70,7 → 88,3 em 14 períodos, por empresa |
| 14 | Fila priorizada | P1/P2/P3, escalonamento por repetição, contrato de dados |
| 15 | Alerta cross-sectional | z-score vs. pares e o CAPEX da Petrobras a 0,01 |
| 16 | Projeção estatística | método por backtesting, IC95, cobertura 10/10 |
| 17 | Governança | SEC, lacuna de XBRL, canais primários bloqueados |
| 18 | Auditoria e PDF | trilha de decisão e o relatório do período |
| 19 | Glossário | unidade e convenção de sinal de cada indicador |
| 20 | O que os testes acharam | 20 bugs reais, com o de mais honesto em destaque |
| 21 | Limites assumidos | 8 limites e como cada um está registrado |
| 22 | Próximos passos | anexos SEC, rolling-origin, Brent/FX, cache, RI com JS |
| 23 | Fecho | "não é o dashboard, é a cadeia de decisões" |

## Ajustes finos que só aparecem na renderização

Cada um destes foi encontrado abrindo o PNG do slide, não lendo o código:

- **Tupla da KPI na ordem (valor, rótulo)** — invertida, o slide mostrava
  "empresas comparadas / 7": o número virava legenda. A `_kpis` agora **recusa**
  uma string no lugar do valor, e há teste para isso.
- **Rótulo com caixa própria, mais baixa que o valor** — com a mesma altura, um
  rótulo de duas linhas cresce para dentro da caixa de cima e some atrás do número.
- **Títulos de uma linha só** — o "DQS médio da base: … em 14 períodos" quebrava
  em duas linhas e cobria o parágrafo explicativo logo abaixo.
- **Gráfico de DQS na largura toda** — na metade da largura cabiam só 7 das 14
  barras; a tabela de empresas foi para baixo do gráfico.
- **Tabela de projeção a 0,55in de linha** — a 0,62in ela invadia o texto à direita.
- **CAPEX com 2 casas decimais** — a 1 casa o valor do defeito de extração (0,01)
  virava "0,0", que é exatamente o número que o slide seguinte denuncia.

## Preview

`render_pptx.py` cria `docs/_preview_pptx/` com o PDF e um PNG de cada slide (~1,5 MB).
É material de conferência, não entregável: **não está versionado** e pode ser apagado
a qualquer momento — `python workers\render_pptx.py` recria.