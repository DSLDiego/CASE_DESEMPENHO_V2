# Apresentação executiva em PowerPoint

Deck de **23 slides** gerado do banco, nas cores da Petrobras
(verde `#006B3F` · amarelo `#FFCD00` · verde-escuro `#00432A`).

```bat
python app_main.py pdf --pptx                          :: docs/APRESENTACAO_PETROBRAS.pptx
python app_main.py pdf --pptx --saida C:\deck.pptx     :: outro caminho
python workers\validar_pptx.py                         :: confere layout e números
python workers\render_pptx.py                          :: converte em PDF/PNG (preview)
```

Gerador: `workers/apresentacao_pptx.py` · Validador: `workers/validar_pptx.py` ·
Prévia: `workers/render_pptx.py`

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