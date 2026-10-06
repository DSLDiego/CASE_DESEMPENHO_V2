# 4. Evidências dos controles de qualidade

Detalhe completo: [`../EVIDENCIAS_QUALIDADE.md`](../EVIDENCIAS_QUALIDADE.md) ·
Subsistema: `workers/quality_score.py`, `workers/data_contract.py`, `workers/etl.py`

Todas as métricas abaixo vêm do banco e podem ser reproduzidas com
`python app_main.py qualidade rodar` e `python app_main.py qualidade resumo`.

## 1. DQS — scorecard por empresa × trimestre

DQS 0–100 com cinco dimensões ponderadas:

| Dimensão | Peso | Média da base |
|---|---|---|
| Completude | 30% | 40,6 |
| Plausibilidade | 25% | 98,5 |
| Consistência | 15% | 93,8 |
| Rastreabilidade | 15% | 100,0 |
| Tempestividade | 15% | 64,2 |
| **DQS médio** | — | **75,5** (67 scorecards) |

Classificação: **CONFIÁVEL** ≥ 80 · **REVISAR** 60–79 · **NÃO CONFIÁVEL** < 60.
Hoje: 16 CONFIÁVEL · 51 REVISAR · 0 NÃO CONFIÁVEL.

**Evidência de que a rastreabilidade é real:** 100,0 de rastreabilidade significa que
**todos** os 272 fatos financeiros têm `id_fonte` válido — verificado também por
integridade referencial (0 órfãos).

## 2. Evolução do DQS no tempo (M7.23)

`tb_qualidade_score` guarda o **último** estado de cada empresa × trimestre (chave
única, sobrescrita a cada recálculo) — sem uma segunda tabela, a evolução da
qualidade se perdia. `tb_qualidade_historico` grava um ponto por empresa × período
**quando o DQS muda de verdade**; rodar o scorecard de novo sem mudança não cria
ponto (a série mostra evolução, não log de execução).

| Período | DQS médio | Empresas |
|---|---|---|
| 2023Q1 | 70,7 | 5 |
| 2023Q2 | 71,6 | 7 |
| 2023Q3 | 70,4 | 3 |
| 2023Q4 | 66,5 | 1 |
| 2024Q1 | 70,7 | 5 |
| 2024Q2 | 74,5 | 7 |
| 2024Q3 | 72,4 | 3 |
| 2024Q4 | 66,5 | 1 |
| 2025Q1 | 71,8 | 4 |
| 2025Q2 | 72,5 | 7 |
| 2025Q3 | 70,4 | 3 |
| 2025Q4 | 80,5 | 7 |
| 2026Q1 | 82,6 | 7 |
| 2026Q2 | **88,3** | 7 |

| Empresa | Inicial → atual | Variação | Classe |
|---|---|---|---|
| PETROBRAS | 75,4 → 99,8 | **+24,4** | CONFIÁVEL |
| SHELL | 72,5 → 95,4 | +22,9 | CONFIÁVEL |
| TOTALENERGIES | 69,5 → 92,4 | +22,9 | CONFIÁVEL |
| CHEVRON | 72,5 → 89,4 | +16,9 | CONFIÁVEL |
| BP | 72,5 → 83,4 | +10,9 | CONFIÁVEL |
| EQUINOR | 66,5 → 76,3 | +9,8 | REVISAR |
| EXXONMOBIL | 72,5 → 81,7 | +9,2 | CONFIÁVEL |

**Leitura:** a virada de 2025Q4 (72,5 → 80,5) coincide com a carga SEC completa
nesse trimestre — antes disso os trimestres eram SEC parciais, com completude baixa.
É a sériehistoricalque transforma "DQS médio 75,5" em "a qualidade subiu 17,6 pontos
desde 2023 e a Petrobras é a que mais subiu".

Reprodução: `python app_main.py qualidade historico` (com `--empresa` para uma só).

## 3. Fila de análise priorizada

458 itens com código de motivo e prioridade:

| Prioridade | Itens | Origem dominante |
|---|---|---|
| P1 (urgente) | 60 | `OUTLIER_CROSS_SECTIONAL` (10), `DRIFT_ZSCORE` repetido da BP, `CONTAGEM_PERIODO`, `ATRASO_TRIMESTRE` |
| P3 | 398 | `RUBRICA_AUSENTE` (completude) |

**Escalonamento automático (M2.11):** um código de alerta que se repete mais de 3
vezes sobe um nível (P3→P2→P1). O `DRIFT_ZSCORE` da BP apareceu 39 vezes e foi
de P2 para P1 — o problema recorrente ficou no topo da fila em vez de se diluir.

## 4. Contrato de dados (execução a cada ETL)

`workers/data_contract.py` verifica tipos, obrigatoriedade, domínio e **convenção de
sinal** das tabelas de fato, apontando a linha exata.

| Verificação | Exemplo de violação detectada |
|---|---|
| Domínio de período | `26Q2` (fora de `20xxQ1..Q4`) → `fora do padrão` |
| Intervalo de confiança | `1.7` → `fora do intervalo [0, 1]` |
| Sinal obrigatório | receita −33,6 → "RECEITA_LIQUIDA não pode ser ≤ 0" |
| Convenção de sinal | despesa positiva, CAPEX negativo |

**Resultado real:** 393 fatos verificados (272 financeiros + 121 operacionais),
**0 violações**. Durante a implementação o contrato encontrou 9 registros operacionais
com período anual `2024A` — que são legítimos (âncoras de efetivo) e passaram a ser
aceitos explicitamente na tabela operacional.

## 5. Diagnóstico por arquivo (painel de Gestão ETL)

O ETL não diz mais apenas "não extraiu". A mensagem `SEM_DADOS` diz a causa real:

| Causa | Quantidade |
|---|---|
| não achou número no documento | 42 |
| período fora da janela-alvo | 16 |
| perdeu para um fato já gravado com confiança maior | 14 |
| foi para a fila de revisão | 10 |

E o motivo do PDF pulado é gravado: `PDF pulado: narrativo ('presentation')`.

### Métrica de leitura do PDF (M8.12)

O parse passa a medir **quanto leu**, não só o que extraiu. Por documento:
`n_paginas` (tamanho do arquivo), `n_paginas_lidas` (o que o parse percorreu, limitado
pela política de profundidade) e `n_tabelas` (tabelas detectadas). A execução soma em
`tb_etl_execucao.paginas_lidas` / `.tabelas_detectadas`.

| Métrica do acervo | Valor |
|---|---|
| PDFs medidos | 133 |
| Páginas (soma dos arquivos) | 3 743 |
| Páginas lidas | 1 366 |
| Cobertura | 36,5% |
| Throughput | **6,7 páginas/seg** |
| Tabelas detectadas | 1 205 (9,1 por documento) |

**Duas decisões que evitam número mentiroso:**
- o throughput divide **páginas lidas** pelo **tempo de parse**. Dividir o total do
  arquivo (37 páginas num DF lido até a 12ª) pelo tempo do parse inflaria o número
  em mais de 3×; dividir pelo tempo total da fonte mediria o disco, não o leitor;
- `NULL` (não medido) é diferente de `0` (mediu e não tem). As **581** fontes sem
  arquivo local ficam **fora** da média em vez de puxá-la para baixo.

`python app_main.py fontes metrica` preenche o acervo já processado sem
reprocessar — só conta páginas e detecta tabelas (~0,2 s/documento), em processos
paralelos; é idempotente e pula o que já tem métrica.

## 6. Regras de desvio (9, configuráveis em `tb_regra_alerta`)

`DRIFT_ZSCORE` · `QUEBRA_ESTRUTURAL` · `CONTAGEM_PERIODO` ·
`REVISAO_ENTRE_EXECUCOES` · `ATRASO_TRIMESTRE` · `BAIXA_CONFIANCA` ·
`SEM_FONTE` · `RUBRICA_AUSENTE` · `OUTLIER_CROSS_SECTIONAL`.

**Cross-sectional (M7.24):** as regras acima comparam a empresa com a **própria
história**; esta compara com os **pares do mesmo trimestre** (z-score ≥ 1,8σ,
mínimo de 4 empresas no grupo, para não acusar desvio onde a amostra é
insignificante). Rodando sobre os dados atuais, ela encontrou 10 casos — entre
eles o **CAPEX da Petrobras em 0,01 USD bi no 1T26 e 2T26**, contra pares em
3–6 bi. É um defeito de extração da aba "Investimentos" da planilha
(`Excel 2T26 USD.xlsx`, fonte 2067), e a regra o isolou automaticamente como P1
sem ninguém precisar comparar as tabelas à mão.

## 7. Regras de negócio aplicadas na carga

| Regra | Onde | Efeito |
|---|---|---|
| Confiança mínima 0,70 | `etl.py` | abaixo disso vai para revisão, nunca para a matriz |
| Limites de plausibilidade por rubrica | ` plausível()` | valor impossível não entra (vai para revisão) |
| Fato bom nunca é rebaixado | `etl.py` | extração pior não sobrescreve existente melhor |
| BRL não sobrescreve USD | `etl.py` | conversão tem penalidade de 0,05 de confiança |
| Idempotência | `scan_container` + `upsert` | reexecutar não duplica nem altera |
| Proveniência obrigatória | schema | sem `id_fonte` o fato é flagrado (`SEM_FONTE`) |

## 8. Testes automatizados

`python -m pytest tests/ -q` → **117 passam, 2 skips** (2023/2024 sem pasta no Container).

Os testes não são decorativos: **22 bugs reais** foram encontrados por eles, entre
os quais `Transcrição 1T25.pdf` sendo parseado, `R$` lido como USD, IC95 invertido
em série negativa, `ZeroDivisionError` na aba Qualidade, a duração do arquivo
medida antes do parse (67,8 ms gravados como 0), a taxa de resolução da auditoria
dividindo pelo nº de **tipos** de decisão (100% com 875 itens abertos), o
`addTextItem` removido no pyqtgraph 0.14 quebrando a GUI com base vazia e a faixa de
KPI do PPTX com o par (rótulo, valor) invertido.

| Verificação | Evidência |
|---|---|
| Idempotência | 2ª rodada: 136 fatos → 136, soma 3137,8537 → 3137,8537 |
| Integridade | 0 `id_fonte` órfão · 0 hash duplicado · 183 caminhos locais existem |
| ETL completo | 124 arquivos · 269 cargas · **0 erro** |
| ETL incremental | processa 1 arquivo novo e 0 quando nada muda |
| Paralelismo | 1 e 4 processos produzem **resultados idênticos** |
| Projeção | toda rubrica com fato tem projeção (10/10) |
| Contrato | dado adulterado é detectado com a linha |
| Glossário | todo derivado tem fórmula e dependências declaradas |

## 9. Onde conferir no painel

- **Aba Qualidade**: DQS, dimensões, **evolução do DQS no tempo**, fila priorizada, contrato de dados, regras.
- **Aba Gestão ETL**: o que foi processado, pulado, **por quê** (com duração real)
  e a **métrica de leitura do PDF** (páginas, páginas lidas, tabelas, pág/s).
- **Aba Auditoria**: KPIs, triagem e o **relatório em PDF** do período
  (`python app_main.py auditoria relatorio --de --ate`).
- **Aba Fontes**: catálogo com origem, hash, status e URL de cada documento.
- **API**: `/api/qualidade` (inclui `contrato` e `historico`), `/api/etl`,
  `/api/fontes`, `/api/auditoria` (`?de=&ate=` traz a trilha do período, `?pdf=1`
  gera o relatório).