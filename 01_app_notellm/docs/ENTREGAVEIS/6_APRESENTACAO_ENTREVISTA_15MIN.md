# 6. Apresentação para a entrevista (15 minutos)

**Como usar este documento:** é o roteiro do que **contei durante a construção** — não
uma descrição do produto. Cada bloco tem o tempo, o que dizer e **a pergunta que
espero que me façam** (com a resposta pronta).

Deck visual de apoio: `../SLIDES_APRESENTACAO.pdf` (13 páginas).
Tela para demonstrração ao vivo: `1_PAINEL_E_IMAGENS/painel_benchmark.html`.

---

## Bloco 1 — O problema que me recebeu (1 min)

> "Sete companhias publicam o mesmo fato em PDF com layout, planilha com três
> separadores, release em inglês, número em dólar ou em real. Comparar Petrobras com
> seis pares exige planilha na mão e gera erro de versão."

E o problema de governança: **um número sem procedência não pode ir para decisão.**

**Pergunta provável:** *"por que não um dashboard em cima de uma fonte só?"*
**Resposta:** porque a fonte primária não é comparável entre si. Foi por isso que o
sistema tem De-Para aprendido, conversão de moeda com penalidade de confiança e
convenção de sinal — não só um botão de "carregar Excel".

---

## Bloco 2 — Como comecei: premissas antes de código (1 min)

Escrevi primeiro as premissas, porque quase todo erro vem de premissa implícita:

| Premissa | Se for falsa |
|---|---|
| o acervo é local e versionado por hash | duplicado entra como fonte nova |
| os documentos têm camada de texto | precisaria de OCR (e de GB de dependência) |
| escopo é **trimestral** | anual exigiria outro exercício |
| número em USD > número convertido de BRL | o nível de receita fica distorto |

**Pergunta provável:** *"como vocêacrylicoidou o escopo?"*
**Resposta:** por eliminação. O que tinha dados comparáveis era o trimestre em
dólar; o anual ficou fora de propósito — e isso está escrito no código, não só no
documento.

---

## Bloco 3 — O que construí, em camadas (3 min)

Desenho a cadeia na tela (ou no papel):

```
Container/inventário → varredura (SHA-256) → classificação do documento
   → parser (PyMuPDF / planilha / HTML) → De-Para PT-EN → plausibilidade
   → carga com id_fonte + confiança → auditoria → DQS → projeção → painel
```

Quatro camadas, e a regra de separação que **mais importa**:

- `models/` — 12 tabelas SQLite, De-Para, glossário, repositórios.
- `workers/` — scan, parsers, SEC, qualidade, projeção, descoberta, deck.
- `controllers/` — casos de uso finos, **sem regra de negócio**.
- `views/` — Web (Plotly + JS, 11 abas) e GUI (PySide6, 8 abas), mais REST.

> "Projeção não é fato: ela vive em `tb_projeção`, fora da matriz, e é sempre
> rotulada. Isso é o que impede alguém de ler um número projetado como realizado."

**Pergunta provável:** *"por que MVC-W e não só scripts?"*
**Resposta:** porque o problema apareceu em três lugares diferentes — a extração de
texto do PDF falhava por nome de arquivo, a carga perdia confiança, e o painel
mostrava status que não explicava nada. Com a regra de negócio em um lugar só, cada
um desses bugs teve um conserto localizado e testável.

---

## Bloco 4 — Três decisões técnicas que eu defenderia (2 min)

**1. Escolhi a biblioteca medindo, não por fama.** Benchmark no acervo real:

| Biblioteca | Texto (11 PDFs) | Tabelas | Veredito |
|---|---|---|---|
| PyMuPDF | 2,2 s | 31 | **principal** |
| PDFOxide (Rust) | 6,2 s | **0** nos DFs | só fallback |
| pypdf / pdfminer | 16 s / 23 s | — | descartados |

> "As libs Rust são mais rápidas na propaganda e **redundantes** aqui: produzem as
> mesmas 35 extrações. Eu teria ganhado 2,8× de lentidão e perdido a tabela, sem
> ganhar um único fato."

**2. Paralelismo onde é seguro.** O parse (CPU, sem escrita) foi para processos;
a carga continua sequencial no processo principal, na ordem de prioridade.

| Modo | Tempo (124 arquivos) | Resultado |
|---|---|---|
| serial | 169,9 s | 269 cargas, 52 revisões |
| 4 processos | 102,3 s | **idêntico** |

> "Eu não confio em 'deve dar o mesmo resultado' — eu comparei. Mesmo número de
> cargas, mesmas revisões, zero erros. Se o pool morrer, cai para serial em vez de
> marcar 100 arquivos como erro."

**3. O incremental é o que torna o sistema usável.**

| Cenário | Tempo |
|---|---|
| carga inicial (108 arquivos) | 252 s |
| rodar sem nada novo | **4,7 s** |
| 1 arquivo novo | **2,0 s** |

**Pergunta provável:** *"como você garante que rodar de novo não estraga o banco?"*
**Resposta:** três camadas — SHA-256 para não reprocessar, regra de confiança para
não rebaixar fato bom, e um teste que roda o ETL duas vezes e compara a soma dos
fatos. Foi ele que provou: 136 fatos → 136, soma 3137,8537 → 3137,8537.

---

## Bloco 5 — Qualidade como produto, não como relatório (2 min)

> "Um número no painel sem saber de onde veio é opinião. Então construí o controle
> antes de confiar no dashboard."

- **DQS 0–100** com 5 dimensões ponderadas: completude 30%, plausibilidade 25%,
  consistência 15%, rastreabilidade 15%, tempestividade 15%. Hoje: **75,5** em 67
  scorecards.
- **Evolução do DQS no tempo (M7.23):** a série histórica vai de **70,7** para
  **88,3 (+17,6)** em 14 períodos, com PETROBRAS de 75,4 a 99,8. Ela responde
  "melhorou ou piorou desde o início?", que o scorecard atual não responde.
- **Fila priorizada** (458 itens) com código de motivo.
- **Escalonamento por repetição**: `DRIFT_ZSCORE` da BP apareceu 39 vezes e subiu de
  P2 para P1 — problema recorrente vai para o topo.
- **Contrato de dados** roda ao fim de cada ETL e aponta a linha exata.
  Ele já encontrou 9 registros com período anual que eu não tinha previsto.
- **Regra de ouro:** confiança baixa vai para revisão humana, nunca para o painel.

**Pergunta provável:** *"o que você faria com o DQS baixo?"*
**Resposta:** ele não é um número para se gabar, é um mapa do trabalho. DQS baixo por
temperestividade (64,2) diz "faltou o 2T26 da empresa X" — que é uma PUBLICAR_DATA,
não um defeito de dado. Já completude 40,6 diz que falta rubrica — e aí é ação.

---

## Bloco 6 — O que os testes encontraram (2 min)

> "Escrevi os testes para provar as decisões, e eles acharam coisas que eu não
> veria lendo o código."

**22 bugs reais**, dos quais cito quatro que mostram o tipo de raciocínio:

1. **`Transcrição 1T25.pdf` era parseado.** Eu comparava nome de arquivo
   por substring; o acento quebrava o casamento. O documento narrativo entrava na
   base. → normalização por regex sobre nome.
2. **`R$` estava sendo lido como USD.** E `3Q26` não virava período, porque minha
   regex exigia ano de 4 dígitos. → testes de caso de borda com nome real.
3. **A duração do arquivo era medida antes do parse** (Python avalia os argumentos
   da esquerda para a direita), então 67,8 ms apareciam como 0 no painel. → o teste
   de duração do painel pegou.
4. **A taxa de resolução da auditoria anunciava 100%** com **875** itens abertos: o
   denominador era o número de *tipos* de decisão (`GROUP BY decisao`), não o total
   de decisões. O KPI estava errado na direção otimista — o pior defeito possível
   num controle. Hoje são 50% (2 de 4) e o painel mostra os dois contadores.

E o achado mais honesto:

> "Verifiquei se a projeção cobria todos os indicadores e **não cobria**: `FCL`,
> `DIVIDA_BRUTA` e `DESPESA_OPERACIONAL` ficavam de fora por causa de uma lista fixa
> no código, sem aviso na tela. Hoje a projeção é dirigida pelos dados e a aba mostra
> a cobertura — 10 de 10 rubricas. Isso só apareceu porque alguém perguntou."

E o que eu corrigi agora, aplicando o mesmo raciocínio à métrica nova:

> "A primeira versão do `páginas/seg` dividia as 37 páginas do DF pelo tempo do parse
> que só leu 12. O número estava 3× inflado. Passei a contar **páginas lidas**, e a
> separar **não medido** (NULL) de **mediu zero** — senão as 581 fontes sem arquivo
> local puxariam a média para baixo."

---

## Bloco 7 — Governança: como o sistema avisa o que falta (1 min)

Construí o mecanismo que responde *o que foi anunciado e ainda não está aqui*:

| Sinal | Significado |
|---|---|
| `ANUNCIADO` | documento novo do trimestre já publicado |
| `ANUNCIADO_SEM_XBRL` | comunicado existe, número estruturado ainda não |
| `sem frame XBRL CY2026Q3` | **o trimestre ainda não pode ser fechado** |

Na checagem de hoje: 9 documentos relevantes da Petrobras e **nenhum frame
`CY2026Q3`** — o 3T26 foi comunicado, mas o número estruturado não foi publicado.
Quando ele sair, o ciclo é: descoberta → baixa → `etl --novos` → fato.

**Pergunta provável:** *"e se a fonte primária cair?"*
**Resposta:** a SEC publica o mesmo número em XBRL, com CIK por empresa — é a minha
conferência cruzada e o preenchimento de lacuna. Quando a IR bloqueia automação
(Chevron e BP devolvem 403), o relatório **diz isso** em vez de fingir cobertura.

---

## Bloco 8 — Limites que eu assumo de novo (1 min)

Assumir o limite é o que me dá credibilidade:

| Limite | Como trato |
|---|---|
| RI dinâmico ou bloqueado | SEC como canal confiável; falha declarada |
| 6-K principal é só a capa | leio os **anexos** (Shell: 48; Chevron: 70) |
| Anexo é inline XBRL | número vem do `companyfacts` |
| Sem cache de texto de PDF | backlog aberto (M8.11) |
| Memória do scorecard é por mudança de DQS | ponto gravado só quando o score muda — a série mostra evolução, não log de execução |
| Métrica de PDF não cobre fonte sem arquivo local | 581 fontes do acervo não têm mais o PDF no disco; ficam **sem** métrica, nunca zeradas |
| Série curta não é tendência | método e confiança degradam explicitamente |

---

## Bloco 9 — O que eu faria a seguir (1 min)

1. **Ler os anexos em profundidade** para extrair a tabela, não só o número
   estruturado (hoje é inline XBRL e eu entrego o arquivo, não o fato).
2. **Cache de texto por hash** para matar o último custo do reprocessamento.
3. **Rolling-origin**: recalcular o passado e medir o erro real das projeções —
   hoje eu tenho método escolhido por backtesting, ainda não tenho backtest ao longo
   da história viva.
4. **Cenários com Brent/FX** e intervalo que responda à covariância dos fatores.
5. **Fechar o canal primário** com render de JS, hoje bloqueado em 2 de 7 empresas.

E um detalhe de método, se perguntarem como eu mostro o produto:

> "Eu **capturei as telas do painel rodando** em Chrome headless — 11 abas, uma por
> slide. Um mock-up desenhado à mão prova que eu sei desenhar tela, não que o
> sistema funciona. E as telas de governança usam janela maior que as outras,
> porque a métrica nova fica abaixo da dobra: com o print de 1000px eu estaria
> entregando uma tela bonita que esconde justamente o que eu fiz."

---

## Fecho — o que eu quero que levem deste projeto (1 min)

> "Não é o dashboard. É a cadeia de decisões:
> *o número tem dono (id_fonte), tem medida (confiança), tem regra (contrato),
> e tem explicação (diagnóstico por arquivo).*
>
> Quando um número não está pronto, o sistema **diz** que não está — em vez de
> publicar um número bonito e silenciosamente errado. Foi assim que encontrei três
> rubricas sem projeção, um documento narrativo entrando na base e uma duração
> zerada no painel. **O problema nunca foi o gráfico: era o que ele afirmava sem
> dizer.**"

---

### Bônus: a regra que encontrou um erro de dado a regra que encontrou um erro de dado

**Pergunta provável:** "Qual análise automatizada do seu próprio produto valeria
mais na entrevista?"

**Resposta:** A regra cross-sectional (M7.24) compara cada empresa com os pares
do MESMO trimestre, enquanto as demais regras comparam com a propria história.
Rodando sobre a base real, ela sinalizou 10 casos — e um deles era o **CAPEX da
Petrobras a 0,01 USD bi** em 1T26 e 2T26, contra pares em 3 a 6 bi. O CAPEX do
4T25 era 6,29: a série não caiu 98%, o valor não foi extraído. A planilha
`Excel 2T26 USD.xlsx` tem uma aba "Investimentos" cujas linhas são projetos, não
o investimento consolidado.

O ponto que eu defenderia: o alerta **não diz que a Petrobras fez errado**. Diz
que o número não se parece com o dos pares. Quem lê a análise tem duas leituras
possíveis — resultado real ou defeito de extração — e a triagem tem que separar
as duas antes de agir. Num benchmark, apresentar 0,01 como CAPEX sem checar a
fonte seria apresentar um bug como resultado de negócio.

---

## Apêndice — números para citar sem consultar

| Métrica | Valor |
|---|---|
| Empresas / trimestres | 7 · 14 (2023Q1–2026Q2) |
| Fontes catalogadas | 871 (183 com arquivo local) |
| Fatos | 272 financeiros + 121 operacionais |
| DQS médio | 75,5 (67 scorecards) · rastreabilidade 100,0 |
| Evolução do DQS (M7.23) | 70,7 → 88,3 (+17,6) em 14 períodos · PETROBRAS 75,4 → 99,8 |
| Fila de análise | 458 itens (60 P1, 398 P3) · 9 regras de desvio |
| Auditoria | 134 alertas · 877 na fila (875 abertas) · taxa de resolução 50,0 % (2 de 4) |
| Projeções | 147 pontos · 49 séries · 10 de 10 rubricas |
| ETL completo / incremental | 135 s (3 processos) / 2–5 s |
| Leitura de PDF (M8.12) | 133 PDFs · 1.366 páginas lidas · 6,7 pág/s · 1.205 tabelas |
| Apresentação | 23 slides em PPTX, cores Petrobras, gerados do banco (`app_main.py pdf --pptx`) |
| Testes | 117 passam, 2 skips |
| Erros de carga | 0 |
| Contrato de dados | 393 fatos verificados, 0 violações |
