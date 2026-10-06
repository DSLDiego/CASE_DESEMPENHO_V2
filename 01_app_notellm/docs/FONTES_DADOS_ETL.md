# Fontes de informação usadas no ETL

Inventário de **de onde vem cada número** do PetroAnalytics. Duas famílias:
fonte **primária** (a própria companhia publica) e fonte **secundária
estruturada** (a SEC publica o mesmo número em XBRL, o que serve de conferência).

Regra de ouro do projeto: um fato só entra em `tb_fato_financeiro` com
`id_fonte`, `confianca` e `data_atualizacao`. Não existe número sem procedência.

---

## 1. Fonte primária — releases e demonstrações do Relationado com Investidores

Documentos baixados para `03_Conteiner\<EMPRESA>\<PERÍDO>\` e catalogados por
SHA-256 (136 PDFs + 27 planilhas no acervo atual).

| Empresa | Documentos no acervo | Onde busca |
|---|---|---|
| **Petrobras** | 65 | `investidorpetrobras.com.br` — demonstrações financeiras (USD e R$), ITR, relatório fiscal, relatório de produção e vendas, "Desempenho Financeiro" (dólar e reais), planilhas de resultados |
| **Shell** | 18 | `shell.com/investors` — quarterly databook (`.xls`), resultados, demonstrações financeiras, apresentações |
| **BP** | 21 | `bp.com/investors` — quarterly results, results presentation e supplement, databook |
| **Chevron** | 15 | `chevron.com/investors` — earnings release, data supplement (`.xlsx`) |
| **ExxonMobil** | 23 | `investor.exxonmobil.com` — earnings release, supplement data |
| **TotalEnergies** | 18 | `totalenergies.com/investors` — databook, results,Half-year financial report |
| **Equinor** | 9 | `equinor.com/investors` — quarterly report, results |

Formatos processados e como são lidos:

| Formato | Parser | Observação |
|---|---|---|
| PDF | PyMuPDF (texto) + `find_tables` → fallback pdfplumber | CSV/planilha embutida no PDF também entra |
| XLSX / XLS / XLSM / CSV | `parse_tab` | detecta `;`, vírgula, tab e pipe |
| HTML (comunicado 6-K) | `parse_html` | reaproveita a heurística de frase do PDF |
| DOCX / TXT | `parse_txt` | rare no acervo |

**Normalização de nomes (regex).** O acervo tem nomes hostis
(`_Demonstrações Financeiras 1T26  - US$.pdf`, `Transcrição 1T25.pdf`,
`DFS R$ Português.pdf`, `Relatório Fiscal 3Q25.pdf`). A decisão de parsear é feita
sobre o nome normalizado: narrativos (transcrição, slides, remarks, webcast) são
catalogados mas **não** entram no ETL numérico; documentos com tabela entram.

**Cotações de mercado:** snapshot do Investidor10 (`coleta --mercado`) alimenta
`COTACAO`, `DIVIDEND_YIELD` e `P_L`.

## 2. Fonte secundária estruturada — SEC EDGAR

| API | Uso | Endereço |
|---|---|---|
| **companyfacts (XBRL)** | números estruturados por tag, com `frame` trimestral | `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json` |
| **submissions** | que formulário foi protocolado, `reportDate`, `items`, flag XBRL | `data.sec.gov/submissions/CIK{cik}.json` |
| **Archives** | documento protocolado (6-K, 10-Q) | `sec.gov/Archives/edgar/data/...` |

CIKs em uso (`config.COMPANIES`):

| Empresa | CIK | Formulários |
|---|---|---|
| Petrobras | 0001119639 | 6-K (emissor estrangeiro) |
| Shell | 0001306965 | 6-K |
| BP | 0000313807 | 6-K |
| Chevron | 0000093410 | 10-Q, 8-K |
| ExxonMobil | 0000034088 | 10-Q, 8-K |
| TotalEnergies | 0000879764 | 6-K |
| Equinor | 0001140625 | 6-K |

Mapeamento de tags XBRL → rubrica canônica (`workers/sec_edgar.py`):
`Revenues`/`SalesRevenueNet`/`ifrs:Revenue` → `RECEITA_LIQUIDA` · `GrossProfit` →
`LUCRO_BRUTO` · `NetIncomeLoss`/`ProfitLoss` → `LUCRO_LIQUIDO` ·
`NetCashProvidedByUsedInOperatingActivities`/`CashFlowsFromUsedInOperatingActivities` → `FCO`.

**Regra de conflito:** quando existe fato em USD direto (RI), a conversão de BRL
**não** sobrescreve; e um fato existente com confiança maior nunca é rebaixado por
uma extração pior. Por isso o SEC entra como conferência e preenchimento de lacuna,
não como fonte dominante.

**Correção registrada:** o CIK da BP foi `0000313801` (404) e passou a
`0000313807`; o da Petrobras, `0001119639`.

## 3. Quem gerou mais fatos (auditoria de procedência)

| Fatos | Fonte | Empresa | Documento |
|---|---|---|---|
| 36 | RI | Shell | `q2-2026-quarterly-databook.xls` |
| 30 | SEC XBRL | ExxonMobil | `companyfacts CIK0000034088` |
| 28 | RI | Chevron | `2026_2q_data_supplement.xlsx` |
| 24 | SEC XBRL | Chevron | `companyfacts CIK0000093410` |
| 20 | RI | Petrobras | `Excel 2T26 USD.xlsx` |
| 20 | RI | BP | `bp-second-quarter-2026-results-*` |
| 16 | SEC XBRL | Equinor | `companyfacts CIK0001140625` |
| 16 | RI | TotalEnergies | `totalenergies_databook-results-*` |
| 15 | SEC XBRL | Shell | `companyfacts CIK0001306965` |
| 12 | SEC XBRL | TotalEnergies | `companyfacts CIK0000879764` |

## 4. Conversão de moeda

- Moeda de origem detectada **por regex** no nome (`US$`, `R$`, "em dólar", "reais"),
  não por substring.
- BRL → USD usa **PTAX de fechamento do trimestre** (`config.PTAX_FALLBACK`),
  com fallback quando a série não existe.
- Fato em BRL entra com confiança **−0,05** e nunca sobrepõe fato em USD.

## 5. Fontes discovery (descoberta, não carga)

- `data.sec.gov/submissions` — lista o que foi protocolado; é o canal confiável de
  "o que acabou de sair".
- Páginas de RI — tentativas automatizadas; na prática Chevron e BP devolvem
  **HTTP 403** e Petrobras/Equinor usam página dinâmica, então a descoberta por RI
  retorna 0 documentos nesses casos e o relatório diz isso explicitamente.
- O documento principal de um 6-K é a **capa**; as demonstrações estão nos anexos
  e o número estruturado chega pelo `companyfacts` — é o que o relatório de
  lacuna aponta.

## 6. Fontes *não* usadas (e por quê)

| Fonte | Motivo |
|---|---|
| MinerU, PDF-Extract-Kit | OCR/layout com múltiplos GB de PyTorch; o acervo já tem camada de texto (285 mil caracteres extraídos do MuPDF) |
| FlaxPDF, Xournal++ | São viewers/annotadores, não extratores — servem para conferência visual, não para alimentar o ETL |
| Speeedy, QuickReaderPDF | Leitura humana (RSVP, biónica): não produz dado estruturado |
| Dados de terceiros não oficiais | Não há provenance nem consistência auditável |

## 7. Limites conhecidos

- **Histórico**: o Container local tem sobretudo 2025–2026; 2023–2024 vêm da SEC.
  Os 2 testes ignorados são exatamente por isso.
- **RI automatizado**: bloqueado (403) em Chevron/BP e dinâmico em Petrobras/Equinor.
- **Cobertura de rubricas por empresa** é desigual (ex.: `LUCRO_BRUTO` só tem série
  da Petrobras) — a completude por dimensão no DQS existe justamente para tornar
  isso visível em vez de esconder.
