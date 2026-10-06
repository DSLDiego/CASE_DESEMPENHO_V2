# Premissas, decisões e limitações

## Premissas tecnológicas
1. Python 3.12+ com SQLite (WAL) — zero servidor de BD, custo operacional mínimo.
2. ETL offline-first sobre o Container local; SEC EDGAR/PTAX são online-opcionais com fallback.
3. Moeda do painel: USD bilhões (PTAX de fechamento; fallback tabelado).
4. Valores trimestrais priorizados; semestrais (`1S26`) guardados com `trimestre=0`.

## Premissas financeiras
1. 11 indicadores: os 6 originais (RECEITA_LIQUIDA, EBITDA_AJUSTADO, LUCRO_LIQUIDO, FCO,
   DIVIDA_LIQUIDA + EFETIVO_TOTAL) e mais 5 na matriz expandida — CAPEX (módulo do outflow),
   DIVIDA_BRUTA, LUCRO_BRUTO, FCL e DESPESA_OPERACIONAL (sinal como reportado).
2. Pares: Shell, BP, Chevron, ExxonMobil, TotalEnergies, Equinor (universo cheio do case).
3. Períodos: 2023Q1–2026Q2 no banco (14 trimestres). O Container local traz 2025-2026;
   2023-2024 são preenchidos por SEC EDGAR XBRL (`sec --periodos 2023Q1 ... 2024Q4`),
   e os testes de download/extração de 4 anos reportam `skip` explícito para os anos
   sem pasta local, cobrindo esses anos via `test_sec_download_real_4_anos`.
4. Escala: "US$ milhões"→÷1000; "USD bi"→direto. Dívida líquida pontual (estoque), demais fluxo do trimestre.
5. Efetivo: RIs trimestrais não publicam headcount → âncoras anuais auditadas
   (`models/seed_efetivo.py`, 9 âncoras 2024A/2025A de relatórios oficiais, ex.:
   Petrobras 49.000 no 20-F 2024, TotalEnergies 102.887 em 2024). Série trimestral
   segue ausente e registrada na fila de revisão. Definições variam por empresa
   (próprios vs. total); ver aba "Efetivo" do painel.

## Decisões
1. PDFs de transcript/slides: catalogados, mas não parseados em profundidade (custo/benefício).
2. Conflito RI × SEC: prevalece RI (fonte primária); divergência >15% vira alerta
   DIVERGENCIA_FONTE (ex.: FCO Chevron 2T26 RI=45,32 x SEC=25,15). SEC só preenche lacunas.
3. Itens anuais XBRL (FY/20-F) nunca viram trimestre (caso Equinor 2025: US$ 106 bi anual).
4. Confiança <0.70 não entra no fato — vai para revisão humana; fato bom nunca é
   rebaixado por extração pior (prioridade de confiança + preferência USD).
5. CIK da BP corrigido para 0000313807 (o valor 0000313801 retorna 404 na SEC).
6. PDFs: key-figures em múltiplos blocos por documento; frases de release em 3 níveis
   (com trimestre explícito, com âncora "in the X quarter", copulares com período do
   documento). Footnotes `(1)` e adjusting/identified items nunca viram fato.
7. TotalEnergies: receita via "Revenues from sales" do databook; dívida bruta parcial
   (borrowings) não carregada como bruta total — gap documentado na revisão.
8. EPS: "$X bi, or $Y per share" carrega lucro GAAP; "excluding/adjusted" é descartado.
9. Moeda de exibição: base USD bi; toggle BRL usa PTAX de fechamento do trimestre
   (2024Q2: 5,20 · 2025Q4: 5,40 · 2026Q1: 5,26 · 2026Q2: 5,05 — API BCB com fallback).
   Leitura executiva permanece em USD; efetivo sempre em pessoas.

## Limitações conhecidas
1. Parsers genéricos podem errar em layouts novos → fila de revisão cobre.
2. Sem FX intradiário: conversão usa fechamento do trimestre.
3. Equinor: sem databook Excel no Container; fatos vêm do bloco "key figures" dos PDFs
   (lucro + FCO) e da SEC quando houver 6-K trimestral com frame.
4. GUI exige PySide6 instalado; Web exige CDN Plotly (ou use os PNGs do relatório).
5. 2023-2024 sem documentos locais: sem PDF/XLSX do Container, a extração desses anos
   depende da SEC (frames XBRL) — 4 rubricas em 2023 (receita, lucro, lucro bruto, FCO)
   contra 10 em 2024/2025/2026. A ausência é registrada como limitação, não estimada.
6. RIs sem API JSON pública (Equinor, Petrobras, Shell, BP, TotalEnergies, Chevron,
   Exxon): o consumo é por arquivo/parser. `fontes api` registra "SEM (status)" em
   `api_json` para deixar a tentativa explícita e auditável.
7. `DELETE` de fonte zera `id_fonte` dos fatos (não apaga histórico); para apagar
   histórico é preciso `reset` + novo ETL.
8. "Não baixado" ≠ "erro": das 798 fontes catalogadas, 668 são links de RI/Investidor10
   ainda não baixados (`NAO_BAIXADO`) e 48 são PDFs pulados por regra
   (`transcript`/`slides`). Só `ERRO` entra no contador de falha — por isso o painel de
   gestão do ETL mostra 0 erros mesmo com a maior parte das fontes em aberto.
9. `SEM_DADOS` significa "parseou, mas nenhum período-alvo foi extraído" (documento
   institucional, Release sem números do trimestre, etc.). O motivo fica gravado na
   coluna `erro` para não se perder a informação.
10. **Projeção não é previsão de preço nem de resultado**: é continuação do padrão
    trimestral da série. As regras fixas para séries curtas são deliberadamente
    conservadoras — 1 dado → repete o valor com intervalo **±15%** (confiança 0,25);
    2–5 dados → **média ± 2 desvios-padrão** (confiança 0,35–0,50). Com 6+ pontos o método
    é escolhido por backtesting e o IC95 alarga com o horizonte. Uso correto: cenários e
    planejamento; a decisão humana continua obrigatória.
11. A projeção vive em `tb_projecao` e **nunca** alimenta `tb_fato_financeiro`, a matriz
    comparativa nem o e-mail de benchmark — assim nenhum número projetado é confundido
    com dado publicado.
12. O DQS é uma **regra interna**, não uma certificação externa: os pesos (Completude 30,
    Plausibilidade 25, Consistência 15, Rastreabilidade 15, Tempestividade 15) e os
    limiares de alerta são escolha de projeto, registrados em `tb_regra_alerta` para
    recalibração. Na base atual o DQS médio é 75,4 — puxado para baixo pela completude
    (40,4%), não por erro de extração (plausibilidade 98,5 e rastreabilidade 100).
