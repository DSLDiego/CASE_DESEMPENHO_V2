# Catalogo de fontes utilizadas (gerado pelo ETL)

Total de arquivos catalogados: **798** (130 do Container + cache SEC, se houver).
Origem: portais oficiais de Relacoes com Investidores (ver `RI_URLS` em `workers/scanner.py`) + arquivos locais do Container.
Rastreabilidade: cada fato carrega `id_fonte`; catalogos-espelho em `data/sources_catalog.json` e `.csv`.

## Por empresa x tipo x status

| Empresa | Tipo | Status | Qtd |
|---|---|---|---|
| BP | DOC | NAO_BAIXADO | 1 |
| BP | HTML | NAO_BAIXADO | 1 |
| BP | JSON | NAO_BAIXADO | 1 |
| BP | PDF | NAO_PROCESSADO | 8 |
| BP | PDF | SEM_DADOS | 10 |
| BP | XLSX | PROCESSADO | 3 |
| CHEVRON | DOC | NAO_BAIXADO | 2 |
| CHEVRON | HTML | NAO_BAIXADO | 1 |
| CHEVRON | JSON | NAO_BAIXADO | 1 |
| CHEVRON | PDF | NAO_PROCESSADO | 9 |
| CHEVRON | PDF | SEM_DADOS | 3 |
| CHEVRON | XLSX | PROCESSADO | 3 |
| EQUINOR | DOC | NAO_BAIXADO | 1 |
| EQUINOR | HTML | NAO_BAIXADO | 1 |
| EQUINOR | JSON | NAO_BAIXADO | 1 |
| EQUINOR | PDF | NAO_PROCESSADO | 6 |
| EQUINOR | PDF | PROCESSADO | 3 |
| EXXONMOBIL | DOC | NAO_BAIXADO | 1 |
| EXXONMOBIL | HTML | NAO_BAIXADO | 1 |
| EXXONMOBIL | JSON | NAO_BAIXADO | 1 |
| EXXONMOBIL | PDF | NAO_BAIXADO | 318 |
| EXXONMOBIL | PDF | NAO_PROCESSADO | 7 |
| EXXONMOBIL | PDF | PROCESSADO | 3 |
| EXXONMOBIL | PDF | SEM_DADOS | 10 |
| EXXONMOBIL | XLSX | NAO_BAIXADO | 50 |
| EXXONMOBIL | XLSX | PROCESSADO | 1 |
| EXXONMOBIL | XLSX | SEM_DADOS | 2 |
| PETROBRAS | DOC | NAO_BAIXADO | 1 |
| PETROBRAS | HTML | NAO_BAIXADO | 1 |
| PETROBRAS | JSON | NAO_BAIXADO | 1 |
| PETROBRAS | PDF | NAO_PROCESSADO | 5 |
| PETROBRAS | PDF | PROCESSADO | 2 |
| PETROBRAS | PDF | SEM_DADOS | 13 |
| PETROBRAS | XLSX | PROCESSADO | 3 |
| PETROBRAS | XLSX | SEM_DADOS | 3 |
| SHELL | DOC | NAO_BAIXADO | 1 |
| SHELL | HTML | NAO_BAIXADO | 1 |
| SHELL | JSON | NAO_BAIXADO | 1 |
| SHELL | PDF | NAO_PROCESSADO | 9 |
| SHELL | PDF | PROCESSADO | 3 |
| SHELL | PDF | SEM_DADOS | 3 |
| SHELL | XLSX | PROCESSADO | 3 |
| TOTALENERGIES | DOC | NAO_BAIXADO | 1 |
| TOTALENERGIES | HTML | NAO_BAIXADO | 1 |
| TOTALENERGIES | JSON | NAO_BAIXADO | 1 |
| TOTALENERGIES | PDF | NAO_BAIXADO | 263 |
| TOTALENERGIES | PDF | NAO_PROCESSADO | 4 |
| TOTALENERGIES | PDF | SEM_DADOS | 11 |
| TOTALENERGIES | XLSX | NAO_BAIXADO | 15 |
| TOTALENERGIES | XLSX | PROCESSADO | 3 |

## Arquivos com dados extraidos (amostra, 30 primeiros PROCESSADO)

| ID | Empresa | Arquivo | Download |
|---|---|---|---|
| 1979 | BP | bp-fourth-quarter-2025-results-group-databook.xlsx | 2026-10-04 20:54:28 |
| 1986 | BP | bp-first-quarter-2026-results-group-databook.xlsx | 2026-10-04 20:54:29 |
| 1992 | BP | bp-second-quarter-2026-results-group-databook.xlsx | 2026-10-04 20:54:30 |
| 2003 | CHEVRON | 2025_4q_data_supplement.xlsx | 2026-10-04 20:54:30 |
| 2004 | CHEVRON | 2026 1Q Data Supplement.xlsx | 2026-10-04 20:54:30 |
| 2010 | CHEVRON | 2026_2q_data_supplement.xlsx | 2026-10-04 20:54:31 |
| 2016 | EQUINOR | financial-statements-and-review-q4-2025-equinor.pdf | 2026-10-04 20:54:31 |
| 2019 | EQUINOR | q1-2026-financial-statements-and-review-equinor.pdf | 2026-10-04 20:54:32 |
| 2022 | EQUINOR | q2-2026-financial-statements-and-review-equinor.pdf | 2026-10-04 20:54:32 |
| 2024 | EXXONMOBIL | 4Q25 Earnings Press Release Website.pdf | 2026-10-04 20:54:32 |
| 2040 | EXXONMOBIL | 2Q26 Earnings Release Website.pdf | 2026-10-04 20:54:33 |
| 2042 | EXXONMOBIL | 2Q26 Prepared Remarks.pdf | 2026-10-04 20:54:33 |
| 2045 | EXXONMOBIL | Earning Release Supplement Data - Excel Version.xlsx | 2026-10-04 20:54:34 |
| 2051 | PETROBRAS | Excel 4T25 USD.xlsx | 2026-10-04 20:54:34 |
| 2059 | PETROBRAS | Excel 1T26 USD.xlsx | 2026-10-04 20:54:35 |
| 2060 | PETROBRAS | Relatório de Produção de Vendas 1T26.pdf | 2026-10-04 20:54:35 |
| 2067 | PETROBRAS | Excel 2T26 USD.xlsx | 2026-10-04 20:54:35 |
| 2068 | PETROBRAS | Relatório de Produção e Vendas 2T26.pdf | 2026-10-04 20:54:35 |
| 2073 | SHELL | q4-2025-quarterly-databook.xlsx | 2026-10-04 20:54:35 |
| 2074 | SHELL | q4-2025-quarterly-press-release.pdf | 2026-10-04 20:54:35 |
| 2079 | SHELL | q1-2026-quarterly-databook.xlsx | 2026-10-04 20:54:36 |
| 2080 | SHELL | q1-2026-quarterly-press-release.pdf | 2026-10-04 20:54:36 |
| 2085 | SHELL | q2-2026-quarterly-databook.xlsx | 2026-10-04 20:54:36 |
| 2086 | SHELL | q2-2026-quarterly-press-release.pdf | 2026-10-04 20:54:36 |
| 2093 | TOTALENERGIES | totalenergies_databook-q4-2025_2026_en.xlsx | 2026-10-04 20:54:37 |
| 2098 | TOTALENERGIES | totalenergies_1q26-results-databook_2026.xlsx | 2026-10-04 20:54:37 |
| 2104 | TOTALENERGIES | totalenergies_databook-results-2q26_2026_en.xlsx | 2026-10-04 20:54:37 |
