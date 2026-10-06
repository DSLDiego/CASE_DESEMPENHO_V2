# Evidencias dos controles de qualidade (gerado pelo ETL)

## Auditoria (tb_quality_alerts)

| Tipo | Descricao | Severidade |
|---|---|---|
| ATRASO_TRIMESTRE | [(todas) 2026Q2] último trimestre carregado é 2026Q2, esperado 2026Q3 — pipeline possivelmente parado | HIGH |
| CONTAGEM_PERIODO | [(todas) 2023Q3] volume de fatos caiu de 19 para 7 (-63%) em 2023Q3 | HIGH |
| CONTAGEM_PERIODO | [(todas) 2023Q4] volume de fatos caiu de 7 para 1 (-86%) em 2023Q4 | HIGH |
| CONTAGEM_PERIODO | [(todas) 2024Q3] volume de fatos caiu de 31 para 9 (-71%) em 2024Q3 | HIGH |
| CONTAGEM_PERIODO | [(todas) 2024Q4] volume de fatos caiu de 9 para 1 (-89%) em 2024Q4 | HIGH |
| CONTAGEM_PERIODO | [(todas) 2025Q3] volume de fatos caiu de 21 para 9 (-57%) em 2025Q3 | HIGH |
| DIVERGENCIA_FONTE | LUCRO_LIQUIDO CHEVRON 2026Q1: RI=3.51 x SEC=2.21 (37%) | MEDIUM |
| DIVERGENCIA_FONTE | FCO CHEVRON 2026Q2: RI=45.32 x SEC=25.15 (45%) | MEDIUM |
| DIVERGENCIA_FONTE | FCO CHEVRON 2026Q1: RI=29.85 x SEC=2.51 (92%) | MEDIUM |
| DIVERGENCIA_FONTE | LUCRO_LIQUIDO BP 2024Q2: RI=-0.13 x SEC=0.07 (154%) | MEDIUM |
| DIVERGENCIA_FONTE | FCO CHEVRON 2024Q2: RI=35.23 x SEC=13.12 (63%) | MEDIUM |
| DRIFT_ZSCORE | [BP 2026Q1] FCO 2026Q1: valor 2.86 desvia -5.2σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [BP 2026Q2] FCO 2026Q2: valor 10.86 desvia +2.5σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [BP 2025Q4] LUCRO_LIQUIDO 2025Q4: valor -3.42 desvia -4.8σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [BP 2026Q1] RECEITA_LIQUIDA 2026Q1: valor 52.26 desvia +4.8σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [BP 2026Q2] RECEITA_LIQUIDA 2026Q2: valor 69.11 desvia +10.7σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [CHEVRON 2026Q2] FCL 2026Q2: valor 18.09 desvia +8.3σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [CHEVRON 2024Q2] FCO 2024Q2: valor 35.23 desvia +3.4σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [CHEVRON 2026Q2] FCO 2026Q2: valor 45.32 desvia +2.5σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [CHEVRON 2024Q1] LUCRO_LIQUIDO 2024Q1: valor 5.50 desvia -3.4σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [CHEVRON 2024Q2] LUCRO_LIQUIDO 2024Q2: valor 4.44 desvia -3.9σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [CHEVRON 2025Q1] LUCRO_LIQUIDO 2025Q1: valor 3.50 desvia -2.4σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [CHEVRON 2025Q2] LUCRO_LIQUIDO 2025Q2: valor 2.49 desvia -2.5σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [CHEVRON 2026Q2] LUCRO_LIQUIDO 2026Q2: valor 12.21 desvia +14.1σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [CHEVRON 2025Q2] RECEITA_LIQUIDA 2025Q2: valor 44.82 desvia -2.5σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [CHEVRON 2026Q2] RECEITA_LIQUIDA 2026Q2: valor 67.20 desvia +9.3σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [EQUINOR 2026Q2] FCO 2026Q2: valor 9.47 desvia +2.7σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [EQUINOR 2026Q1] LUCRO_LIQUIDO 2026Q1: valor 3.10 desvia +2.2σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [EQUINOR 2026Q2] LUCRO_LIQUIDO 2026Q2: valor 4.84 desvia +3.0σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [EQUINOR 2026Q1] RECEITA_LIQUIDA 2026Q1: valor 27.84 desvia +7.0σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [EQUINOR 2026Q2] RECEITA_LIQUIDA 2026Q2: valor 35.18 desvia +9.3σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [EXXONMOBIL 2025Q2] LUCRO_LIQUIDO 2025Q2: valor 7.08 desvia -2.4σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [EXXONMOBIL 2026Q1] LUCRO_LIQUIDO 2026Q1: valor 4.18 desvia -5.4σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [EXXONMOBIL 2026Q2] LUCRO_LIQUIDO 2026Q2: valor 14.53 desvia +4.4σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [EXXONMOBIL 2024Q2] RECEITA_LIQUIDA 2024Q2: valor 93.06 desvia +2.3σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [EXXONMOBIL 2026Q2] RECEITA_LIQUIDA 2026Q2: valor 114.53 desvia +7.1σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [PETROBRAS 2025Q4] FCO 2025Q4: valor 10.16 desvia -4.9σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [PETROBRAS 2026Q1] FCO 2026Q1: valor 8.40 desvia -2.1σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [PETROBRAS 2026Q2] LUCRO_BRUTO 2026Q2: valor 19.49 desvia +13.3σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [PETROBRAS 2026Q2] LUCRO_LIQUIDO 2026Q2: valor 10.43 desvia +2.7σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [PETROBRAS 2026Q2] RECEITA_LIQUIDA 2026Q2: valor 33.61 desvia +11.0σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [SHELL 2026Q2] DIVIDA_BRUTA 2026Q2: valor 73.08 desvia -30.2σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [SHELL 2026Q2] EBITDA_AJUSTADO 2026Q2: valor 20.71 desvia +2.3σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [SHELL 2026Q2] FCL 2026Q2: valor 17.52 desvia +3.7σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [SHELL 2025Q1] FCO 2025Q1: valor 9.28 desvia -6.7σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [SHELL 2026Q1] FCO 2026Q1: valor 6.06 desvia -2.8σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [SHELL 2026Q2] FCO 2026Q2: valor 21.43 desvia +4.1σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [SHELL 2026Q2] LUCRO_LIQUIDO 2026Q2: valor 10.82 desvia +4.4σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [SHELL 2026Q2] RECEITA_LIQUIDA 2026Q2: valor 94.66 desvia +7.0σ da série anterior | MEDIUM |
| DRIFT_ZSCORE | [TOTALENERGIES 2025Q2] LUCRO_LIQUIDO 2025Q2: valor 2.75 desvia -2.2σ da série anterior | MEDIUM |
| QUEBRA_ESTRUTURAL | [CHEVRON 2026Q2] FCL: nível muda de 3.93 para 9.68 (+146%) na série | MEDIUM |
| QUEBRA_ESTRUTURAL | [EQUINOR 2026Q2] LUCRO_LIQUIDO: nível muda de 1.13 para 3.08 (+172%) na série | MEDIUM |
| QUEBRA_ESTRUTURAL | [PETROBRAS 2026Q2] FCO: nível muda de 18.16 para 10.27 (-43%) na série | MEDIUM |
| QUEBRA_ESTRUTURAL | [PETROBRAS 2026Q2] LUCRO_LIQUIDO: nível muda de 3.43 para 6.51 (+90%) na série | MEDIUM |
| QUEBRA_ESTRUTURAL | [SHELL 2026Q2] FCL: nível muda de 7.21 para 10.23 (+42%) na série | MEDIUM |
| VARIATION_SPIKE | LUCRO_LIQUIDO BP: 212% entre 2025Q4 e 2026Q1 | MEDIUM |
| VARIATION_SPIKE | FCO BP: 62% entre 2025Q4 e 2026Q1 | MEDIUM |
| VARIATION_SPIKE | FCO BP: 280% entre 2026Q1 e 2026Q2 | MEDIUM |
| VARIATION_SPIKE | RECEITA_LIQUIDA CHEVRON: 46% entre 2026Q1 e 2026Q2 | MEDIUM |
| VARIATION_SPIKE | LUCRO_LIQUIDO CHEVRON: 248% entre 2026Q1 e 2026Q2 | MEDIUM |

## Fila de revisao (tb_review_queue, top 60)

| Empresa | Periodo | Rubrica | Motivo | Status |
|---|---|---|---|---|
| PETROBRAS | 2026Q2 | DIVIDA_BRUTA | fora do limite de plausibilidade (Desempenho Financeiro Petrobras 2T26 (1).pdf) | PENDENTE |
| PETROBRAS | 2026Q2 | DIVIDA_LIQUIDA | confianca 0.65 em Desempenho Financeiro Petrobras 2T26 (1).pdf | ABERTO |
| PETROBRAS | 2026Q2 | LUCRO_LIQUIDO | confianca 0.65 em Desempenho Financeiro Petrobras 2T26 (1).pdf | ABERTO |
| PETROBRAS | 2026Q2 | FCO | confianca 0.65 em Desempenho Financeiro Petrobras 2T26 (1).pdf | ABERTO |
| PETROBRAS | 2026Q2 | FCL | confianca 0.65 em Desempenho Financeiro Petrobras 2T26 (1).pdf | ABERTO |
| PETROBRAS | 2026Q2 | EBITDA_AJUSTADO | confianca 0.65 em Desempenho Financeiro Petrobras 2T26 (1).pdf | ABERTO |
| PETROBRAS | 2026Q2 | RECEITA_LIQUIDA | confianca 0.65 em Desempenho Financeiro Petrobras 2T26 (1).pdf | ABERTO |
| PETROBRAS | 2026Q2 | LUCRO_BRUTO | confianca 0.65 em Desempenho Financeiro Petrobras 2T26 (1).pdf | ABERTO |
| PETROBRAS | 2026Q2 | DESPESA_OPERACIONAL | confianca 0.65 em Desempenho Financeiro Petrobras 2T26 (1).pdf | ABERTO |
| PETROBRAS | 2025Q4 | DIVIDA_BRUTA | fora do limite de plausibilidade (Desempenho Financeiro Petrobras 4T25.pdf) | ABERTO |
| PETROBRAS | 2025Q4 | DIVIDA_LIQUIDA | confianca 0.65 em Desempenho Financeiro Petrobras 4T25.pdf | ABERTO |
| PETROBRAS | 2025Q4 | LUCRO_LIQUIDO | confianca 0.65 em Desempenho Financeiro Petrobras 4T25.pdf | ABERTO |
| PETROBRAS | 2025Q4 | FCO | confianca 0.65 em Desempenho Financeiro Petrobras 4T25.pdf | ABERTO |
| PETROBRAS | 2025Q4 | FCL | confianca 0.65 em Desempenho Financeiro Petrobras 4T25.pdf | ABERTO |
| PETROBRAS | 2025Q4 | EBITDA_AJUSTADO | confianca 0.65 em Desempenho Financeiro Petrobras 4T25.pdf | ABERTO |
| PETROBRAS | 2025Q4 | RECEITA_LIQUIDA | fora do limite de plausibilidade (Desempenho Financeiro Petrobras 4T25.pdf) | ABERTO |
| PETROBRAS | 2025Q4 | LUCRO_BRUTO | fora do limite de plausibilidade (Desempenho Financeiro Petrobras 4T25.pdf) | ABERTO |
| PETROBRAS | 2025Q4 | DESPESA_OPERACIONAL | confianca 0.65 em Desempenho Financeiro Petrobras 4T25.pdf | ABERTO |
| PETROBRAS | 2026Q2 | DIVIDA_BRUTA | fora do limite de plausibilidade (Desempenho Financeiro da Petrobras 2T26 (em dólar) (1).pdf) | ABERTO |
| PETROBRAS | 2026Q1 | RECEITA_LIQUIDA | fora do limite de plausibilidade (Desempenho Financeiro da Petrobras 1T26 (em dólar).pdf) | ABERTO |
| PETROBRAS | 2025Q4 | LUCRO_BRUTO | fora do limite de plausibilidade (Desempenho Financeiro da Petrobras 4T25 (em dólar).pdf) | ABERTO |
| PETROBRAS | 2025Q4 | DIVIDA_BRUTA | fora do limite de plausibilidade (Desempenho Financeiro da Petrobras 4T25 (em dólar).pdf) | ABERTO |
| EXXONMOBIL | 2025Q4 | CAPEX | confianca 0.65 em 1Q26 Earnings Press Release Website.pdf | ABERTO |
| TOTALENERGIES | 2024Q4 | RECEITA_LIQUIDA | registro ausente (cobertura) | ABERTO |
| CHEVRON | 2026Q2 | QUEBRA_ESTRUTURAL | [P2] FCL: nível muda de 3.93 para 9.68 (+146%) na série | ABERTO |
| EQUINOR | 2026Q2 | QUEBRA_ESTRUTURAL | [P2] LUCRO_LIQUIDO: nível muda de 1.13 para 3.08 (+172%) na série | ABERTO |
| PETROBRAS | 2026Q2 | QUEBRA_ESTRUTURAL | [P2] FCO: nível muda de 18.16 para 10.27 (-43%) na série | ABERTO |
| PETROBRAS | 2026Q2 | QUEBRA_ESTRUTURAL | [P2] LUCRO_LIQUIDO: nível muda de 3.43 para 6.51 (+90%) na série | ABERTO |
| SHELL | 2026Q2 | QUEBRA_ESTRUTURAL | [P2] FCL: nível muda de 7.21 para 10.23 (+42%) na série | ABERTO |
| EXXONMOBIL | 2025Q2 | DRIFT_ZSCORE | [P2] LUCRO_LIQUIDO 2025Q2: valor 7.08 desvia -2.4σ da série anterior | ABERTO |
| EXXONMOBIL | 2026Q1 | DRIFT_ZSCORE | [P2] LUCRO_LIQUIDO 2026Q1: valor 4.18 desvia -5.4σ da série anterior | ABERTO |
| EXXONMOBIL | 2026Q2 | DRIFT_ZSCORE | [P2] LUCRO_LIQUIDO 2026Q2: valor 14.53 desvia +4.4σ da série anterior | ABERTO |
| EXXONMOBIL | 2024Q2 | DRIFT_ZSCORE | [P2] RECEITA_LIQUIDA 2024Q2: valor 93.06 desvia +2.3σ da série anterior | ABERTO |
| EXXONMOBIL | 2026Q2 | DRIFT_ZSCORE | [P2] RECEITA_LIQUIDA 2026Q2: valor 114.53 desvia +7.1σ da série anterior | ABERTO |
| PETROBRAS | 2025Q4 | DRIFT_ZSCORE | [P2] FCO 2025Q4: valor 10.16 desvia -4.9σ da série anterior | ABERTO |
| PETROBRAS | 2026Q1 | DRIFT_ZSCORE | [P2] FCO 2026Q1: valor 8.40 desvia -2.1σ da série anterior | ABERTO |
| PETROBRAS | 2026Q2 | DRIFT_ZSCORE | [P2] LUCRO_BRUTO 2026Q2: valor 19.49 desvia +13.3σ da série anterior | ABERTO |
| PETROBRAS | 2026Q2 | DRIFT_ZSCORE | [P2] LUCRO_LIQUIDO 2026Q2: valor 10.43 desvia +2.7σ da série anterior | ABERTO |
| PETROBRAS | 2026Q2 | DRIFT_ZSCORE | [P2] RECEITA_LIQUIDA 2026Q2: valor 33.61 desvia +11.0σ da série anterior | ABERTO |
| SHELL | 2026Q2 | DRIFT_ZSCORE | [P2] DIVIDA_BRUTA 2026Q2: valor 73.08 desvia -30.2σ da série anterior | ABERTO |
| SHELL | 2026Q2 | DRIFT_ZSCORE | [P2] EBITDA_AJUSTADO 2026Q2: valor 20.71 desvia +2.3σ da série anterior | ABERTO |
| SHELL | 2026Q2 | DRIFT_ZSCORE | [P2] FCL 2026Q2: valor 17.52 desvia +3.7σ da série anterior | ABERTO |
| SHELL | 2025Q1 | DRIFT_ZSCORE | [P2] FCO 2025Q1: valor 9.28 desvia -6.7σ da série anterior | ABERTO |
| SHELL | 2026Q1 | DRIFT_ZSCORE | [P2] FCO 2026Q1: valor 6.06 desvia -2.8σ da série anterior | ABERTO |
| SHELL | 2026Q2 | DRIFT_ZSCORE | [P2] FCO 2026Q2: valor 21.43 desvia +4.1σ da série anterior | ABERTO |
| SHELL | 2026Q2 | DRIFT_ZSCORE | [P2] LUCRO_LIQUIDO 2026Q2: valor 10.82 desvia +4.4σ da série anterior | ABERTO |
| SHELL | 2026Q2 | DRIFT_ZSCORE | [P2] RECEITA_LIQUIDA 2026Q2: valor 94.66 desvia +7.0σ da série anterior | ABERTO |
| TOTALENERGIES | 2025Q2 | DRIFT_ZSCORE | [P2] LUCRO_LIQUIDO 2025Q2: valor 2.75 desvia -2.2σ da série anterior | ABERTO |
| BP | 2026Q1 | DRIFT_ZSCORE | [P2] FCO 2026Q1: valor 2.86 desvia -5.2σ da série anterior | ABERTO |
| BP | 2026Q2 | DRIFT_ZSCORE | [P2] FCO 2026Q2: valor 10.86 desvia +2.5σ da série anterior | ABERTO |
| BP | 2025Q4 | DRIFT_ZSCORE | [P2] LUCRO_LIQUIDO 2025Q4: valor -3.42 desvia -4.8σ da série anterior | ABERTO |
| BP | 2026Q1 | DRIFT_ZSCORE | [P2] RECEITA_LIQUIDA 2026Q1: valor 52.26 desvia +4.8σ da série anterior | ABERTO |
| BP | 2026Q2 | DRIFT_ZSCORE | [P2] RECEITA_LIQUIDA 2026Q2: valor 69.11 desvia +10.7σ da série anterior | ABERTO |
| CHEVRON | 2026Q2 | DRIFT_ZSCORE | [P2] FCL 2026Q2: valor 18.09 desvia +8.3σ da série anterior | ABERTO |
| CHEVRON | 2024Q2 | DRIFT_ZSCORE | [P2] FCO 2024Q2: valor 35.23 desvia +3.4σ da série anterior | ABERTO |
| CHEVRON | 2026Q2 | DRIFT_ZSCORE | [P2] FCO 2026Q2: valor 45.32 desvia +2.5σ da série anterior | ABERTO |
| CHEVRON | 2024Q1 | DRIFT_ZSCORE | [P2] LUCRO_LIQUIDO 2024Q1: valor 5.50 desvia -3.4σ da série anterior | ABERTO |
| CHEVRON | 2024Q2 | DRIFT_ZSCORE | [P2] LUCRO_LIQUIDO 2024Q2: valor 4.44 desvia -3.9σ da série anterior | ABERTO |
| CHEVRON | 2025Q1 | DRIFT_ZSCORE | [P2] LUCRO_LIQUIDO 2025Q1: valor 3.50 desvia -2.4σ da série anterior | ABERTO |
| CHEVRON | 2025Q2 | DRIFT_ZSCORE | [P2] LUCRO_LIQUIDO 2025Q2: valor 2.49 desvia -2.5σ da série anterior | ABERTO |

## Cobertura (fatos por empresa x periodo)

| Empresa | Periodo | Fatos |
|---|---|---|
| BP | 2023Q2 | 3 |
| BP | 2024Q2 | 5 |
| BP | 2025Q2 | 3 |
| BP | 2025Q4 | 5 |
| BP | 2026Q1 | 5 |
| BP | 2026Q2 | 5 |
| CHEVRON | 2023Q1 | 3 |
| CHEVRON | 2023Q2 | 3 |
| CHEVRON | 2023Q3 | 3 |
| CHEVRON | 2024Q1 | 3 |
| CHEVRON | 2024Q2 | 7 |
| CHEVRON | 2024Q3 | 3 |
| CHEVRON | 2025Q1 | 3 |
| CHEVRON | 2025Q2 | 3 |
| CHEVRON | 2025Q3 | 3 |
| CHEVRON | 2025Q4 | 7 |
| CHEVRON | 2026Q1 | 7 |
| CHEVRON | 2026Q2 | 7 |
| EQUINOR | 2023Q1 | 1 |
| EQUINOR | 2023Q2 | 1 |
| EQUINOR | 2023Q3 | 1 |
| EQUINOR | 2023Q4 | 1 |
| EQUINOR | 2024Q1 | 1 |
| EQUINOR | 2024Q2 | 1 |
| EQUINOR | 2024Q3 | 3 |
| EQUINOR | 2024Q4 | 1 |
| EQUINOR | 2025Q2 | 3 |
| EQUINOR | 2025Q3 | 3 |
| EQUINOR | 2025Q4 | 4 |
| EQUINOR | 2026Q1 | 4 |
| EQUINOR | 2026Q2 | 3 |
| EXXONMOBIL | 2023Q1 | 3 |
| EXXONMOBIL | 2023Q2 | 3 |
| EXXONMOBIL | 2023Q3 | 3 |
| EXXONMOBIL | 2024Q1 | 3 |
| EXXONMOBIL | 2024Q2 | 3 |
| EXXONMOBIL | 2024Q3 | 3 |
| EXXONMOBIL | 2025Q1 | 3 |
| EXXONMOBIL | 2025Q2 | 3 |
| EXXONMOBIL | 2025Q3 | 3 |
| EXXONMOBIL | 2025Q4 | 2 |
| EXXONMOBIL | 2026Q1 | 4 |
| EXXONMOBIL | 2026Q2 | 5 |
| PETROBRAS | 2023Q2 | 4 |
| PETROBRAS | 2024Q2 | 4 |
| PETROBRAS | 2025Q2 | 4 |
| PETROBRAS | 2025Q4 | 10 |
| PETROBRAS | 2026Q1 | 10 |
| PETROBRAS | 2026Q2 | 10 |
| SHELL | 2023Q1 | 3 |
| SHELL | 2023Q2 | 3 |
| SHELL | 2024Q1 | 3 |
| SHELL | 2024Q2 | 9 |
| SHELL | 2025Q1 | 3 |
| SHELL | 2025Q2 | 3 |
| SHELL | 2025Q4 | 9 |
| SHELL | 2026Q1 | 9 |
| SHELL | 2026Q2 | 9 |
| TOTALENERGIES | 2023Q1 | 2 |
| TOTALENERGIES | 2023Q2 | 2 |
| TOTALENERGIES | 2024Q1 | 2 |
| TOTALENERGIES | 2024Q2 | 2 |
| TOTALENERGIES | 2025Q1 | 2 |
| TOTALENERGIES | 2025Q2 | 2 |
| TOTALENERGIES | 2025Q4 | 8 |
| TOTALENERGIES | 2026Q1 | 8 |
| TOTALENERGIES | 2026Q2 | 8 |
