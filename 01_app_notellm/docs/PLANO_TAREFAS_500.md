# Plano de execucao — 520 tarefas

Formato `[Gx-Ay-Tnnn]`. Status PoC (out/2026): G1–G6 **executados** pelo ETL real
(138 fontes, 123 fatos, 29 alertas, 7/7 empresas × 3 trimestres); G7–G8 **validados**
por build do painel + pytest 16/16 + GUI offscreen (4 abas). Itens abaixo seguem como
roadmap de endurecimento ( `. ` marcados [x] = núcleo já coberto por teste ou ETL).

## G1 — Fundacao e Model SQLite (70 tarefas)

### G1-A1
- [ ] [G1-A1-T001] Testar: tabela tb_fato_financeiro.
- [ ] [G1-A1-T002] Revisar: tabela tb_fato_operacional.
- [ ] [G1-A1-T003] Documentar: tabela tb_quality_alerts.
- [ ] [G1-A1-T004] Otimizar: tabela tb_review_queue.
- [ ] [G1-A1-T005] Validar: indice idx_fato_emp_per.
- [ ] [G1-A1-T006] Implementar: singleton DatabaseManager thread-safe.
- [ ] [G1-A1-T007] Testar: modo WAL.
- [ ] [G1-A1-T008] Revisar: FonteRepository.registrar idempotente.
- [ ] [G1-A1-T009] Documentar: FonteRepository.exportar json/csv.
- [ ] [G1-A1-T010] Otimizar: FonteRepository.verificar_integridade.

### G1-A2
- [ ] [G1-A2-T011] Validar: FatoRepository.upsert.
- [ ] [G1-A2-T012] Implementar: FatoRepository.matriz/evoulcao.
- [ ] [G1-A2-T013] Testar: QualityRepository.alertar/para_revisao.
- [ ] [G1-A2-T014] Revisar: reset do banco.
- [ ] [G1-A2-T015] Documentar: migracao de schema.
- [ ] [G1-A2-T016] Otimizar: backup do .db.
- [ ] [G1-A2-T017] Validar: timeout de conexao.
- [ ] [G1-A2-T018] Implementar: tabela tb_fonte_dados (hash UNIQUE).
- [ ] [G1-A2-T019] Testar: tabela tb_depara_rubrica.
- [ ] [G1-A2-T020] Revisar: tabela tb_fato_financeiro.

### G1-A3
- [ ] [G1-A3-T021] Documentar: tabela tb_quality_alerts.
- [ ] [G1-A3-T022] Otimizar: tabela tb_review_queue.
- [ ] [G1-A3-T023] Validar: indice idx_fato_emp_per.
- [ ] [G1-A3-T024] Implementar: singleton DatabaseManager thread-safe.
- [ ] [G1-A3-T025] Testar: modo WAL.
- [ ] [G1-A3-T026] Revisar: FonteRepository.registrar idempotente.
- [ ] [G1-A3-T027] Documentar: FonteRepository.exportar json/csv.
- [ ] [G1-A3-T028] Otimizar: FonteRepository.verificar_integridade.
- [ ] [G1-A3-T029] Validar: DeParaRepository cache.
- [ ] [G1-A3-T030] Implementar: FatoRepository.upsert.

### G1-A4
- [ ] [G1-A4-T031] Testar: QualityRepository.alertar/para_revisao.
- [ ] [G1-A4-T032] Revisar: reset do banco.
- [ ] [G1-A4-T033] Documentar: migracao de schema.
- [ ] [G1-A4-T034] Otimizar: backup do .db.
- [ ] [G1-A4-T035] Validar: timeout de conexao.
- [ ] [G1-A4-T036] Implementar: tabela tb_fonte_dados (hash UNIQUE).
- [ ] [G1-A4-T037] Testar: tabela tb_depara_rubrica.
- [ ] [G1-A4-T038] Revisar: tabela tb_fato_financeiro.
- [ ] [G1-A4-T039] Documentar: tabela tb_fato_operacional.
- [ ] [G1-A4-T040] Otimizar: tabela tb_quality_alerts.

### G1-A5
- [ ] [G1-A5-T041] Validar: indice idx_fato_emp_per.
- [ ] [G1-A5-T042] Implementar: singleton DatabaseManager thread-safe.
- [ ] [G1-A5-T043] Testar: modo WAL.
- [ ] [G1-A5-T044] Revisar: FonteRepository.registrar idempotente.
- [ ] [G1-A5-T045] Documentar: FonteRepository.exportar json/csv.
- [ ] [G1-A5-T046] Otimizar: FonteRepository.verificar_integridade.
- [ ] [G1-A5-T047] Validar: DeParaRepository cache.
- [ ] [G1-A5-T048] Implementar: FatoRepository.upsert.
- [ ] [G1-A5-T049] Testar: FatoRepository.matriz/evoulcao.
- [ ] [G1-A5-T050] Revisar: QualityRepository.alertar/para_revisao.

### G1-A6
- [ ] [G1-A6-T051] Documentar: migracao de schema.
- [ ] [G1-A6-T052] Otimizar: backup do .db.
- [ ] [G1-A6-T053] Validar: timeout de conexao.
- [ ] [G1-A6-T054] Implementar: tabela tb_fonte_dados (hash UNIQUE).
- [ ] [G1-A6-T055] Testar: tabela tb_depara_rubrica.
- [ ] [G1-A6-T056] Revisar: tabela tb_fato_financeiro.
- [ ] [G1-A6-T057] Documentar: tabela tb_fato_operacional.
- [ ] [G1-A6-T058] Otimizar: tabela tb_quality_alerts.
- [ ] [G1-A6-T059] Validar: tabela tb_review_queue.
- [ ] [G1-A6-T060] Implementar: indice idx_fato_emp_per.

### G1-A7
- [ ] [G1-A7-T061] Testar: modo WAL.
- [ ] [G1-A7-T062] Revisar: FonteRepository.registrar idempotente.
- [ ] [G1-A7-T063] Documentar: FonteRepository.exportar json/csv.
- [ ] [G1-A7-T064] Otimizar: FonteRepository.verificar_integridade.
- [ ] [G1-A7-T065] Validar: DeParaRepository cache.
- [ ] [G1-A7-T066] Implementar: FatoRepository.upsert.
- [ ] [G1-A7-T067] Testar: FatoRepository.matriz/evoulcao.
- [ ] [G1-A7-T068] Revisar: QualityRepository.alertar/para_revisao.
- [ ] [G1-A7-T069] Documentar: reset do banco.
- [ ] [G1-A7-T070] Otimizar: migracao de schema.

## G2 — De-Para e normalizacao (60 tarefas)

### G2-A1
- [ ] [G2-A1-T071] Validar: preferencia USD sobre conversao.
- [ ] [G2-A1-T072] Implementar: prioridade de confianca na sobrescrita.
- [ ] [G2-A1-T073] Testar: normalizacao Mboed->kboed.
- [ ] [G2-A1-T074] Revisar: limites de plausibilidade por rubrica.
- [ ] [G2-A1-T075] Documentar: re-escala automatica /1000.
- [ ] [G2-A1-T076] Otimizar: seed de de-para por empresa.
- [ ] [G2-A1-T077] Validar: normalizacao unicode.
- [ ] [G2-A1-T078] Implementar: teste de resolve() PT/EN.
- [ ] [G2-A1-T079] Testar: regra RECEITA_LIQUIDA PT/EN.
- [ ] [G2-A1-T080] Revisar: regra EBITDA_AJUSTADO.

### G2-A2
- [ ] [G2-A2-T081] Documentar: regra FCO/FCL.
- [ ] [G2-A2-T082] Otimizar: regra DIVIDA_LIQUIDA/BRUTA.
- [ ] [G2-A2-T083] Validar: regra EFETIVO_TOTAL.
- [ ] [G2-A2-T084] Implementar: regra PRODUCAO_BOED/FUT_REFINO.
- [ ] [G2-A2-T085] Testar: word-boundary em SG&A.
- [ ] [G2-A2-T086] Revisar: skip de per-share.
- [ ] [G2-A2-T087] Documentar: skip de contribution-of.
- [ ] [G2-A2-T088] Otimizar: conversao BRL->USD via PTAX.
- [ ] [G2-A2-T089] Validar: fallback PTAX_FALLBACK.
- [ ] [G2-A2-T090] Implementar: preferencia USD sobre conversao.

### G2-A3
- [ ] [G2-A3-T091] Testar: normalizacao Mboed->kboed.
- [ ] [G2-A3-T092] Revisar: limites de plausibilidade por rubrica.
- [ ] [G2-A3-T093] Documentar: re-escala automatica /1000.
- [ ] [G2-A3-T094] Otimizar: seed de de-para por empresa.
- [ ] [G2-A3-T095] Validar: normalizacao unicode.
- [ ] [G2-A3-T096] Implementar: teste de resolve() PT/EN.
- [ ] [G2-A3-T097] Testar: regra RECEITA_LIQUIDA PT/EN.
- [ ] [G2-A3-T098] Revisar: regra EBITDA_AJUSTADO.
- [ ] [G2-A3-T099] Documentar: regra LUCRO_LIQUIDO.
- [ ] [G2-A3-T100] Otimizar: regra FCO/FCL.

### G2-A4
- [ ] [G2-A4-T101] Validar: regra EFETIVO_TOTAL.
- [ ] [G2-A4-T102] Implementar: regra PRODUCAO_BOED/FUT_REFINO.
- [ ] [G2-A4-T103] Testar: word-boundary em SG&A.
- [ ] [G2-A4-T104] Revisar: skip de per-share.
- [ ] [G2-A4-T105] Documentar: skip de contribution-of.
- [ ] [G2-A4-T106] Otimizar: conversao BRL->USD via PTAX.
- [ ] [G2-A4-T107] Validar: fallback PTAX_FALLBACK.
- [ ] [G2-A4-T108] Implementar: preferencia USD sobre conversao.
- [ ] [G2-A4-T109] Testar: prioridade de confianca na sobrescrita.
- [ ] [G2-A4-T110] Revisar: normalizacao Mboed->kboed.

### G2-A5
- [ ] [G2-A5-T111] Documentar: re-escala automatica /1000.
- [ ] [G2-A5-T112] Otimizar: seed de de-para por empresa.
- [ ] [G2-A5-T113] Validar: normalizacao unicode.
- [ ] [G2-A5-T114] Implementar: teste de resolve() PT/EN.
- [ ] [G2-A5-T115] Testar: regra RECEITA_LIQUIDA PT/EN.
- [ ] [G2-A5-T116] Revisar: regra EBITDA_AJUSTADO.
- [ ] [G2-A5-T117] Documentar: regra LUCRO_LIQUIDO.
- [ ] [G2-A5-T118] Otimizar: regra FCO/FCL.
- [ ] [G2-A5-T119] Validar: regra DIVIDA_LIQUIDA/BRUTA.
- [ ] [G2-A5-T120] Implementar: regra EFETIVO_TOTAL.

### G2-A6
- [ ] [G2-A6-T121] Testar: word-boundary em SG&A.
- [ ] [G2-A6-T122] Revisar: skip de per-share.
- [ ] [G2-A6-T123] Documentar: skip de contribution-of.
- [ ] [G2-A6-T124] Otimizar: conversao BRL->USD via PTAX.
- [ ] [G2-A6-T125] Validar: fallback PTAX_FALLBACK.
- [ ] [G2-A6-T126] Implementar: preferencia USD sobre conversao.
- [ ] [G2-A6-T127] Testar: prioridade de confianca na sobrescrita.
- [ ] [G2-A6-T128] Revisar: normalizacao Mboed->kboed.
- [ ] [G2-A6-T129] Documentar: limites de plausibilidade por rubrica.
- [ ] [G2-A6-T130] Otimizar: re-escala automatica /1000.

## G3 — Coleta e scanner (60 tarefas)

### G3-A1
- [ ] [G3-A1-T131] Validar: filtro form 10-Q/10-K/20-F.
- [ ] [G3-A1-T132] Implementar: conversao XBRL para USD bi.
- [ ] [G3-A1-T133] Testar: cache SEC_*.json.
- [ ] [G3-A1-T134] Revisar: tratamento HTTP 403/429.
- [ ] [G3-A1-T135] Documentar: timeout SEC.
- [ ] [G3-A1-T136] Otimizar: cross-check RI x SEC.
- [ ] [G3-A1-T137] Validar: coleta por empresa.
- [ ] [G3-A1-T138] Implementar: log de coleta.
- [ ] [G3-A1-T139] Testar: mapeamento RI_URLS por empresa.
- [ ] [G3-A1-T140] Revisar: tabela CIKs (7 empresas).

### G3-A2
- [ ] [G3-A2-T141] Documentar: empresa_do_caminho.
- [ ] [G3-A2-T142] Otimizar: hash SHA-256 em chunks.
- [ ] [G3-A2-T143] Validar: deteccao de duplicados.
- [ ] [G3-A2-T144] Implementar: registro CATALOGADO.
- [ ] [G3-A2-T145] Testar: pasta ausente (aviso).
- [ ] [G3-A2-T146] Revisar: User-Agent SEC obrigatorio.
- [ ] [G3-A2-T147] Documentar: throttle 0.25s SEC.
- [ ] [G3-A2-T148] Otimizar: endpoint companyfacts.
- [ ] [G3-A2-T149] Validar: mapeamento XBRL->canonico.
- [ ] [G3-A2-T150] Implementar: filtro form 10-Q/10-K/20-F.

### G3-A3
- [ ] [G3-A3-T151] Testar: cache SEC_*.json.
- [ ] [G3-A3-T152] Revisar: tratamento HTTP 403/429.
- [ ] [G3-A3-T153] Documentar: timeout SEC.
- [ ] [G3-A3-T154] Otimizar: cross-check RI x SEC.
- [ ] [G3-A3-T155] Validar: coleta por empresa.
- [ ] [G3-A3-T156] Implementar: log de coleta.
- [ ] [G3-A3-T157] Testar: mapeamento RI_URLS por empresa.
- [ ] [G3-A3-T158] Revisar: tabela CIKs (7 empresas).
- [ ] [G3-A3-T159] Documentar: EXT_TIPO por extensao.
- [ ] [G3-A3-T160] Otimizar: empresa_do_caminho.

### G3-A4
- [ ] [G3-A4-T161] Validar: deteccao de duplicados.
- [ ] [G3-A4-T162] Implementar: registro CATALOGADO.
- [ ] [G3-A4-T163] Testar: pasta ausente (aviso).
- [ ] [G3-A4-T164] Revisar: User-Agent SEC obrigatorio.
- [ ] [G3-A4-T165] Documentar: throttle 0.25s SEC.
- [ ] [G3-A4-T166] Otimizar: endpoint companyfacts.
- [ ] [G3-A4-T167] Validar: mapeamento XBRL->canonico.
- [ ] [G3-A4-T168] Implementar: filtro form 10-Q/10-K/20-F.
- [ ] [G3-A4-T169] Testar: conversao XBRL para USD bi.
- [ ] [G3-A4-T170] Revisar: cache SEC_*.json.

### G3-A5
- [ ] [G3-A5-T171] Documentar: timeout SEC.
- [ ] [G3-A5-T172] Otimizar: cross-check RI x SEC.
- [ ] [G3-A5-T173] Validar: coleta por empresa.
- [ ] [G3-A5-T174] Implementar: log de coleta.
- [ ] [G3-A5-T175] Testar: mapeamento RI_URLS por empresa.
- [ ] [G3-A5-T176] Revisar: tabela CIKs (7 empresas).
- [ ] [G3-A5-T177] Documentar: EXT_TIPO por extensao.
- [ ] [G3-A5-T178] Otimizar: empresa_do_caminho.
- [ ] [G3-A5-T179] Validar: hash SHA-256 em chunks.
- [ ] [G3-A5-T180] Implementar: deteccao de duplicados.

### G3-A6
- [ ] [G3-A6-T181] Testar: pasta ausente (aviso).
- [ ] [G3-A6-T182] Revisar: User-Agent SEC obrigatorio.
- [ ] [G3-A6-T183] Documentar: throttle 0.25s SEC.
- [ ] [G3-A6-T184] Otimizar: endpoint companyfacts.
- [ ] [G3-A6-T185] Validar: mapeamento XBRL->canonico.
- [ ] [G3-A6-T186] Implementar: filtro form 10-Q/10-K/20-F.
- [ ] [G3-A6-T187] Testar: conversao XBRL para USD bi.
- [ ] [G3-A6-T188] Revisar: cache SEC_*.json.
- [ ] [G3-A6-T189] Documentar: tratamento HTTP 403/429.
- [ ] [G3-A6-T190] Otimizar: timeout SEC.

## G4 — Parser tabular (70 tarefas)

### G4-A1
- [ ] [G4-A1-T191] Validar: cabecalho 2T26/Q2 2026/2026Q2.
- [ ] [G4-A1-T192] Implementar: trimestres nus 1Q-4Q + ano contexto.
- [ ] [G4-A1-T193] Testar: balanco at 6/30.
- [ ] [G4-A1-T194] Revisar: semestres 1H26/1S26.
- [ ] [G4-A1-T195] Documentar: fallback Three Months Ended + ano.
- [ ] [G4-A1-T196] Otimizar: rotulo nas cols 0-2.
- [ ] [G4-A1-T197] Validar: skip coluna variacao/vs/%.
- [ ] [G4-A1-T198] Implementar: skip linha ratio/margin.
- [ ] [G4-A1-T199] Testar: deteccao milhoes vs bilhoes.
- [ ] [G4-A1-T200] Revisar: deteccao BRL (R$/REAIS).

### G4-A2
- [ ] [G4-A2-T201] Documentar: negativo entre parenteses.
- [ ] [G4-A2-T202] Otimizar: max_col 44 / max_row 150.
- [ ] [G4-A2-T203] Validar: multi-abas por workbook.
- [ ] [G4-A2-T204] Implementar: sheet Principais indicadores Petrobras.
- [ ] [G4-A2-T205] Testar: databook Shell (col B).
- [ ] [G4-A2-T206] Revisar: supplement Chevron.
- [ ] [G4-A2-T207] Documentar: supplement Exxon (dolares cheios).
- [ ] [G4-A2-T208] Otimizar: databook BP (formulas).
- [ ] [G4-A2-T209] Validar: databook Total (B$ vs mi).
- [ ] [G4-A2-T210] Implementar: dedup por (rubrica,periodo).

### G4-A3
- [ ] [G4-A3-T211] Testar: parse_csv.
- [ ] [G4-A3-T212] Revisar: parse .xls via pandas.
- [ ] [G4-A3-T213] Documentar: cabecalho 2T26/Q2 2026/2026Q2.
- [ ] [G4-A3-T214] Otimizar: trimestres nus 1Q-4Q + ano contexto.
- [ ] [G4-A3-T215] Validar: balanco at 6/30.
- [ ] [G4-A3-T216] Implementar: semestres 1H26/1S26.
- [ ] [G4-A3-T217] Testar: fallback Three Months Ended + ano.
- [ ] [G4-A3-T218] Revisar: rotulo nas cols 0-2.
- [ ] [G4-A3-T219] Documentar: skip coluna variacao/vs/%.
- [ ] [G4-A3-T220] Otimizar: skip linha ratio/margin.

### G4-A4
- [ ] [G4-A4-T221] Validar: deteccao BRL (R$/REAIS).
- [ ] [G4-A4-T222] Implementar: numero BR 1.234,56.
- [ ] [G4-A4-T223] Testar: negativo entre parenteses.
- [ ] [G4-A4-T224] Revisar: max_col 44 / max_row 150.
- [ ] [G4-A4-T225] Documentar: multi-abas por workbook.
- [ ] [G4-A4-T226] Otimizar: sheet Principais indicadores Petrobras.
- [ ] [G4-A4-T227] Validar: databook Shell (col B).
- [ ] [G4-A4-T228] Implementar: supplement Chevron.
- [ ] [G4-A4-T229] Testar: supplement Exxon (dolares cheios).
- [ ] [G4-A4-T230] Revisar: databook BP (formulas).

### G4-A5
- [ ] [G4-A5-T231] Documentar: dedup por (rubrica,periodo).
- [ ] [G4-A5-T232] Otimizar: confianca por fonte.
- [ ] [G4-A5-T233] Validar: parse_csv.
- [ ] [G4-A5-T234] Implementar: parse .xls via pandas.
- [ ] [G4-A5-T235] Testar: cabecalho 2T26/Q2 2026/2026Q2.
- [ ] [G4-A5-T236] Revisar: trimestres nus 1Q-4Q + ano contexto.
- [ ] [G4-A5-T237] Documentar: balanco at 6/30.
- [ ] [G4-A5-T238] Otimizar: semestres 1H26/1S26.
- [ ] [G4-A5-T239] Validar: fallback Three Months Ended + ano.
- [ ] [G4-A5-T240] Implementar: rotulo nas cols 0-2.

### G4-A6
- [ ] [G4-A6-T241] Testar: skip linha ratio/margin.
- [ ] [G4-A6-T242] Revisar: deteccao milhoes vs bilhoes.
- [ ] [G4-A6-T243] Documentar: deteccao BRL (R$/REAIS).
- [ ] [G4-A6-T244] Otimizar: numero BR 1.234,56.
- [ ] [G4-A6-T245] Validar: negativo entre parenteses.
- [ ] [G4-A6-T246] Implementar: max_col 44 / max_row 150.
- [ ] [G4-A6-T247] Testar: multi-abas por workbook.
- [ ] [G4-A6-T248] Revisar: sheet Principais indicadores Petrobras.
- [ ] [G4-A6-T249] Documentar: databook Shell (col B).
- [ ] [G4-A6-T250] Otimizar: supplement Chevron.

### G4-A7
- [ ] [G4-A7-T251] Validar: databook BP (formulas).
- [ ] [G4-A7-T252] Implementar: databook Total (B$ vs mi).
- [ ] [G4-A7-T253] Testar: dedup por (rubrica,periodo).
- [ ] [G4-A7-T254] Revisar: confianca por fonte.
- [ ] [G4-A7-T255] Documentar: parse_csv.
- [ ] [G4-A7-T256] Otimizar: parse .xls via pandas.
- [ ] [G4-A7-T257] Validar: cabecalho 2T26/Q2 2026/2026Q2.
- [ ] [G4-A7-T258] Implementar: trimestres nus 1Q-4Q + ano contexto.
- [ ] [G4-A7-T259] Testar: balanco at 6/30.
- [ ] [G4-A7-T260] Revisar: semestres 1H26/1S26.

## G5 — Parsers PDF e texto (60 tarefas)

### G5-A1
- [ ] [G5-A1-T261] Documentar: limite de paginas PDF.
- [ ] [G5-A1-T262] Otimizar: triagem PDF_PARSE_ALLOW/SKIP.
- [ ] [G5-A1-T263] Validar: fallback quarter-name (second quarter 2026).
- [ ] [G5-A1-T264] Implementar: confianca PDF -0.15.
- [ ] [G5-A1-T265] Testar: PDF protegido/corrompido.
- [ ] [G5-A1-T266] Revisar: leitura docx via python-docx.
- [ ] [G5-A1-T267] Documentar: leitura txt utf-8.
- [ ] [G5-A1-T268] Otimizar: regex rotulo: valor.
- [ ] [G5-A1-T269] Validar: periodo no texto.
- [ ] [G5-A1-T270] Implementar: origem #pdf-table/#texto.

### G5-A2
- [ ] [G5-A2-T271] Testar: release Chevron/Exxon.
- [ ] [G5-A2-T272] Revisar: Desempenho Petrobras.
- [ ] [G5-A2-T273] Documentar: statements Equinor.
- [ ] [G5-A2-T274] Otimizar: transcripts -> NAO_PROCESSADO.
- [ ] [G5-A2-T275] Validar: slides -> NAO_PROCESSADO.
- [ ] [G5-A2-T276] Implementar: status SEM_DADOS vs ERRO.
- [ ] [G5-A2-T277] Testar: fila de revisao em falha de parse.
- [ ] [G5-A2-T278] Revisar: texto via pymupdf (streaming).
- [ ] [G5-A2-T279] Documentar: tabelas via pdfplumber.
- [ ] [G5-A2-T280] Otimizar: limite de paginas PDF.

### G5-A3
- [ ] [G5-A3-T281] Validar: fallback quarter-name (second quarter 2026).
- [ ] [G5-A3-T282] Implementar: confianca PDF -0.15.
- [ ] [G5-A3-T283] Testar: PDF protegido/corrompido.
- [ ] [G5-A3-T284] Revisar: leitura docx via python-docx.
- [ ] [G5-A3-T285] Documentar: leitura txt utf-8.
- [ ] [G5-A3-T286] Otimizar: regex rotulo: valor.
- [ ] [G5-A3-T287] Validar: periodo no texto.
- [ ] [G5-A3-T288] Implementar: origem #pdf-table/#texto.
- [ ] [G5-A3-T289] Testar: QRA Shell.
- [ ] [G5-A3-T290] Revisar: release Chevron/Exxon.

### G5-A4
- [ ] [G5-A4-T291] Documentar: statements Equinor.
- [ ] [G5-A4-T292] Otimizar: transcripts -> NAO_PROCESSADO.
- [ ] [G5-A4-T293] Validar: slides -> NAO_PROCESSADO.
- [ ] [G5-A4-T294] Implementar: status SEM_DADOS vs ERRO.
- [ ] [G5-A4-T295] Testar: fila de revisao em falha de parse.
- [ ] [G5-A4-T296] Revisar: texto via pymupdf (streaming).
- [ ] [G5-A4-T297] Documentar: tabelas via pdfplumber.
- [ ] [G5-A4-T298] Otimizar: limite de paginas PDF.
- [ ] [G5-A4-T299] Validar: triagem PDF_PARSE_ALLOW/SKIP.
- [ ] [G5-A4-T300] Implementar: fallback quarter-name (second quarter 2026).

### G5-A5
- [ ] [G5-A5-T301] Testar: PDF protegido/corrompido.
- [ ] [G5-A5-T302] Revisar: leitura docx via python-docx.
- [ ] [G5-A5-T303] Documentar: leitura txt utf-8.
- [ ] [G5-A5-T304] Otimizar: regex rotulo: valor.
- [ ] [G5-A5-T305] Validar: periodo no texto.
- [ ] [G5-A5-T306] Implementar: origem #pdf-table/#texto.
- [ ] [G5-A5-T307] Testar: QRA Shell.
- [ ] [G5-A5-T308] Revisar: release Chevron/Exxon.
- [ ] [G5-A5-T309] Documentar: Desempenho Petrobras.
- [ ] [G5-A5-T310] Otimizar: statements Equinor.

### G5-A6
- [ ] [G5-A6-T311] Validar: slides -> NAO_PROCESSADO.
- [ ] [G5-A6-T312] Implementar: status SEM_DADOS vs ERRO.
- [ ] [G5-A6-T313] Testar: fila de revisao em falha de parse.
- [ ] [G5-A6-T314] Revisar: texto via pymupdf (streaming).
- [ ] [G5-A6-T315] Documentar: tabelas via pdfplumber.
- [ ] [G5-A6-T316] Otimizar: limite de paginas PDF.
- [ ] [G5-A6-T317] Validar: triagem PDF_PARSE_ALLOW/SKIP.
- [ ] [G5-A6-T318] Implementar: fallback quarter-name (second quarter 2026).
- [ ] [G5-A6-T319] Testar: confianca PDF -0.15.
- [ ] [G5-A6-T320] Revisar: PDF protegido/corrompido.

## G6 — Qualidade e auditoria (60 tarefas)

### G6-A1
- [ ] [G6-A1-T321] Documentar: regra confianca <0.70.
- [ ] [G6-A1-T322] Otimizar: regra cobertura ausente.
- [ ] [G6-A1-T323] Validar: limites plausiveis no audit.
- [ ] [G6-A1-T324] Implementar: severidade HIGH/MEDIUM.
- [ ] [G6-A1-T325] Testar: review_queue ABERTO.
- [ ] [G6-A1-T326] Revisar: supressao por evento M&A.
- [ ] [G6-A1-T327] Documentar: relatorio EVIDENCIAS_QUALIDADE.
- [ ] [G6-A1-T328] Otimizar: contagens do audit.
- [ ] [G6-A1-T329] Validar: alerta Chevron 2T26 (+248%).
- [ ] [G6-A1-T330] Implementar: spikes sazonais 1T.

### G6-A2
- [ ] [G6-A2-T331] Testar: magic-bytes AUTH_REQUIRED.
- [ ] [G6-A2-T332] Revisar: integridade arquivo sumido.
- [ ] [G6-A2-T333] Documentar: revisao de PDFs 0.55.
- [ ] [G6-A2-T334] Otimizar: revisao Exxon 0.69->carga.
- [ ] [G6-A2-T335] Validar: cobertura EFETIVO.
- [ ] [G6-A2-T336] Implementar: cobertura Equinor (limite).
- [ ] [G6-A2-T337] Testar: teste quality negativo+spike.
- [ ] [G6-A2-T338] Revisar: regra INVALID_NEGATIVE.
- [ ] [G6-A2-T339] Documentar: regra VARIATION_SPIKE 40%.
- [ ] [G6-A2-T340] Otimizar: regra confianca <0.70.

### G6-A3
- [ ] [G6-A3-T341] Validar: limites plausiveis no audit.
- [ ] [G6-A3-T342] Implementar: severidade HIGH/MEDIUM.
- [ ] [G6-A3-T343] Testar: review_queue ABERTO.
- [ ] [G6-A3-T344] Revisar: supressao por evento M&A.
- [ ] [G6-A3-T345] Documentar: relatorio EVIDENCIAS_QUALIDADE.
- [ ] [G6-A3-T346] Otimizar: contagens do audit.
- [ ] [G6-A3-T347] Validar: alerta Chevron 2T26 (+248%).
- [ ] [G6-A3-T348] Implementar: spikes sazonais 1T.
- [ ] [G6-A3-T349] Testar: divergencia RI x SEC >2%.
- [ ] [G6-A3-T350] Revisar: magic-bytes AUTH_REQUIRED.

### G6-A4
- [ ] [G6-A4-T351] Documentar: revisao de PDFs 0.55.
- [ ] [G6-A4-T352] Otimizar: revisao Exxon 0.69->carga.
- [ ] [G6-A4-T353] Validar: cobertura EFETIVO.
- [ ] [G6-A4-T354] Implementar: cobertura Equinor (limite).
- [ ] [G6-A4-T355] Testar: teste quality negativo+spike.
- [ ] [G6-A4-T356] Revisar: regra INVALID_NEGATIVE.
- [ ] [G6-A4-T357] Documentar: regra VARIATION_SPIKE 40%.
- [ ] [G6-A4-T358] Otimizar: regra confianca <0.70.
- [ ] [G6-A4-T359] Validar: regra cobertura ausente.
- [ ] [G6-A4-T360] Implementar: limites plausiveis no audit.

### G6-A5
- [ ] [G6-A5-T361] Testar: review_queue ABERTO.
- [ ] [G6-A5-T362] Revisar: supressao por evento M&A.
- [ ] [G6-A5-T363] Documentar: relatorio EVIDENCIAS_QUALIDADE.
- [ ] [G6-A5-T364] Otimizar: contagens do audit.
- [ ] [G6-A5-T365] Validar: alerta Chevron 2T26 (+248%).
- [ ] [G6-A5-T366] Implementar: spikes sazonais 1T.
- [ ] [G6-A5-T367] Testar: divergencia RI x SEC >2%.
- [ ] [G6-A5-T368] Revisar: magic-bytes AUTH_REQUIRED.
- [ ] [G6-A5-T369] Documentar: integridade arquivo sumido.
- [ ] [G6-A5-T370] Otimizar: revisao de PDFs 0.55.

### G6-A6
- [ ] [G6-A6-T371] Validar: cobertura EFETIVO.
- [ ] [G6-A6-T372] Implementar: cobertura Equinor (limite).
- [ ] [G6-A6-T373] Testar: teste quality negativo+spike.
- [ ] [G6-A6-T374] Revisar: regra INVALID_NEGATIVE.
- [ ] [G6-A6-T375] Documentar: regra VARIATION_SPIKE 40%.
- [ ] [G6-A6-T376] Otimizar: regra confianca <0.70.
- [ ] [G6-A6-T377] Validar: regra cobertura ausente.
- [ ] [G6-A6-T378] Implementar: limites plausiveis no audit.
- [ ] [G6-A6-T379] Testar: severidade HIGH/MEDIUM.
- [ ] [G6-A6-T380] Revisar: review_queue ABERTO.

## G7 — Views Web e GUI (70 tarefas)

### G7-A1
- [ ] [G7-A1-T381] Documentar: tab fontes CRUD.
- [ ] [G7-A1-T382] Otimizar: tab auditoria.
- [ ] [G7-A1-T383] Validar: insight executivo.
- [ ] [G7-A1-T384] Implementar: ranking por periodo.
- [ ] [G7-A1-T385] Testar: margem EBITDA.
- [ ] [G7-A1-T386] Revisar: CDN plotly.
- [ ] [G7-A1-T387] Documentar: responsivo <900px.
- [ ] [G7-A1-T388] Otimizar: QSplitter 25/75.
- [ ] [G7-A1-T389] Validar: QToolBox accordions.
- [ ] [G7-A1-T390] Implementar: QTabWidget benchmark+fontes.

### G7-A2
- [ ] [G7-A2-T391] Testar: QSS dark/light.
- [ ] [G7-A2-T392] Revisar: combo de periodo GUI.
- [ ] [G7-A2-T393] Documentar: tabela de fontes GUI.
- [ ] [G7-A2-T394] Otimizar: sidebar 25% + colapso.
- [ ] [G7-A2-T395] Validar: accordions verticais.
- [ ] [G7-A2-T396] Implementar: scroll sidebar.
- [ ] [G7-A2-T397] Testar: tabs fora da sidebar.
- [ ] [G7-A2-T398] Revisar: grid NxM 2x2.
- [ ] [G7-A2-T399] Documentar: temas light/dark.
- [ ] [G7-A2-T400] Otimizar: barras Plotly por empresa.

### G7-A3
- [ ] [G7-A3-T401] Validar: tab fontes CRUD.
- [ ] [G7-A3-T402] Implementar: tab auditoria.
- [ ] [G7-A3-T403] Testar: insight executivo.
- [ ] [G7-A3-T404] Revisar: ranking por periodo.
- [ ] [G7-A3-T405] Documentar: margem EBITDA.
- [ ] [G7-A3-T406] Otimizar: CDN plotly.
- [ ] [G7-A3-T407] Validar: responsivo <900px.
- [ ] [G7-A3-T408] Implementar: QSplitter 25/75.
- [ ] [G7-A3-T409] Testar: QToolBox accordions.
- [ ] [G7-A3-T410] Revisar: QTabWidget benchmark+fontes.

### G7-A4
- [ ] [G7-A4-T411] Documentar: QSS dark/light.
- [ ] [G7-A4-T412] Otimizar: combo de periodo GUI.
- [ ] [G7-A4-T413] Validar: tabela de fontes GUI.
- [ ] [G7-A4-T414] Implementar: sidebar 25% + colapso.
- [ ] [G7-A4-T415] Testar: accordions verticais.
- [ ] [G7-A4-T416] Revisar: scroll sidebar.
- [ ] [G7-A4-T417] Documentar: tabs fora da sidebar.
- [ ] [G7-A4-T418] Otimizar: grid NxM 2x2.
- [ ] [G7-A4-T419] Validar: temas light/dark.
- [ ] [G7-A4-T420] Implementar: barras Plotly por empresa.

### G7-A5
- [ ] [G7-A5-T421] Testar: tab fontes CRUD.
- [ ] [G7-A5-T422] Revisar: tab auditoria.
- [ ] [G7-A5-T423] Documentar: insight executivo.
- [ ] [G7-A5-T424] Otimizar: ranking por periodo.
- [ ] [G7-A5-T425] Validar: margem EBITDA.
- [ ] [G7-A5-T426] Implementar: CDN plotly.
- [ ] [G7-A5-T427] Testar: responsivo <900px.
- [ ] [G7-A5-T428] Revisar: QSplitter 25/75.
- [ ] [G7-A5-T429] Documentar: QToolBox accordions.
- [ ] [G7-A5-T430] Otimizar: QTabWidget benchmark+fontes.

### G7-A6
- [ ] [G7-A6-T431] Validar: QSS dark/light.
- [ ] [G7-A6-T432] Implementar: combo de periodo GUI.
- [ ] [G7-A6-T433] Testar: tabela de fontes GUI.
- [ ] [G7-A6-T434] Revisar: sidebar 25% + colapso.
- [ ] [G7-A6-T435] Documentar: accordions verticais.
- [ ] [G7-A6-T436] Otimizar: scroll sidebar.
- [ ] [G7-A6-T437] Validar: tabs fora da sidebar.
- [ ] [G7-A6-T438] Implementar: grid NxM 2x2.
- [ ] [G7-A6-T439] Testar: temas light/dark.
- [ ] [G7-A6-T440] Revisar: barras Plotly por empresa.

### G7-A7
- [ ] [G7-A7-T441] Documentar: tab fontes CRUD.
- [ ] [G7-A7-T442] Otimizar: tab auditoria.
- [ ] [G7-A7-T443] Validar: insight executivo.
- [ ] [G7-A7-T444] Implementar: ranking por periodo.
- [ ] [G7-A7-T445] Testar: margem EBITDA.
- [ ] [G7-A7-T446] Revisar: CDN plotly.
- [ ] [G7-A7-T447] Documentar: responsivo <900px.
- [ ] [G7-A7-T448] Otimizar: QSplitter 25/75.
- [ ] [G7-A7-T449] Validar: QToolBox accordions.
- [ ] [G7-A7-T450] Implementar: QTabWidget benchmark+fontes.

## G8 — Controllers, CLI, docs e entrega (70 tarefas)

### G8-A1
- [ ] [G8-A1-T451] Testar: PLANO 520 tarefas.
- [ ] [G8-A1-T452] Revisar: test_schema.
- [ ] [G8-A1-T453] Documentar: test_depara.
- [ ] [G8-A1-T454] Otimizar: test_hash.
- [ ] [G8-A1-T455] Validar: test_parse_tab real.
- [ ] [G8-A1-T456] Implementar: test_quality.
- [ ] [G8-A1-T457] Testar: test_web.
- [ ] [G8-A1-T458] Revisar: entrega 06/11 10h.
- [ ] [G8-A1-T459] Documentar: PipelineController.etl_completo.
- [ ] [G8-A1-T460] Otimizar: AnalyticsController.ranking/insight.

### G8-A2
- [ ] [G8-A2-T461] Validar: CLI full/etl/web/gui/sec/status/reset.
- [ ] [G8-A2-T462] Implementar: main_vis.bat opcoes 1-5.
- [ ] [G8-A2-T463] Testar: requirements.txt.
- [ ] [G8-A2-T464] Revisar: CATALOGO_FONTES.md.
- [ ] [G8-A2-T465] Documentar: PREMISSAS_E_LIMITACOES.md.
- [ ] [G8-A2-T466] Otimizar: ROTEIRO_15MIN.
- [ ] [G8-A2-T467] Validar: SLIDES_APRESENTACAO.
- [ ] [G8-A2-T468] Implementar: DOCUMENTACAO_ARQUITETURA.
- [ ] [G8-A2-T469] Testar: INSTRUCOES_EXECUCAO.
- [ ] [G8-A2-T470] Revisar: PLANO 520 tarefas.

### G8-A3
- [ ] [G8-A3-T471] Documentar: test_depara.
- [ ] [G8-A3-T472] Otimizar: test_hash.
- [ ] [G8-A3-T473] Validar: test_parse_tab real.
- [ ] [G8-A3-T474] Implementar: test_quality.
- [ ] [G8-A3-T475] Testar: test_web.
- [ ] [G8-A3-T476] Revisar: entrega 06/11 10h.
- [ ] [G8-A3-T477] Documentar: PipelineController.etl_completo.
- [ ] [G8-A3-T478] Otimizar: AnalyticsController.ranking/insight.
- [ ] [G8-A3-T479] Validar: SourceController CRUD.
- [ ] [G8-A3-T480] Implementar: CLI full/etl/web/gui/sec/status/reset.

### G8-A4
- [ ] [G8-A4-T481] Testar: requirements.txt.
- [ ] [G8-A4-T482] Revisar: CATALOGO_FONTES.md.
- [ ] [G8-A4-T483] Documentar: PREMISSAS_E_LIMITACOES.md.
- [ ] [G8-A4-T484] Otimizar: ROTEIRO_15MIN.
- [ ] [G8-A4-T485] Validar: SLIDES_APRESENTACAO.
- [ ] [G8-A4-T486] Implementar: DOCUMENTACAO_ARQUITETURA.
- [ ] [G8-A4-T487] Testar: INSTRUCOES_EXECUCAO.
- [ ] [G8-A4-T488] Revisar: PLANO 520 tarefas.
- [ ] [G8-A4-T489] Documentar: test_schema.
- [ ] [G8-A4-T490] Otimizar: test_depara.

### G8-A5
- [ ] [G8-A5-T491] Validar: test_parse_tab real.
- [ ] [G8-A5-T492] Implementar: test_quality.
- [ ] [G8-A5-T493] Testar: test_web.
- [ ] [G8-A5-T494] Revisar: entrega 06/11 10h.
- [ ] [G8-A5-T495] Documentar: PipelineController.etl_completo.
- [ ] [G8-A5-T496] Otimizar: AnalyticsController.ranking/insight.
- [ ] [G8-A5-T497] Validar: SourceController CRUD.
- [ ] [G8-A5-T498] Implementar: CLI full/etl/web/gui/sec/status/reset.
- [ ] [G8-A5-T499] Testar: main_vis.bat opcoes 1-5.
- [ ] [G8-A5-T500] Revisar: requirements.txt.

### G8-A6
- [ ] [G8-A6-T501] Documentar: PREMISSAS_E_LIMITACOES.md.
- [ ] [G8-A6-T502] Otimizar: ROTEIRO_15MIN.
- [ ] [G8-A6-T503] Validar: SLIDES_APRESENTACAO.
- [ ] [G8-A6-T504] Implementar: DOCUMENTACAO_ARQUITETURA.
- [ ] [G8-A6-T505] Testar: INSTRUCOES_EXECUCAO.
- [ ] [G8-A6-T506] Revisar: PLANO 520 tarefas.
- [ ] [G8-A6-T507] Documentar: test_schema.
- [ ] [G8-A6-T508] Otimizar: test_depara.
- [ ] [G8-A6-T509] Validar: test_hash.
- [ ] [G8-A6-T510] Implementar: test_parse_tab real.

### G8-A7
- [ ] [G8-A7-T511] Testar: test_web.
- [ ] [G8-A7-T512] Revisar: entrega 06/11 10h.
- [ ] [G8-A7-T513] Documentar: PipelineController.etl_completo.
- [ ] [G8-A7-T514] Otimizar: AnalyticsController.ranking/insight.
- [ ] [G8-A7-T515] Validar: SourceController CRUD.
- [ ] [G8-A7-T516] Implementar: CLI full/etl/web/gui/sec/status/reset.
- [ ] [G8-A7-T517] Testar: main_vis.bat opcoes 1-5.
- [ ] [G8-A7-T518] Revisar: requirements.txt.
- [ ] [G8-A7-T519] Documentar: CATALOGO_FONTES.md.
- [ ] [G8-A7-T520] Otimizar: PREMISSAS_E_LIMITACOES.md.

**Total: 520 tarefas.**