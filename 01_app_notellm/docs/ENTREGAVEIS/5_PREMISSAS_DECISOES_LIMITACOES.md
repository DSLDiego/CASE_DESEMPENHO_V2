# 5. Premissas, decisões e limitações

Detalhe original: [`../PREMISSAS_E_LIMITACOES.md`](../PREMISSAS_E_LIMITACOES.md)

Organizado em **5.1 Tecnológicas** e **5.2 Financeiras**, porque as duas naturezas
de risco são diferentes: uma é limitação de engenharia, a outra é limitação de
interpretação do número.

---

## 5.1 Premissas, decisões e limitações TECNOLÓGICAS

### Premissas

| # | Premissa | Consequência se for falsa |
|---|---|---|
| T1 | O acervo é local (`03_Conteiner`) e versionado por hash | Duplicado entra como fonte nova → o scanner escolhe o nome mais descritivo |
| T2 | Documentos têm camada de texto (não são PDFs digitalizados) | OCR seria necessário — por isso MinerU/PDF-Extract-Kit foram descartados |
| T3 | SQLite suporta o volume (centenas de milhares de fatos) | Migração para Postgres; a camada de repositório isola o impacto |
| T4 | A SEC é acessível e publica os mesmos números das companhias | Sem XBRL, a conferência cruzada deixa de existir |
| T5 | Um processo principal + parses paralelos é seguro | Gravação fora do processo principal poderia corromper a transação |

### Decisões técnicas (com o porquê)

| # | Decisão | Alternativa descartada | Motivo |
|---|---|---|---|
| D1 | **PyMuPDF como parser principal** | PDFOxide, pdf-inspector, pypdf, pdfminer | Benchmark no acervo: 2,2 s contra 6–23 s, e **as libs Rust são redundantes** (mesmas 35 extrações). Trocar custaria 2,8× de velocidade e a detecção de tabelas sem ganhar um fato |
| D2 | PyMuPDF → pdfplumber como fallback de tabela | so pdfplumber | pdfplumber encontra as tabelas, mas é 2× mais lento |
| D3 | PDFOxide como **fallback de PDF corrompido** | sem fallback | Arquivo truncado derrubava o parse; o pânico pyo3 é `BaseException` e derrubaria o ETL inteiro |
| D4 | **Carga sequencial, parse paralelo** | paralelizar também a carga | A regra "fato bom nunca é rebaixado" depende da ordem; com carga paralela o resultado passaria a depender do schedule |
| D5 | Projeção **dirigida pelos dados** (toda rubrica com fato) | lista fixa de rubricas | A lista fixa deixava `FCL`, `DIVIDA_BRUTA` e `DESPESA_OPERACIONAL` sem projeção, sem aviso |
| D6 | Projeção isolada em `tb_projeção` | misturar na matriz | Projeção não é fato; a separação é o que impede que um número projetado seja lido como realizado |
| D7 | Método escolhido por **backtesting** (menor MAE) | método fixo por rubrica | Escolher por métrica de erro é defensável; escolher por intuição não |
| D8 | Classificação de PDF por **regex sobre nome normalizado** | substring em nome cru | `Transcrição 1T25.pdf` (com acento) era **parseado** e `_DFs ... US$.pdf` não casava |
| D9 | Contrato de dados roda **ao fim** de cada ETL | so na carga | Defeito de tipo/escala aparece tarde; o contrato dá a linha exata |
| D10 | Descoberta prioriza a SEC e **declara** a falha do RI | esconder RI inacessível | Chevron/BP bloqueiam automação (403); dizer isso é mais honesto que fingir cobertura |
| D11 | Sem `SMTP_*`, gerar `.eml` em vez de enviar | enviar "para testar" | Envio sem credencial é erro clássico e polui a caixa de entrada |
| D12 | 4 dimensões visuais + glossário | deixar o usuário interpretar o rótulo | `DESPESA_OPERACIONAL` negativo e `CAPEX` positivo geram dúvida legítima |

### Como ler um alerta de outlier

Um alerta cross-sectional **nao afirma que a empresa está errada**. Afirma que o
número nao se parece com o dos pares no mesmo trimestre. As duas leituras sao
possiveis e precisam ser separadas antes de agir:

| Leitura | Como distinguir | O que fazer |
|---|---|---|
| **Real** | O número confere com o release da empresa | Levar para a análise comparativa |
| **Defeito de extração** | O release traz o valor correto e a base nao | Corrigir o parser e reprocessar a fonte |

O caso real destá base e o CAPEX da Petrobras a 0,01 USD bi em 1T26 e 2T26
(-1,9 sigma contra pares em 3-6 bi). A série nao caiu 98%: o valor nao foi
extraido da planilha `Excel 2T26 USD.xlsx`, cuja aba "Investimentos" lista
projetos e nao o investimento consolidado. Sem a comparação com os pares, o
0,01 entraria no benchmark como se fosse resultado operacional.

### Limitações técnicas

| # | Limitação | Impacto | Como está registrado |
|---|---|---|---|
| L1 | Portal de RI dinâmico (Petrobras, Equinor) ou bloqueado (Chevron, BP: HTTP 403) | Sem canal primário automatizado | Relatório de descoberta mostra o erro por empresa; SEC cobre |
| L2 | Documento principal do 6-K é só a **capa**; a demonstração é anexo | Comunicado é achado, número não | `anexos_sec()` lê o `index.json` (Shell: 48 anexos; Chevron: 70); número estruturado vem do `companyfacts` |
| L3 | Anexos da SEC são **inline XBRL** (tabela em tag, não frase) | Entra no acervo como `SEM_DADOS` | Lacuna reportada até o `CY20xxQn` existir |
| L4 | Histórico local concentrado em 2025–2026 | 2023–2024 dependem da SEC | 2 testes marcados como skip por isso, explicitamente |
| L5 | Cobertura de rubricas desigual entre empresas | `LUCRO_BRUTO` so na Petrobras | DQS de completude torna visível em vez de esconder |
| L6 | Sem cache de texto de PDF (M8.11 aberto) | Reprocessar reextrai o texto | ETL incremental já evita o reprocessamento |
| L7 | Gauge de precedence: baixo compared ao ganho de paralelismo | Limite de escala | `--jobs` é configurável |
| L8 | A métrica de leitura do PDF (M8.12) cobre só os **133 PDFs com arquivo local** | 581 fontes sem arquivo não têm páginas/tabelas | Ficam **fora** da média (`NULL` ≠ 0); `fontes metrica` reprova o acervo quando o PDF volta ao disco |
| L9 | O histórico do scorecard grava um ponto **quando o DQS muda**, não a cada execução | Uma mudança pequena e uma grande têm o mesmo peso visual | É o que faz a série ser evolução e não log; a variação por trimestre fica explícita na tabela |
| L10 | Páginas lidas é limitado pela política de profundidade (12 páginas; 30 em DF) | Cobertura de 36,5% do acervo | "Cobertura" é exibida ao lado do throughput, para o número não parecer maior do que é |

---

### Limitações tecnológicas adicionais

| # | Limitação | Impacto | Mitigacao no produto |
|---|---|---|---|
| T-L1 | A comparação cross-sectional acusa **defeito de extração**, nao erro da empresa | Um CAPEX de 0,01 bi na Petrobras aparece como "fora da curva" quando, na verdade, o valor nao foi extraido | `OUTLIER_CROSS_SECTIONAL` gera item de fila com a fonte, e a triagem checa a fonte antes de culpar o número |
| T-L2 | Com 7 empresas e 14 trimestres, o desvio-padrão do grupo e instável em trimestres com pouca cobertura | Grupo com 4-5 empresas pode gerar z alto por ruido | Piso de 4 empresas por grupo e limiar de 1,8 sigma (nao 2,0) justamente porque a amostra e pequena |
| T-L3 | O z-score usa desvio-padrão populacional, nao amostral | Em grupos pequenos, o estimador amostral inflaria o desvio e esconderia outliers | `pstdev` foi escolhido por ser o mais conservador para detectar; o preco e dizer "1,8 sigma" quando a amostra nao sustenta o intervalo |

## 5.2 Premissas, decisões e limitações FINANCEIRAS

### Premissas

| # | Premissa | Consequência se for falsa |
|---|---|---|
| F1 | Os números publicados pelas 7 companies são comparáveis entre si | Todo o benchmark perde sentido |
| F2 | O mesmo trimestre é o período de referência em todas as fontes | Comparação cruzada fica enviesada |
| F3 | USD é a moeda de comparação; BRL convertido por PTAX de fechamento | Nível de receita fica distorto |
| F4 | Versão em USD do documento é preferível à convertida de BRL | Preferência invertida inflaria/diminuiria a receita |
| F5 | Série de 4+ trimestres é mínima para falar em tendência | Com menos pontos, é extrapolação — e o sistema diz isso (`MEDIA_2DP`, confiança 0,35) |
| F6 | "Ajustado" (EBITDA ajustado) é a medida comparável entre companhias | Comparar ajustado com GAAP distorce margem |

### Decisões financeiras

| # | Decisão | Motivo |
|---|---|---|
| DF1 | EBITDA **ajustado** como referência de rentabilidade | É o que as companhias reportam de forma homogênea |
| DF2 | FCL = FCO − CAPEX, padronizado pelo painel | Cada empresa publica sua própria definição; o painel usa uma so |
| DF3 | **Despesa negativa** e **CAPEX positivo** por convenção | Evita que "despesa menor = pior" na leitura do gráfico |
| DF4 | Conversão BRL→USD com penalidade de 0,05 de confiança | Conversão é menos confiável que número nativo |
| DF5 | Fato existente com confiança maior **não** é rebaixado | O banco so melhora com o tempo |
| DF6 | Projeção rotulada como projeção, nunca somada à matriz real | Nenhum número projetado pode ser lido como realizado |
| DF7 | DQS com pesos explícitos e pública | Sem isso, "score de qualidade" é opinião |
| DF8 | Confianca < 0,70 vai para revisão humana, **não** para o painel | Automação não decide o que é verdade |

### Limitações financeiras

| # | Limitação | Impacto | Como está registrada |
|---|---|---|---|
| LF1 | Escopo **trimestral** — anual (20-F/10-K) fora | Comparação anual exige outro exercício | Regra explícita em `sec_edgar.extract_facts` |
| LF2 | "Receita líquida" diverge entre empresas (cada uma publica sua composição) | Pequeno desvio de nível | De-Para aprendido + confiança menor na rubrica ambígua |
| LF3 | Capex é outflow: o número positivo representa uso de caixa | Leitura invertida | Glossário e convenção de sinal |
| LF4 | CAGR/tendência exige ≥4 pontos; com menos, o intervalo é largo | Projeção com ±2σ | `confiança` exposto no painel |
| LF5 | Temperestividade é baixa (64,2) porque nem toda empresa publicou 2T26 | DQS cai por defasura, não por erro | Distingue de plausibilidade (98,5) |
| LF6 | Conversão BRL usa PTAX do trimestre, não taxa intradiária | Diferença de ±1% no convertido | Declarado em `config.PTAX_FALLBACK` |
| LF7 | IFRS 16 (aluguel) não é homogeneizado entre as empresas | CAPEX e EBITDA ajustado divergem | Registrado como backlog |
| LF8 | Projeção assume sazonalidade estável (k=4) | Eventos extraordinários (venda de ativo) quebram a série | `QUEBRA_ESTRUTURAL` sinaliza isso |

### Como um número deve ser lido (protocolo)

1. **Existe fonte?** → `id_fonte` na aba Fontes.
2. **É confiável?** → DQS da empresa×trimestre e a fila de revisão.
3. **É realizado ou projetado?** → projeção vive em `tb_projeção`, sempre rotulada.
4. **Como está medido?** → glossário (definição, fórmula, unidade, sinal).

**Regra de ouro do projeto:** *confiança baixa vai para revisão humana, nunca para o
painel como se fosse verdade.*
