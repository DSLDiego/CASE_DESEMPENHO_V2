# Plano de execucao — 2040 tarefas (12 grupos x 170)

Formato `[Gx-Ay-Tnnnn]`. PoC executada (out/2026): ETL real + pytest + painel no ar.
Itens marcados derivam 1:1 de modulos, testes e evidencias existentes.

## Backlog de melhorias (M1-M3) - prioridade alta

| ID | Melhoria | Escopo | Onde |
|---|---|---|---|
| **M1** | Aba Fontes -> **Gestao e Controle de Fontes** | De CRUD para gestao: cobertura empresa x periodo, integridade (hash/arquivo/URL), lacunas (o que falta vs. o que existe), acoes em lote, KPIs por status/origem/extensao | `SourceController.painel_fontes()`, aba Fontes |
| **M2** | Aba Auditoria -> **Gestao e Controle de Auditoria** | KPIs por severidade/tipo/empresa, triagem (aceitar/rejeitar/ignorar) com trilha em `tb_auditoria_decisao`, aging da fila, reabertura | `QualityRepository.decidir()`, aba Auditoria |
| **M3** | **Metodologia estatistica de projecao (ate 3 trimestres)** | `workers/forecast.py`: Holt-Winters aditivo damped com sazonalidade trimestral + sazonal-naive + ultima-observacao; **metodo escolhido por backtesting** (MAE/MAPE), IC95 que alarga com o horizonte, piso de dados e aviso de baixa confianca | `tb_projecao`, aba Projecoes |

### M3 - metodologia (detalhamento)
1. **Serie**: valores por trimestre (YYYYQn) por empresa x rubrica; lacunas interpoladas
   linearmente e descontadas da confianca.
2. **Sazonalidade (k=4)**: indices por trimestre normalizados (soma zero), aplicada apenas
   com >= 6 observacoes.
3. **Tendencia**: Holt linear com amortecimento (phi=0.85) - evita extrapolacao explosiva
   em series de petroleo.
4. **Selecao por backtesting**: testa sazonal-naive, HW-damped e ultima-observacao nos
   ultimos k pontos; fica com a de menor MAE (desempate: menor MAPE).
5. **Incerteza**: sigma dos erros de backtesting; IC95 = f +- 1,96*sigma*sqrt(h).
6. **Governanca**: confianca < 0.5 quando < 6 pontos ou sigma alto; a projecao e sempre
   rotulada como projecao e **nunca** entra na matriz de fatos reais.

### Limites de M3 (registrados em PREMISSAS_E_LIMITACOES.md)
- 14 trimestres por rubrica e pouco para sazonalidade robusta: por isso backtesting e
  intervalos declarados, e nunca projecao pontual sem erro.
- Projecao nao e previsao de preco do petroleo nem de resultado: e continuacao do padrao
  trimestral da serie, util para cenarios; decisao humana continua obrigatoria.

## G1 — Fundacao e Model SQLite (170 tarefas)
_Modulos: `models/database.py, models/repositories.py, config.py`_

### G1-A1
- [ ] [G1-A1-T0001] Testar: tabela tb_fato_financeiro.
- [ ] [G1-A1-T0002] Revisar: tabela tb_fato_operacional.
- [ ] [G1-A1-T0003] Documentar: tabela tb_quality_alerts.
- [ ] [G1-A1-T0004] Otimizar: tabela tb_review_queue.
- [ ] [G1-A1-T0005] Validar: indices idempotentes.
- [ ] [G1-A1-T0006] Medir: singleton thread-safe.
- [ ] [G1-A1-T0007] Automatizar: modo WAL.
- [ ] [G1-A1-T0008] Implementar: registrar idempotente.
- [ ] [G1-A1-T0009] Testar: exportar json/csv.
- [ ] [G1-A1-T0010] Revisar: verificar_integridade.

### G1-A2
- [ ] [G1-A2-T0011] Documentar: upsert financeiro.
- [ ] [G1-A2-T0012] Otimizar: upsert operacional.
- [ ] [G1-A2-T0013] Validar: matriz benchmarking.
- [ ] [G1-A2-T0014] Medir: obter fato.
- [ ] [G1-A2-T0015] Automatizar: contar.
- [ ] [G1-A2-T0016] Implementar: alertar.
- [ ] [G1-A2-T0017] Testar: para_revisao.
- [ ] [G1-A2-T0018] Revisar: listar_alertas.
- [ ] [G1-A2-T0019] Documentar: listar_revisao.
- [ ] [G1-A2-T0020] Otimizar: reset.

### G1-A3
- [ ] [G1-A3-T0021] Validar: tabela tb_fonte_dados.
- [ ] [G1-A3-T0022] Medir: tabela tb_depara_rubrica.
- [ ] [G1-A3-T0023] Automatizar: tabela tb_fato_financeiro.
- [ ] [G1-A3-T0024] Implementar: tabela tb_fato_operacional.
- [ ] [G1-A3-T0025] Testar: tabela tb_quality_alerts.
- [ ] [G1-A3-T0026] Revisar: tabela tb_review_queue.
- [ ] [G1-A3-T0027] Documentar: indices idempotentes.
- [ ] [G1-A3-T0028] Otimizar: singleton thread-safe.
- [ ] [G1-A3-T0029] Validar: modo WAL.
- [ ] [G1-A3-T0030] Medir: registrar idempotente.

### G1-A4
- [ ] [G1-A4-T0031] Automatizar: verificar_integridade.
- [ ] [G1-A4-T0032] Implementar: cache DePara.
- [ ] [G1-A4-T0033] Testar: upsert financeiro.
- [ ] [G1-A4-T0034] Revisar: upsert operacional.
- [ ] [G1-A4-T0035] Documentar: matriz benchmarking.
- [ ] [G1-A4-T0036] Otimizar: obter fato.
- [ ] [G1-A4-T0037] Validar: contar.
- [ ] [G1-A4-T0038] Medir: alertar.
- [ ] [G1-A4-T0039] Automatizar: para_revisao.
- [ ] [G1-A4-T0040] Implementar: listar_alertas.

### G1-A5
- [ ] [G1-A5-T0041] Testar: reset.
- [ ] [G1-A5-T0042] Revisar: migracao schema.
- [ ] [G1-A5-T0043] Documentar: tabela tb_fonte_dados.
- [ ] [G1-A5-T0044] Otimizar: tabela tb_depara_rubrica.
- [ ] [G1-A5-T0045] Validar: tabela tb_fato_financeiro.
- [ ] [G1-A5-T0046] Medir: tabela tb_fato_operacional.
- [ ] [G1-A5-T0047] Automatizar: tabela tb_quality_alerts.
- [ ] [G1-A5-T0048] Implementar: tabela tb_review_queue.
- [ ] [G1-A5-T0049] Testar: indices idempotentes.
- [ ] [G1-A5-T0050] Revisar: singleton thread-safe.

### G1-A6
- [ ] [G1-A6-T0051] Documentar: registrar idempotente.
- [ ] [G1-A6-T0052] Otimizar: exportar json/csv.
- [ ] [G1-A6-T0053] Validar: verificar_integridade.
- [ ] [G1-A6-T0054] Medir: cache DePara.
- [ ] [G1-A6-T0055] Automatizar: upsert financeiro.
- [ ] [G1-A6-T0056] Implementar: upsert operacional.
- [ ] [G1-A6-T0057] Testar: matriz benchmarking.
- [ ] [G1-A6-T0058] Revisar: obter fato.
- [ ] [G1-A6-T0059] Documentar: contar.
- [ ] [G1-A6-T0060] Otimizar: alertar.

### G1-A7
- [ ] [G1-A7-T0061] Validar: listar_alertas.
- [ ] [G1-A7-T0062] Medir: listar_revisao.
- [ ] [G1-A7-T0063] Automatizar: reset.
- [ ] [G1-A7-T0064] Implementar: migracao schema.
- [ ] [G1-A7-T0065] Testar: tabela tb_fonte_dados.
- [ ] [G1-A7-T0066] Revisar: tabela tb_depara_rubrica.
- [ ] [G1-A7-T0067] Documentar: tabela tb_fato_financeiro.
- [ ] [G1-A7-T0068] Otimizar: tabela tb_fato_operacional.
- [ ] [G1-A7-T0069] Validar: tabela tb_quality_alerts.
- [ ] [G1-A7-T0070] Medir: tabela tb_review_queue.

### G1-A8
- [ ] [G1-A8-T0071] Automatizar: singleton thread-safe.
- [ ] [G1-A8-T0072] Implementar: modo WAL.
- [ ] [G1-A8-T0073] Testar: registrar idempotente.
- [ ] [G1-A8-T0074] Revisar: exportar json/csv.
- [ ] [G1-A8-T0075] Documentar: verificar_integridade.
- [ ] [G1-A8-T0076] Otimizar: cache DePara.
- [ ] [G1-A8-T0077] Validar: upsert financeiro.
- [ ] [G1-A8-T0078] Medir: upsert operacional.
- [ ] [G1-A8-T0079] Automatizar: matriz benchmarking.
- [ ] [G1-A8-T0080] Implementar: obter fato.

### G1-A9
- [ ] [G1-A9-T0081] Testar: alertar.
- [ ] [G1-A9-T0082] Revisar: para_revisao.
- [ ] [G1-A9-T0083] Documentar: listar_alertas.
- [ ] [G1-A9-T0084] Otimizar: listar_revisao.
- [ ] [G1-A9-T0085] Validar: reset.
- [ ] [G1-A9-T0086] Medir: migracao schema.
- [ ] [G1-A9-T0087] Automatizar: tabela tb_fonte_dados.
- [ ] [G1-A9-T0088] Implementar: tabela tb_depara_rubrica.
- [ ] [G1-A9-T0089] Testar: tabela tb_fato_financeiro.
- [ ] [G1-A9-T0090] Revisar: tabela tb_fato_operacional.

### G1-A10
- [ ] [G1-A10-T0091] Documentar: tabela tb_review_queue.
- [ ] [G1-A10-T0092] Otimizar: indices idempotentes.
- [ ] [G1-A10-T0093] Validar: singleton thread-safe.
- [ ] [G1-A10-T0094] Medir: modo WAL.
- [ ] [G1-A10-T0095] Automatizar: registrar idempotente.
- [ ] [G1-A10-T0096] Implementar: exportar json/csv.
- [ ] [G1-A10-T0097] Testar: verificar_integridade.
- [ ] [G1-A10-T0098] Revisar: cache DePara.
- [ ] [G1-A10-T0099] Documentar: upsert financeiro.
- [ ] [G1-A10-T0100] Otimizar: upsert operacional.

### G1-A11
- [ ] [G1-A11-T0101] Validar: obter fato.
- [ ] [G1-A11-T0102] Medir: contar.
- [ ] [G1-A11-T0103] Automatizar: alertar.
- [ ] [G1-A11-T0104] Implementar: para_revisao.
- [ ] [G1-A11-T0105] Testar: listar_alertas.
- [ ] [G1-A11-T0106] Revisar: listar_revisao.
- [ ] [G1-A11-T0107] Documentar: reset.
- [ ] [G1-A11-T0108] Otimizar: migracao schema.
- [ ] [G1-A11-T0109] Validar: tabela tb_fonte_dados.
- [ ] [G1-A11-T0110] Medir: tabela tb_depara_rubrica.

### G1-A12
- [ ] [G1-A12-T0111] Automatizar: tabela tb_fato_operacional.
- [ ] [G1-A12-T0112] Implementar: tabela tb_quality_alerts.
- [ ] [G1-A12-T0113] Testar: tabela tb_review_queue.
- [ ] [G1-A12-T0114] Revisar: indices idempotentes.
- [ ] [G1-A12-T0115] Documentar: singleton thread-safe.
- [ ] [G1-A12-T0116] Otimizar: modo WAL.
- [ ] [G1-A12-T0117] Validar: registrar idempotente.
- [ ] [G1-A12-T0118] Medir: exportar json/csv.
- [ ] [G1-A12-T0119] Automatizar: verificar_integridade.
- [ ] [G1-A12-T0120] Implementar: cache DePara.

### G1-A13
- [ ] [G1-A13-T0121] Testar: upsert operacional.
- [ ] [G1-A13-T0122] Revisar: matriz benchmarking.
- [ ] [G1-A13-T0123] Documentar: obter fato.
- [ ] [G1-A13-T0124] Otimizar: contar.
- [ ] [G1-A13-T0125] Validar: alertar.
- [ ] [G1-A13-T0126] Medir: para_revisao.
- [ ] [G1-A13-T0127] Automatizar: listar_alertas.
- [ ] [G1-A13-T0128] Implementar: listar_revisao.
- [ ] [G1-A13-T0129] Testar: reset.
- [ ] [G1-A13-T0130] Revisar: migracao schema.

### G1-A14
- [ ] [G1-A14-T0131] Documentar: tabela tb_depara_rubrica.
- [ ] [G1-A14-T0132] Otimizar: tabela tb_fato_financeiro.
- [ ] [G1-A14-T0133] Validar: tabela tb_fato_operacional.
- [ ] [G1-A14-T0134] Medir: tabela tb_quality_alerts.
- [ ] [G1-A14-T0135] Automatizar: tabela tb_review_queue.
- [ ] [G1-A14-T0136] Implementar: indices idempotentes.
- [ ] [G1-A14-T0137] Testar: singleton thread-safe.
- [ ] [G1-A14-T0138] Revisar: modo WAL.
- [ ] [G1-A14-T0139] Documentar: registrar idempotente.
- [ ] [G1-A14-T0140] Otimizar: exportar json/csv.

### G1-A15
- [ ] [G1-A15-T0141] Validar: cache DePara.
- [ ] [G1-A15-T0142] Medir: upsert financeiro.
- [ ] [G1-A15-T0143] Automatizar: upsert operacional.
- [ ] [G1-A15-T0144] Implementar: matriz benchmarking.
- [ ] [G1-A15-T0145] Testar: obter fato.
- [ ] [G1-A15-T0146] Revisar: contar.
- [ ] [G1-A15-T0147] Documentar: alertar.
- [ ] [G1-A15-T0148] Otimizar: para_revisao.
- [ ] [G1-A15-T0149] Validar: listar_alertas.
- [ ] [G1-A15-T0150] Medir: listar_revisao.

### G1-A16
- [ ] [G1-A16-T0151] Automatizar: migracao schema.
- [ ] [G1-A16-T0152] Implementar: tabela tb_fonte_dados.
- [ ] [G1-A16-T0153] Testar: tabela tb_depara_rubrica.
- [ ] [G1-A16-T0154] Revisar: tabela tb_fato_financeiro.
- [ ] [G1-A16-T0155] Documentar: tabela tb_fato_operacional.
- [ ] [G1-A16-T0156] Otimizar: tabela tb_quality_alerts.
- [ ] [G1-A16-T0157] Validar: tabela tb_review_queue.
- [ ] [G1-A16-T0158] Medir: indices idempotentes.
- [ ] [G1-A16-T0159] Automatizar: singleton thread-safe.
- [ ] [G1-A16-T0160] Implementar: modo WAL.

### G1-A17
- [ ] [G1-A17-T0161] Testar: exportar json/csv.
- [ ] [G1-A17-T0162] Revisar: verificar_integridade.
- [ ] [G1-A17-T0163] Documentar: cache DePara.
- [ ] [G1-A17-T0164] Otimizar: upsert financeiro.
- [ ] [G1-A17-T0165] Validar: upsert operacional.
- [ ] [G1-A17-T0166] Medir: matriz benchmarking.
- [ ] [G1-A17-T0167] Automatizar: obter fato.
- [ ] [G1-A17-T0168] Implementar: contar.
- [ ] [G1-A17-T0169] Testar: alertar.
- [ ] [G1-A17-T0170] Revisar: para_revisao.

## G2 — De-Para e normalizacao (170 tarefas)
_Modulos: `models/depara.py, workers/etl.py, workers/quality.py`_

### G2-A1
- [ ] [G2-A1-T0171] Documentar: re-escala /1000.
- [ ] [G2-A1-T0172] Otimizar: normalizar_sinal.
- [ ] [G2-A1-T0173] Validar: seed de-para.
- [ ] [G2-A1-T0174] Medir: normalize unicode.
- [ ] [G2-A1-T0175] Automatizar: RECEITA PT/EN.
- [ ] [G2-A1-T0176] Implementar: EBITDA.
- [ ] [G2-A1-T0177] Testar: LUCRO.
- [ ] [G2-A1-T0178] Revisar: FCO/FCL.
- [ ] [G2-A1-T0179] Documentar: DIVIDAS.
- [ ] [G2-A1-T0180] Otimizar: EFETIVO.

### G2-A2
- [ ] [G2-A2-T0181] Validar: CAPEX.
- [ ] [G2-A2-T0182] Medir: word-boundary SGA.
- [ ] [G2-A2-T0183] Automatizar: skip per-share.
- [ ] [G2-A2-T0184] Implementar: skip contribution-of.
- [ ] [G2-A2-T0185] Testar: skip non-controlling.
- [ ] [G2-A2-T0186] Revisar: PTAX BCB.
- [ ] [G2-A2-T0187] Documentar: fallback PTAX.
- [ ] [G2-A2-T0188] Otimizar: preferencia USD.
- [ ] [G2-A2-T0189] Validar: prioridade confianca.
- [ ] [G2-A2-T0190] Medir: Mboed->kboed.

### G2-A3
- [ ] [G2-A3-T0191] Automatizar: re-escala /1000.
- [ ] [G2-A3-T0192] Implementar: normalizar_sinal.
- [ ] [G2-A3-T0193] Testar: seed de-para.
- [ ] [G2-A3-T0194] Revisar: normalize unicode.
- [ ] [G2-A3-T0195] Documentar: RECEITA PT/EN.
- [ ] [G2-A3-T0196] Otimizar: EBITDA.
- [ ] [G2-A3-T0197] Validar: LUCRO.
- [ ] [G2-A3-T0198] Medir: FCO/FCL.
- [ ] [G2-A3-T0199] Automatizar: DIVIDAS.
- [ ] [G2-A3-T0200] Implementar: EFETIVO.

### G2-A4
- [ ] [G2-A4-T0201] Testar: CAPEX.
- [ ] [G2-A4-T0202] Revisar: word-boundary SGA.
- [ ] [G2-A4-T0203] Documentar: skip per-share.
- [ ] [G2-A4-T0204] Otimizar: skip contribution-of.
- [ ] [G2-A4-T0205] Validar: skip non-controlling.
- [ ] [G2-A4-T0206] Medir: PTAX BCB.
- [ ] [G2-A4-T0207] Automatizar: fallback PTAX.
- [ ] [G2-A4-T0208] Implementar: preferencia USD.
- [ ] [G2-A4-T0209] Testar: prioridade confianca.
- [ ] [G2-A4-T0210] Revisar: Mboed->kboed.

### G2-A5
- [ ] [G2-A5-T0211] Documentar: re-escala /1000.
- [ ] [G2-A5-T0212] Otimizar: normalizar_sinal.
- [ ] [G2-A5-T0213] Validar: seed de-para.
- [ ] [G2-A5-T0214] Medir: normalize unicode.
- [ ] [G2-A5-T0215] Automatizar: RECEITA PT/EN.
- [ ] [G2-A5-T0216] Implementar: EBITDA.
- [ ] [G2-A5-T0217] Testar: LUCRO.
- [ ] [G2-A5-T0218] Revisar: FCO/FCL.
- [ ] [G2-A5-T0219] Documentar: DIVIDAS.
- [ ] [G2-A5-T0220] Otimizar: EFETIVO.

### G2-A6
- [ ] [G2-A6-T0221] Validar: CAPEX.
- [ ] [G2-A6-T0222] Medir: word-boundary SGA.
- [ ] [G2-A6-T0223] Automatizar: skip per-share.
- [ ] [G2-A6-T0224] Implementar: skip contribution-of.
- [ ] [G2-A6-T0225] Testar: skip non-controlling.
- [ ] [G2-A6-T0226] Revisar: PTAX BCB.
- [ ] [G2-A6-T0227] Documentar: fallback PTAX.
- [ ] [G2-A6-T0228] Otimizar: preferencia USD.
- [ ] [G2-A6-T0229] Validar: prioridade confianca.
- [ ] [G2-A6-T0230] Medir: Mboed->kboed.

### G2-A7
- [ ] [G2-A7-T0231] Automatizar: re-escala /1000.
- [ ] [G2-A7-T0232] Implementar: normalizar_sinal.
- [ ] [G2-A7-T0233] Testar: seed de-para.
- [ ] [G2-A7-T0234] Revisar: normalize unicode.
- [ ] [G2-A7-T0235] Documentar: RECEITA PT/EN.
- [ ] [G2-A7-T0236] Otimizar: EBITDA.
- [ ] [G2-A7-T0237] Validar: LUCRO.
- [ ] [G2-A7-T0238] Medir: FCO/FCL.
- [ ] [G2-A7-T0239] Automatizar: DIVIDAS.
- [ ] [G2-A7-T0240] Implementar: EFETIVO.

### G2-A8
- [ ] [G2-A8-T0241] Testar: CAPEX.
- [ ] [G2-A8-T0242] Revisar: word-boundary SGA.
- [ ] [G2-A8-T0243] Documentar: skip per-share.
- [ ] [G2-A8-T0244] Otimizar: skip contribution-of.
- [ ] [G2-A8-T0245] Validar: skip non-controlling.
- [ ] [G2-A8-T0246] Medir: PTAX BCB.
- [ ] [G2-A8-T0247] Automatizar: fallback PTAX.
- [ ] [G2-A8-T0248] Implementar: preferencia USD.
- [ ] [G2-A8-T0249] Testar: prioridade confianca.
- [ ] [G2-A8-T0250] Revisar: Mboed->kboed.

### G2-A9
- [ ] [G2-A9-T0251] Documentar: re-escala /1000.
- [ ] [G2-A9-T0252] Otimizar: normalizar_sinal.
- [ ] [G2-A9-T0253] Validar: seed de-para.
- [ ] [G2-A9-T0254] Medir: normalize unicode.
- [ ] [G2-A9-T0255] Automatizar: RECEITA PT/EN.
- [ ] [G2-A9-T0256] Implementar: EBITDA.
- [ ] [G2-A9-T0257] Testar: LUCRO.
- [ ] [G2-A9-T0258] Revisar: FCO/FCL.
- [ ] [G2-A9-T0259] Documentar: DIVIDAS.
- [ ] [G2-A9-T0260] Otimizar: EFETIVO.

### G2-A10
- [ ] [G2-A10-T0261] Validar: CAPEX.
- [ ] [G2-A10-T0262] Medir: word-boundary SGA.
- [ ] [G2-A10-T0263] Automatizar: skip per-share.
- [ ] [G2-A10-T0264] Implementar: skip contribution-of.
- [ ] [G2-A10-T0265] Testar: skip non-controlling.
- [ ] [G2-A10-T0266] Revisar: PTAX BCB.
- [ ] [G2-A10-T0267] Documentar: fallback PTAX.
- [ ] [G2-A10-T0268] Otimizar: preferencia USD.
- [ ] [G2-A10-T0269] Validar: prioridade confianca.
- [ ] [G2-A10-T0270] Medir: Mboed->kboed.

### G2-A11
- [ ] [G2-A11-T0271] Automatizar: re-escala /1000.
- [ ] [G2-A11-T0272] Implementar: normalizar_sinal.
- [ ] [G2-A11-T0273] Testar: seed de-para.
- [ ] [G2-A11-T0274] Revisar: normalize unicode.
- [ ] [G2-A11-T0275] Documentar: RECEITA PT/EN.
- [ ] [G2-A11-T0276] Otimizar: EBITDA.
- [ ] [G2-A11-T0277] Validar: LUCRO.
- [ ] [G2-A11-T0278] Medir: FCO/FCL.
- [ ] [G2-A11-T0279] Automatizar: DIVIDAS.
- [ ] [G2-A11-T0280] Implementar: EFETIVO.

### G2-A12
- [ ] [G2-A12-T0281] Testar: CAPEX.
- [ ] [G2-A12-T0282] Revisar: word-boundary SGA.
- [ ] [G2-A12-T0283] Documentar: skip per-share.
- [ ] [G2-A12-T0284] Otimizar: skip contribution-of.
- [ ] [G2-A12-T0285] Validar: skip non-controlling.
- [ ] [G2-A12-T0286] Medir: PTAX BCB.
- [ ] [G2-A12-T0287] Automatizar: fallback PTAX.
- [ ] [G2-A12-T0288] Implementar: preferencia USD.
- [ ] [G2-A12-T0289] Testar: prioridade confianca.
- [ ] [G2-A12-T0290] Revisar: Mboed->kboed.

### G2-A13
- [ ] [G2-A13-T0291] Documentar: re-escala /1000.
- [ ] [G2-A13-T0292] Otimizar: normalizar_sinal.
- [ ] [G2-A13-T0293] Validar: seed de-para.
- [ ] [G2-A13-T0294] Medir: normalize unicode.
- [ ] [G2-A13-T0295] Automatizar: RECEITA PT/EN.
- [ ] [G2-A13-T0296] Implementar: EBITDA.
- [ ] [G2-A13-T0297] Testar: LUCRO.
- [ ] [G2-A13-T0298] Revisar: FCO/FCL.
- [ ] [G2-A13-T0299] Documentar: DIVIDAS.
- [ ] [G2-A13-T0300] Otimizar: EFETIVO.

### G2-A14
- [ ] [G2-A14-T0301] Validar: CAPEX.
- [ ] [G2-A14-T0302] Medir: word-boundary SGA.
- [ ] [G2-A14-T0303] Automatizar: skip per-share.
- [ ] [G2-A14-T0304] Implementar: skip contribution-of.
- [ ] [G2-A14-T0305] Testar: skip non-controlling.
- [ ] [G2-A14-T0306] Revisar: PTAX BCB.
- [ ] [G2-A14-T0307] Documentar: fallback PTAX.
- [ ] [G2-A14-T0308] Otimizar: preferencia USD.
- [ ] [G2-A14-T0309] Validar: prioridade confianca.
- [ ] [G2-A14-T0310] Medir: Mboed->kboed.

### G2-A15
- [ ] [G2-A15-T0311] Automatizar: re-escala /1000.
- [ ] [G2-A15-T0312] Implementar: normalizar_sinal.
- [ ] [G2-A15-T0313] Testar: seed de-para.
- [ ] [G2-A15-T0314] Revisar: normalize unicode.
- [ ] [G2-A15-T0315] Documentar: RECEITA PT/EN.
- [ ] [G2-A15-T0316] Otimizar: EBITDA.
- [ ] [G2-A15-T0317] Validar: LUCRO.
- [ ] [G2-A15-T0318] Medir: FCO/FCL.
- [ ] [G2-A15-T0319] Automatizar: DIVIDAS.
- [ ] [G2-A15-T0320] Implementar: EFETIVO.

### G2-A16
- [ ] [G2-A16-T0321] Testar: CAPEX.
- [ ] [G2-A16-T0322] Revisar: word-boundary SGA.
- [ ] [G2-A16-T0323] Documentar: skip per-share.
- [ ] [G2-A16-T0324] Otimizar: skip contribution-of.
- [ ] [G2-A16-T0325] Validar: skip non-controlling.
- [ ] [G2-A16-T0326] Medir: PTAX BCB.
- [ ] [G2-A16-T0327] Automatizar: fallback PTAX.
- [ ] [G2-A16-T0328] Implementar: preferencia USD.
- [ ] [G2-A16-T0329] Testar: prioridade confianca.
- [ ] [G2-A16-T0330] Revisar: Mboed->kboed.

### G2-A17
- [ ] [G2-A17-T0331] Documentar: re-escala /1000.
- [ ] [G2-A17-T0332] Otimizar: normalizar_sinal.
- [ ] [G2-A17-T0333] Validar: seed de-para.
- [ ] [G2-A17-T0334] Medir: normalize unicode.
- [ ] [G2-A17-T0335] Automatizar: RECEITA PT/EN.
- [ ] [G2-A17-T0336] Implementar: EBITDA.
- [ ] [G2-A17-T0337] Testar: LUCRO.
- [ ] [G2-A17-T0338] Revisar: FCO/FCL.
- [ ] [G2-A17-T0339] Documentar: DIVIDAS.
- [ ] [G2-A17-T0340] Otimizar: EFETIVO.

## G3 — Coleta web e SEC (170 tarefas)
_Modulos: `workers/scanner.py, workers/sec_edgar.py, workers/ri_collector.py`_

### G3-A1
- [ ] [G3-A1-T0341] Validar: download dedup.
- [ ] [G3-A1-T0342] Medir: magic-bytes.
- [ ] [G3-A1-T0343] Automatizar: retry backoff.
- [ ] [G3-A1-T0344] Implementar: URL canonica.
- [ ] [G3-A1-T0345] Testar: snapshot Investidor10.
- [ ] [G3-A1-T0346] Revisar: FAQ JSON-LD.
- [ ] [G3-A1-T0347] Documentar: trimestre_corrente.
- [ ] [G3-A1-T0348] Otimizar: mercado MKT_*.
- [ ] [G3-A1-T0349] Validar: coleta CLI.
- [ ] [G3-A1-T0350] Medir: BP CIK 0000313807.

### G3-A2
- [ ] [G3-A2-T0351] Automatizar: CIKs 7 empresas.
- [ ] [G3-A2-T0352] Implementar: User-Agent SEC.
- [ ] [G3-A2-T0353] Testar: throttle.
- [ ] [G3-A2-T0354] Revisar: companyfacts.
- [ ] [G3-A2-T0355] Documentar: XBRL US-GAAP.
- [ ] [G3-A2-T0356] Otimizar: XBRL IFRS.
- [ ] [G3-A2-T0357] Validar: frame CY.
- [ ] [G3-A2-T0358] Medir: FY nunca vira trimestre.
- [ ] [G3-A2-T0359] Automatizar: cache JSON.
- [ ] [G3-A2-T0360] Implementar: 403/429.

### G3-A3
- [ ] [G3-A3-T0361] Testar: download dedup.
- [ ] [G3-A3-T0362] Revisar: magic-bytes.
- [ ] [G3-A3-T0363] Documentar: retry backoff.
- [ ] [G3-A3-T0364] Otimizar: URL canonica.
- [ ] [G3-A3-T0365] Validar: snapshot Investidor10.
- [ ] [G3-A3-T0366] Medir: FAQ JSON-LD.
- [ ] [G3-A3-T0367] Automatizar: trimestre_corrente.
- [ ] [G3-A3-T0368] Implementar: mercado MKT_*.
- [ ] [G3-A3-T0369] Testar: coleta CLI.
- [ ] [G3-A3-T0370] Revisar: BP CIK 0000313807.

### G3-A4
- [ ] [G3-A4-T0371] Documentar: CIKs 7 empresas.
- [ ] [G3-A4-T0372] Otimizar: User-Agent SEC.
- [ ] [G3-A4-T0373] Validar: throttle.
- [ ] [G3-A4-T0374] Medir: companyfacts.
- [ ] [G3-A4-T0375] Automatizar: XBRL US-GAAP.
- [ ] [G3-A4-T0376] Implementar: XBRL IFRS.
- [ ] [G3-A4-T0377] Testar: frame CY.
- [ ] [G3-A4-T0378] Revisar: FY nunca vira trimestre.
- [ ] [G3-A4-T0379] Documentar: cache JSON.
- [ ] [G3-A4-T0380] Otimizar: 403/429.

### G3-A5
- [ ] [G3-A5-T0381] Validar: download dedup.
- [ ] [G3-A5-T0382] Medir: magic-bytes.
- [ ] [G3-A5-T0383] Automatizar: retry backoff.
- [ ] [G3-A5-T0384] Implementar: URL canonica.
- [ ] [G3-A5-T0385] Testar: snapshot Investidor10.
- [ ] [G3-A5-T0386] Revisar: FAQ JSON-LD.
- [ ] [G3-A5-T0387] Documentar: trimestre_corrente.
- [ ] [G3-A5-T0388] Otimizar: mercado MKT_*.
- [ ] [G3-A5-T0389] Validar: coleta CLI.
- [ ] [G3-A5-T0390] Medir: BP CIK 0000313807.

### G3-A6
- [ ] [G3-A6-T0391] Automatizar: CIKs 7 empresas.
- [ ] [G3-A6-T0392] Implementar: User-Agent SEC.
- [ ] [G3-A6-T0393] Testar: throttle.
- [ ] [G3-A6-T0394] Revisar: companyfacts.
- [ ] [G3-A6-T0395] Documentar: XBRL US-GAAP.
- [ ] [G3-A6-T0396] Otimizar: XBRL IFRS.
- [ ] [G3-A6-T0397] Validar: frame CY.
- [ ] [G3-A6-T0398] Medir: FY nunca vira trimestre.
- [ ] [G3-A6-T0399] Automatizar: cache JSON.
- [ ] [G3-A6-T0400] Implementar: 403/429.

### G3-A7
- [ ] [G3-A7-T0401] Testar: download dedup.
- [ ] [G3-A7-T0402] Revisar: magic-bytes.
- [ ] [G3-A7-T0403] Documentar: retry backoff.
- [ ] [G3-A7-T0404] Otimizar: URL canonica.
- [ ] [G3-A7-T0405] Validar: snapshot Investidor10.
- [ ] [G3-A7-T0406] Medir: FAQ JSON-LD.
- [ ] [G3-A7-T0407] Automatizar: trimestre_corrente.
- [ ] [G3-A7-T0408] Implementar: mercado MKT_*.
- [ ] [G3-A7-T0409] Testar: coleta CLI.
- [ ] [G3-A7-T0410] Revisar: BP CIK 0000313807.

### G3-A8
- [ ] [G3-A8-T0411] Documentar: CIKs 7 empresas.
- [ ] [G3-A8-T0412] Otimizar: User-Agent SEC.
- [ ] [G3-A8-T0413] Validar: throttle.
- [ ] [G3-A8-T0414] Medir: companyfacts.
- [ ] [G3-A8-T0415] Automatizar: XBRL US-GAAP.
- [ ] [G3-A8-T0416] Implementar: XBRL IFRS.
- [ ] [G3-A8-T0417] Testar: frame CY.
- [ ] [G3-A8-T0418] Revisar: FY nunca vira trimestre.
- [ ] [G3-A8-T0419] Documentar: cache JSON.
- [ ] [G3-A8-T0420] Otimizar: 403/429.

### G3-A9
- [ ] [G3-A9-T0421] Validar: download dedup.
- [ ] [G3-A9-T0422] Medir: magic-bytes.
- [ ] [G3-A9-T0423] Automatizar: retry backoff.
- [ ] [G3-A9-T0424] Implementar: URL canonica.
- [ ] [G3-A9-T0425] Testar: snapshot Investidor10.
- [ ] [G3-A9-T0426] Revisar: FAQ JSON-LD.
- [ ] [G3-A9-T0427] Documentar: trimestre_corrente.
- [ ] [G3-A9-T0428] Otimizar: mercado MKT_*.
- [ ] [G3-A9-T0429] Validar: coleta CLI.
- [ ] [G3-A9-T0430] Medir: BP CIK 0000313807.

### G3-A10
- [ ] [G3-A10-T0431] Automatizar: CIKs 7 empresas.
- [ ] [G3-A10-T0432] Implementar: User-Agent SEC.
- [ ] [G3-A10-T0433] Testar: throttle.
- [ ] [G3-A10-T0434] Revisar: companyfacts.
- [ ] [G3-A10-T0435] Documentar: XBRL US-GAAP.
- [ ] [G3-A10-T0436] Otimizar: XBRL IFRS.
- [ ] [G3-A10-T0437] Validar: frame CY.
- [ ] [G3-A10-T0438] Medir: FY nunca vira trimestre.
- [ ] [G3-A10-T0439] Automatizar: cache JSON.
- [ ] [G3-A10-T0440] Implementar: 403/429.

### G3-A11
- [ ] [G3-A11-T0441] Testar: download dedup.
- [ ] [G3-A11-T0442] Revisar: magic-bytes.
- [ ] [G3-A11-T0443] Documentar: retry backoff.
- [ ] [G3-A11-T0444] Otimizar: URL canonica.
- [ ] [G3-A11-T0445] Validar: snapshot Investidor10.
- [ ] [G3-A11-T0446] Medir: FAQ JSON-LD.
- [ ] [G3-A11-T0447] Automatizar: trimestre_corrente.
- [ ] [G3-A11-T0448] Implementar: mercado MKT_*.
- [ ] [G3-A11-T0449] Testar: coleta CLI.
- [ ] [G3-A11-T0450] Revisar: BP CIK 0000313807.

### G3-A12
- [ ] [G3-A12-T0451] Documentar: CIKs 7 empresas.
- [ ] [G3-A12-T0452] Otimizar: User-Agent SEC.
- [ ] [G3-A12-T0453] Validar: throttle.
- [ ] [G3-A12-T0454] Medir: companyfacts.
- [ ] [G3-A12-T0455] Automatizar: XBRL US-GAAP.
- [ ] [G3-A12-T0456] Implementar: XBRL IFRS.
- [ ] [G3-A12-T0457] Testar: frame CY.
- [ ] [G3-A12-T0458] Revisar: FY nunca vira trimestre.
- [ ] [G3-A12-T0459] Documentar: cache JSON.
- [ ] [G3-A12-T0460] Otimizar: 403/429.

### G3-A13
- [ ] [G3-A13-T0461] Validar: download dedup.
- [ ] [G3-A13-T0462] Medir: magic-bytes.
- [ ] [G3-A13-T0463] Automatizar: retry backoff.
- [ ] [G3-A13-T0464] Implementar: URL canonica.
- [ ] [G3-A13-T0465] Testar: snapshot Investidor10.
- [ ] [G3-A13-T0466] Revisar: FAQ JSON-LD.
- [ ] [G3-A13-T0467] Documentar: trimestre_corrente.
- [ ] [G3-A13-T0468] Otimizar: mercado MKT_*.
- [ ] [G3-A13-T0469] Validar: coleta CLI.
- [ ] [G3-A13-T0470] Medir: BP CIK 0000313807.

### G3-A14
- [ ] [G3-A14-T0471] Automatizar: CIKs 7 empresas.
- [ ] [G3-A14-T0472] Implementar: User-Agent SEC.
- [ ] [G3-A14-T0473] Testar: throttle.
- [ ] [G3-A14-T0474] Revisar: companyfacts.
- [ ] [G3-A14-T0475] Documentar: XBRL US-GAAP.
- [ ] [G3-A14-T0476] Otimizar: XBRL IFRS.
- [ ] [G3-A14-T0477] Validar: frame CY.
- [ ] [G3-A14-T0478] Medir: FY nunca vira trimestre.
- [ ] [G3-A14-T0479] Automatizar: cache JSON.
- [ ] [G3-A14-T0480] Implementar: 403/429.

### G3-A15
- [ ] [G3-A15-T0481] Testar: download dedup.
- [ ] [G3-A15-T0482] Revisar: magic-bytes.
- [ ] [G3-A15-T0483] Documentar: retry backoff.
- [ ] [G3-A15-T0484] Otimizar: URL canonica.
- [ ] [G3-A15-T0485] Validar: snapshot Investidor10.
- [ ] [G3-A15-T0486] Medir: FAQ JSON-LD.
- [ ] [G3-A15-T0487] Automatizar: trimestre_corrente.
- [ ] [G3-A15-T0488] Implementar: mercado MKT_*.
- [ ] [G3-A15-T0489] Testar: coleta CLI.
- [ ] [G3-A15-T0490] Revisar: BP CIK 0000313807.

### G3-A16
- [ ] [G3-A16-T0491] Documentar: CIKs 7 empresas.
- [ ] [G3-A16-T0492] Otimizar: User-Agent SEC.
- [ ] [G3-A16-T0493] Validar: throttle.
- [ ] [G3-A16-T0494] Medir: companyfacts.
- [ ] [G3-A16-T0495] Automatizar: XBRL US-GAAP.
- [ ] [G3-A16-T0496] Implementar: XBRL IFRS.
- [ ] [G3-A16-T0497] Testar: frame CY.
- [ ] [G3-A16-T0498] Revisar: FY nunca vira trimestre.
- [ ] [G3-A16-T0499] Documentar: cache JSON.
- [ ] [G3-A16-T0500] Otimizar: 403/429.

### G3-A17
- [ ] [G3-A17-T0501] Validar: download dedup.
- [ ] [G3-A17-T0502] Medir: magic-bytes.
- [ ] [G3-A17-T0503] Automatizar: retry backoff.
- [ ] [G3-A17-T0504] Implementar: URL canonica.
- [ ] [G3-A17-T0505] Testar: snapshot Investidor10.
- [ ] [G3-A17-T0506] Revisar: FAQ JSON-LD.
- [ ] [G3-A17-T0507] Documentar: trimestre_corrente.
- [ ] [G3-A17-T0508] Otimizar: mercado MKT_*.
- [ ] [G3-A17-T0509] Validar: coleta CLI.
- [ ] [G3-A17-T0510] Medir: BP CIK 0000313807.

## G4 — Parser tabular (170 tarefas)
_Modulos: `workers/parse_tab.py`_

### G4-A1
- [ ] [G4-A1-T0511] Automatizar: skip ratio.
- [ ] [G4-A1-T0512] Implementar: milhoes vs bilhoes.
- [ ] [G4-A1-T0513] Testar: BRL detect.
- [ ] [G4-A1-T0514] Revisar: numero BR.
- [ ] [G4-A1-T0515] Documentar: parenteses negativos.
- [ ] [G4-A1-T0516] Otimizar: max_col 44.
- [ ] [G4-A1-T0517] Validar: multi-abas.
- [ ] [G4-A1-T0518] Medir: Principais indicadores.
- [ ] [G4-A1-T0519] Automatizar: databook Shell.
- [ ] [G4-A1-T0520] Implementar: supplement Chevron.

### G4-A2
- [ ] [G4-A2-T0521] Testar: databook BP.
- [ ] [G4-A2-T0522] Revisar: databook Total.
- [ ] [G4-A2-T0523] Documentar: dedup rubrica-periodo.
- [ ] [G4-A2-T0524] Otimizar: subtotal invest.
- [ ] [G4-A2-T0525] Validar: footnote markers.
- [ ] [G4-A2-T0526] Medir: 2T26/Q2 2026/2026Q2.
- [ ] [G4-A2-T0527] Automatizar: trimestres nus + ano.
- [ ] [G4-A2-T0528] Implementar: at 6/30.
- [ ] [G4-A2-T0529] Testar: MM/DD/YYYY.
- [ ] [G4-A2-T0530] Revisar: semestres H/S.

### G4-A3
- [ ] [G4-A3-T0531] Documentar: rotulo cols 0-2.
- [ ] [G4-A3-T0532] Otimizar: skip variacao.
- [ ] [G4-A3-T0533] Validar: skip ratio.
- [ ] [G4-A3-T0534] Medir: milhoes vs bilhoes.
- [ ] [G4-A3-T0535] Automatizar: BRL detect.
- [ ] [G4-A3-T0536] Implementar: numero BR.
- [ ] [G4-A3-T0537] Testar: parenteses negativos.
- [ ] [G4-A3-T0538] Revisar: max_col 44.
- [ ] [G4-A3-T0539] Documentar: multi-abas.
- [ ] [G4-A3-T0540] Otimizar: Principais indicadores.

### G4-A4
- [ ] [G4-A4-T0541] Validar: supplement Chevron.
- [ ] [G4-A4-T0542] Medir: supplement Exxon.
- [ ] [G4-A4-T0543] Automatizar: databook BP.
- [ ] [G4-A4-T0544] Implementar: databook Total.
- [ ] [G4-A4-T0545] Testar: dedup rubrica-periodo.
- [ ] [G4-A4-T0546] Revisar: subtotal invest.
- [ ] [G4-A4-T0547] Documentar: footnote markers.
- [ ] [G4-A4-T0548] Otimizar: 2T26/Q2 2026/2026Q2.
- [ ] [G4-A4-T0549] Validar: trimestres nus + ano.
- [ ] [G4-A4-T0550] Medir: at 6/30.

### G4-A5
- [ ] [G4-A5-T0551] Automatizar: semestres H/S.
- [ ] [G4-A5-T0552] Implementar: Three Months Ended.
- [ ] [G4-A5-T0553] Testar: rotulo cols 0-2.
- [ ] [G4-A5-T0554] Revisar: skip variacao.
- [ ] [G4-A5-T0555] Documentar: skip ratio.
- [ ] [G4-A5-T0556] Otimizar: milhoes vs bilhoes.
- [ ] [G4-A5-T0557] Validar: BRL detect.
- [ ] [G4-A5-T0558] Medir: numero BR.
- [ ] [G4-A5-T0559] Automatizar: parenteses negativos.
- [ ] [G4-A5-T0560] Implementar: max_col 44.

### G4-A6
- [ ] [G4-A6-T0561] Testar: Principais indicadores.
- [ ] [G4-A6-T0562] Revisar: databook Shell.
- [ ] [G4-A6-T0563] Documentar: supplement Chevron.
- [ ] [G4-A6-T0564] Otimizar: supplement Exxon.
- [ ] [G4-A6-T0565] Validar: databook BP.
- [ ] [G4-A6-T0566] Medir: databook Total.
- [ ] [G4-A6-T0567] Automatizar: dedup rubrica-periodo.
- [ ] [G4-A6-T0568] Implementar: subtotal invest.
- [ ] [G4-A6-T0569] Testar: footnote markers.
- [ ] [G4-A6-T0570] Revisar: 2T26/Q2 2026/2026Q2.

### G4-A7
- [ ] [G4-A7-T0571] Documentar: at 6/30.
- [ ] [G4-A7-T0572] Otimizar: MM/DD/YYYY.
- [ ] [G4-A7-T0573] Validar: semestres H/S.
- [ ] [G4-A7-T0574] Medir: Three Months Ended.
- [ ] [G4-A7-T0575] Automatizar: rotulo cols 0-2.
- [ ] [G4-A7-T0576] Implementar: skip variacao.
- [ ] [G4-A7-T0577] Testar: skip ratio.
- [ ] [G4-A7-T0578] Revisar: milhoes vs bilhoes.
- [ ] [G4-A7-T0579] Documentar: BRL detect.
- [ ] [G4-A7-T0580] Otimizar: numero BR.

### G4-A8
- [ ] [G4-A8-T0581] Validar: max_col 44.
- [ ] [G4-A8-T0582] Medir: multi-abas.
- [ ] [G4-A8-T0583] Automatizar: Principais indicadores.
- [ ] [G4-A8-T0584] Implementar: databook Shell.
- [ ] [G4-A8-T0585] Testar: supplement Chevron.
- [ ] [G4-A8-T0586] Revisar: supplement Exxon.
- [ ] [G4-A8-T0587] Documentar: databook BP.
- [ ] [G4-A8-T0588] Otimizar: databook Total.
- [ ] [G4-A8-T0589] Validar: dedup rubrica-periodo.
- [ ] [G4-A8-T0590] Medir: subtotal invest.

### G4-A9
- [ ] [G4-A9-T0591] Automatizar: 2T26/Q2 2026/2026Q2.
- [ ] [G4-A9-T0592] Implementar: trimestres nus + ano.
- [ ] [G4-A9-T0593] Testar: at 6/30.
- [ ] [G4-A9-T0594] Revisar: MM/DD/YYYY.
- [ ] [G4-A9-T0595] Documentar: semestres H/S.
- [ ] [G4-A9-T0596] Otimizar: Three Months Ended.
- [ ] [G4-A9-T0597] Validar: rotulo cols 0-2.
- [ ] [G4-A9-T0598] Medir: skip variacao.
- [ ] [G4-A9-T0599] Automatizar: skip ratio.
- [ ] [G4-A9-T0600] Implementar: milhoes vs bilhoes.

### G4-A10
- [ ] [G4-A10-T0601] Testar: numero BR.
- [ ] [G4-A10-T0602] Revisar: parenteses negativos.
- [ ] [G4-A10-T0603] Documentar: max_col 44.
- [ ] [G4-A10-T0604] Otimizar: multi-abas.
- [ ] [G4-A10-T0605] Validar: Principais indicadores.
- [ ] [G4-A10-T0606] Medir: databook Shell.
- [ ] [G4-A10-T0607] Automatizar: supplement Chevron.
- [ ] [G4-A10-T0608] Implementar: supplement Exxon.
- [ ] [G4-A10-T0609] Testar: databook BP.
- [ ] [G4-A10-T0610] Revisar: databook Total.

### G4-A11
- [ ] [G4-A11-T0611] Documentar: subtotal invest.
- [ ] [G4-A11-T0612] Otimizar: footnote markers.
- [ ] [G4-A11-T0613] Validar: 2T26/Q2 2026/2026Q2.
- [ ] [G4-A11-T0614] Medir: trimestres nus + ano.
- [ ] [G4-A11-T0615] Automatizar: at 6/30.
- [ ] [G4-A11-T0616] Implementar: MM/DD/YYYY.
- [ ] [G4-A11-T0617] Testar: semestres H/S.
- [ ] [G4-A11-T0618] Revisar: Three Months Ended.
- [ ] [G4-A11-T0619] Documentar: rotulo cols 0-2.
- [ ] [G4-A11-T0620] Otimizar: skip variacao.

### G4-A12
- [ ] [G4-A12-T0621] Validar: milhoes vs bilhoes.
- [ ] [G4-A12-T0622] Medir: BRL detect.
- [ ] [G4-A12-T0623] Automatizar: numero BR.
- [ ] [G4-A12-T0624] Implementar: parenteses negativos.
- [ ] [G4-A12-T0625] Testar: max_col 44.
- [ ] [G4-A12-T0626] Revisar: multi-abas.
- [ ] [G4-A12-T0627] Documentar: Principais indicadores.
- [ ] [G4-A12-T0628] Otimizar: databook Shell.
- [ ] [G4-A12-T0629] Validar: supplement Chevron.
- [ ] [G4-A12-T0630] Medir: supplement Exxon.

### G4-A13
- [ ] [G4-A13-T0631] Automatizar: databook Total.
- [ ] [G4-A13-T0632] Implementar: dedup rubrica-periodo.
- [ ] [G4-A13-T0633] Testar: subtotal invest.
- [ ] [G4-A13-T0634] Revisar: footnote markers.
- [ ] [G4-A13-T0635] Documentar: 2T26/Q2 2026/2026Q2.
- [ ] [G4-A13-T0636] Otimizar: trimestres nus + ano.
- [ ] [G4-A13-T0637] Validar: at 6/30.
- [ ] [G4-A13-T0638] Medir: MM/DD/YYYY.
- [ ] [G4-A13-T0639] Automatizar: semestres H/S.
- [ ] [G4-A13-T0640] Implementar: Three Months Ended.

### G4-A14
- [ ] [G4-A14-T0641] Testar: skip variacao.
- [ ] [G4-A14-T0642] Revisar: skip ratio.
- [ ] [G4-A14-T0643] Documentar: milhoes vs bilhoes.
- [ ] [G4-A14-T0644] Otimizar: BRL detect.
- [ ] [G4-A14-T0645] Validar: numero BR.
- [ ] [G4-A14-T0646] Medir: parenteses negativos.
- [ ] [G4-A14-T0647] Automatizar: max_col 44.
- [ ] [G4-A14-T0648] Implementar: multi-abas.
- [ ] [G4-A14-T0649] Testar: Principais indicadores.
- [ ] [G4-A14-T0650] Revisar: databook Shell.

### G4-A15
- [ ] [G4-A15-T0651] Documentar: supplement Exxon.
- [ ] [G4-A15-T0652] Otimizar: databook BP.
- [ ] [G4-A15-T0653] Validar: databook Total.
- [ ] [G4-A15-T0654] Medir: dedup rubrica-periodo.
- [ ] [G4-A15-T0655] Automatizar: subtotal invest.
- [ ] [G4-A15-T0656] Implementar: footnote markers.
- [ ] [G4-A15-T0657] Testar: 2T26/Q2 2026/2026Q2.
- [ ] [G4-A15-T0658] Revisar: trimestres nus + ano.
- [ ] [G4-A15-T0659] Documentar: at 6/30.
- [ ] [G4-A15-T0660] Otimizar: MM/DD/YYYY.

### G4-A16
- [ ] [G4-A16-T0661] Validar: Three Months Ended.
- [ ] [G4-A16-T0662] Medir: rotulo cols 0-2.
- [ ] [G4-A16-T0663] Automatizar: skip variacao.
- [ ] [G4-A16-T0664] Implementar: skip ratio.
- [ ] [G4-A16-T0665] Testar: milhoes vs bilhoes.
- [ ] [G4-A16-T0666] Revisar: BRL detect.
- [ ] [G4-A16-T0667] Documentar: numero BR.
- [ ] [G4-A16-T0668] Otimizar: parenteses negativos.
- [ ] [G4-A16-T0669] Validar: max_col 44.
- [ ] [G4-A16-T0670] Medir: multi-abas.

### G4-A17
- [ ] [G4-A17-T0671] Automatizar: databook Shell.
- [ ] [G4-A17-T0672] Implementar: supplement Chevron.
- [ ] [G4-A17-T0673] Testar: supplement Exxon.
- [ ] [G4-A17-T0674] Revisar: databook BP.
- [ ] [G4-A17-T0675] Documentar: databook Total.
- [ ] [G4-A17-T0676] Otimizar: dedup rubrica-periodo.
- [ ] [G4-A17-T0677] Validar: subtotal invest.
- [ ] [G4-A17-T0678] Medir: footnote markers.
- [ ] [G4-A17-T0679] Automatizar: 2T26/Q2 2026/2026Q2.
- [ ] [G4-A17-T0680] Implementar: trimestres nus + ano.

## G5 — Parsers PDF/texto (170 tarefas)
_Modulos: `workers/parse_pdf.py, workers/parse_txt.py`_

### G5-A1
- [ ] [G5-A1-T0681] Testar: EPS per-share.
- [ ] [G5-A1-T0682] Revisar: doc-period hint.
- [ ] [G5-A1-T0683] Documentar: footnote skip.
- [ ] [G5-A1-T0684] Otimizar: texto refluido.
- [ ] [G5-A1-T0685] Validar: docx python-docx.
- [ ] [G5-A1-T0686] Medir: ANNUAL_CUE.
- [ ] [G5-A1-T0687] Automatizar: pymupdf streaming.
- [ ] [G5-A1-T0688] Implementar: pdfplumber tabelas.
- [ ] [G5-A1-T0689] Testar: limite paginas.
- [ ] [G5-A1-T0690] Revisar: triagem ALLOW/SKIP.

### G5-A2
- [ ] [G5-A2-T0691] Documentar: key-figures multi-bloco.
- [ ] [G5-A2-T0692] Otimizar: colunar label+numeros.
- [ ] [G5-A2-T0693] Validar: frases Q explicito.
- [ ] [G5-A2-T0694] Medir: frases ancora quarter.
- [ ] [G5-A2-T0695] Automatizar: frases copulares.
- [ ] [G5-A2-T0696] Implementar: EPS per-share.
- [ ] [G5-A2-T0697] Testar: doc-period hint.
- [ ] [G5-A2-T0698] Revisar: footnote skip.
- [ ] [G5-A2-T0699] Documentar: texto refluido.
- [ ] [G5-A2-T0700] Otimizar: docx python-docx.

### G5-A3
- [ ] [G5-A3-T0701] Validar: pymupdf streaming.
- [ ] [G5-A3-T0702] Medir: pdfplumber tabelas.
- [ ] [G5-A3-T0703] Automatizar: limite paginas.
- [ ] [G5-A3-T0704] Implementar: triagem ALLOW/SKIP.
- [ ] [G5-A3-T0705] Testar: quarter-name fallback.
- [ ] [G5-A3-T0706] Revisar: key-figures multi-bloco.
- [ ] [G5-A3-T0707] Documentar: colunar label+numeros.
- [ ] [G5-A3-T0708] Otimizar: frases Q explicito.
- [ ] [G5-A3-T0709] Validar: frases ancora quarter.
- [ ] [G5-A3-T0710] Medir: frases copulares.

### G5-A4
- [ ] [G5-A4-T0711] Automatizar: doc-period hint.
- [ ] [G5-A4-T0712] Implementar: footnote skip.
- [ ] [G5-A4-T0713] Testar: texto refluido.
- [ ] [G5-A4-T0714] Revisar: docx python-docx.
- [ ] [G5-A4-T0715] Documentar: ANNUAL_CUE.
- [ ] [G5-A4-T0716] Otimizar: pymupdf streaming.
- [ ] [G5-A4-T0717] Validar: pdfplumber tabelas.
- [ ] [G5-A4-T0718] Medir: limite paginas.
- [ ] [G5-A4-T0719] Automatizar: triagem ALLOW/SKIP.
- [ ] [G5-A4-T0720] Implementar: quarter-name fallback.

### G5-A5
- [ ] [G5-A5-T0721] Testar: colunar label+numeros.
- [ ] [G5-A5-T0722] Revisar: frases Q explicito.
- [ ] [G5-A5-T0723] Documentar: frases ancora quarter.
- [ ] [G5-A5-T0724] Otimizar: frases copulares.
- [ ] [G5-A5-T0725] Validar: EPS per-share.
- [ ] [G5-A5-T0726] Medir: doc-period hint.
- [ ] [G5-A5-T0727] Automatizar: footnote skip.
- [ ] [G5-A5-T0728] Implementar: texto refluido.
- [ ] [G5-A5-T0729] Testar: docx python-docx.
- [ ] [G5-A5-T0730] Revisar: ANNUAL_CUE.

### G5-A6
- [ ] [G5-A6-T0731] Documentar: pdfplumber tabelas.
- [ ] [G5-A6-T0732] Otimizar: limite paginas.
- [ ] [G5-A6-T0733] Validar: triagem ALLOW/SKIP.
- [ ] [G5-A6-T0734] Medir: quarter-name fallback.
- [ ] [G5-A6-T0735] Automatizar: key-figures multi-bloco.
- [ ] [G5-A6-T0736] Implementar: colunar label+numeros.
- [ ] [G5-A6-T0737] Testar: frases Q explicito.
- [ ] [G5-A6-T0738] Revisar: frases ancora quarter.
- [ ] [G5-A6-T0739] Documentar: frases copulares.
- [ ] [G5-A6-T0740] Otimizar: EPS per-share.

### G5-A7
- [ ] [G5-A7-T0741] Validar: footnote skip.
- [ ] [G5-A7-T0742] Medir: texto refluido.
- [ ] [G5-A7-T0743] Automatizar: docx python-docx.
- [ ] [G5-A7-T0744] Implementar: ANNUAL_CUE.
- [ ] [G5-A7-T0745] Testar: pymupdf streaming.
- [ ] [G5-A7-T0746] Revisar: pdfplumber tabelas.
- [ ] [G5-A7-T0747] Documentar: limite paginas.
- [ ] [G5-A7-T0748] Otimizar: triagem ALLOW/SKIP.
- [ ] [G5-A7-T0749] Validar: quarter-name fallback.
- [ ] [G5-A7-T0750] Medir: key-figures multi-bloco.

### G5-A8
- [ ] [G5-A8-T0751] Automatizar: frases Q explicito.
- [ ] [G5-A8-T0752] Implementar: frases ancora quarter.
- [ ] [G5-A8-T0753] Testar: frases copulares.
- [ ] [G5-A8-T0754] Revisar: EPS per-share.
- [ ] [G5-A8-T0755] Documentar: doc-period hint.
- [ ] [G5-A8-T0756] Otimizar: footnote skip.
- [ ] [G5-A8-T0757] Validar: texto refluido.
- [ ] [G5-A8-T0758] Medir: docx python-docx.
- [ ] [G5-A8-T0759] Automatizar: ANNUAL_CUE.
- [ ] [G5-A8-T0760] Implementar: pymupdf streaming.

### G5-A9
- [ ] [G5-A9-T0761] Testar: limite paginas.
- [ ] [G5-A9-T0762] Revisar: triagem ALLOW/SKIP.
- [ ] [G5-A9-T0763] Documentar: quarter-name fallback.
- [ ] [G5-A9-T0764] Otimizar: key-figures multi-bloco.
- [ ] [G5-A9-T0765] Validar: colunar label+numeros.
- [ ] [G5-A9-T0766] Medir: frases Q explicito.
- [ ] [G5-A9-T0767] Automatizar: frases ancora quarter.
- [ ] [G5-A9-T0768] Implementar: frases copulares.
- [ ] [G5-A9-T0769] Testar: EPS per-share.
- [ ] [G5-A9-T0770] Revisar: doc-period hint.

### G5-A10
- [ ] [G5-A10-T0771] Documentar: texto refluido.
- [ ] [G5-A10-T0772] Otimizar: docx python-docx.
- [ ] [G5-A10-T0773] Validar: ANNUAL_CUE.
- [ ] [G5-A10-T0774] Medir: pymupdf streaming.
- [ ] [G5-A10-T0775] Automatizar: pdfplumber tabelas.
- [ ] [G5-A10-T0776] Implementar: limite paginas.
- [ ] [G5-A10-T0777] Testar: triagem ALLOW/SKIP.
- [ ] [G5-A10-T0778] Revisar: quarter-name fallback.
- [ ] [G5-A10-T0779] Documentar: key-figures multi-bloco.
- [ ] [G5-A10-T0780] Otimizar: colunar label+numeros.

### G5-A11
- [ ] [G5-A11-T0781] Validar: frases ancora quarter.
- [ ] [G5-A11-T0782] Medir: frases copulares.
- [ ] [G5-A11-T0783] Automatizar: EPS per-share.
- [ ] [G5-A11-T0784] Implementar: doc-period hint.
- [ ] [G5-A11-T0785] Testar: footnote skip.
- [ ] [G5-A11-T0786] Revisar: texto refluido.
- [ ] [G5-A11-T0787] Documentar: docx python-docx.
- [ ] [G5-A11-T0788] Otimizar: ANNUAL_CUE.
- [ ] [G5-A11-T0789] Validar: pymupdf streaming.
- [ ] [G5-A11-T0790] Medir: pdfplumber tabelas.

### G5-A12
- [ ] [G5-A12-T0791] Automatizar: triagem ALLOW/SKIP.
- [ ] [G5-A12-T0792] Implementar: quarter-name fallback.
- [ ] [G5-A12-T0793] Testar: key-figures multi-bloco.
- [ ] [G5-A12-T0794] Revisar: colunar label+numeros.
- [ ] [G5-A12-T0795] Documentar: frases Q explicito.
- [ ] [G5-A12-T0796] Otimizar: frases ancora quarter.
- [ ] [G5-A12-T0797] Validar: frases copulares.
- [ ] [G5-A12-T0798] Medir: EPS per-share.
- [ ] [G5-A12-T0799] Automatizar: doc-period hint.
- [ ] [G5-A12-T0800] Implementar: footnote skip.

### G5-A13
- [ ] [G5-A13-T0801] Testar: docx python-docx.
- [ ] [G5-A13-T0802] Revisar: ANNUAL_CUE.
- [ ] [G5-A13-T0803] Documentar: pymupdf streaming.
- [ ] [G5-A13-T0804] Otimizar: pdfplumber tabelas.
- [ ] [G5-A13-T0805] Validar: limite paginas.
- [ ] [G5-A13-T0806] Medir: triagem ALLOW/SKIP.
- [ ] [G5-A13-T0807] Automatizar: quarter-name fallback.
- [ ] [G5-A13-T0808] Implementar: key-figures multi-bloco.
- [ ] [G5-A13-T0809] Testar: colunar label+numeros.
- [ ] [G5-A13-T0810] Revisar: frases Q explicito.

### G5-A14
- [ ] [G5-A14-T0811] Documentar: frases copulares.
- [ ] [G5-A14-T0812] Otimizar: EPS per-share.
- [ ] [G5-A14-T0813] Validar: doc-period hint.
- [ ] [G5-A14-T0814] Medir: footnote skip.
- [ ] [G5-A14-T0815] Automatizar: texto refluido.
- [ ] [G5-A14-T0816] Implementar: docx python-docx.
- [ ] [G5-A14-T0817] Testar: ANNUAL_CUE.
- [ ] [G5-A14-T0818] Revisar: pymupdf streaming.
- [ ] [G5-A14-T0819] Documentar: pdfplumber tabelas.
- [ ] [G5-A14-T0820] Otimizar: limite paginas.

### G5-A15
- [ ] [G5-A15-T0821] Validar: quarter-name fallback.
- [ ] [G5-A15-T0822] Medir: key-figures multi-bloco.
- [ ] [G5-A15-T0823] Automatizar: colunar label+numeros.
- [ ] [G5-A15-T0824] Implementar: frases Q explicito.
- [ ] [G5-A15-T0825] Testar: frases ancora quarter.
- [ ] [G5-A15-T0826] Revisar: frases copulares.
- [ ] [G5-A15-T0827] Documentar: EPS per-share.
- [ ] [G5-A15-T0828] Otimizar: doc-period hint.
- [ ] [G5-A15-T0829] Validar: footnote skip.
- [ ] [G5-A15-T0830] Medir: texto refluido.

### G5-A16
- [ ] [G5-A16-T0831] Automatizar: ANNUAL_CUE.
- [ ] [G5-A16-T0832] Implementar: pymupdf streaming.
- [ ] [G5-A16-T0833] Testar: pdfplumber tabelas.
- [ ] [G5-A16-T0834] Revisar: limite paginas.
- [ ] [G5-A16-T0835] Documentar: triagem ALLOW/SKIP.
- [ ] [G5-A16-T0836] Otimizar: quarter-name fallback.
- [ ] [G5-A16-T0837] Validar: key-figures multi-bloco.
- [ ] [G5-A16-T0838] Medir: colunar label+numeros.
- [ ] [G5-A16-T0839] Automatizar: frases Q explicito.
- [ ] [G5-A16-T0840] Implementar: frases ancora quarter.

### G5-A17
- [ ] [G5-A17-T0841] Testar: EPS per-share.
- [ ] [G5-A17-T0842] Revisar: doc-period hint.
- [ ] [G5-A17-T0843] Documentar: footnote skip.
- [ ] [G5-A17-T0844] Otimizar: texto refluido.
- [ ] [G5-A17-T0845] Validar: docx python-docx.
- [ ] [G5-A17-T0846] Medir: ANNUAL_CUE.
- [ ] [G5-A17-T0847] Automatizar: pymupdf streaming.
- [ ] [G5-A17-T0848] Implementar: pdfplumber tabelas.
- [ ] [G5-A17-T0849] Testar: limite paginas.
- [ ] [G5-A17-T0850] Revisar: triagem ALLOW/SKIP.

## G6 — Qualidade e auditoria (170 tarefas)
_Modulos: `workers/quality.py, workers/derived.py`_

### G6-A1
- [ ] [G6-A1-T0851] Documentar: EVIDENCIAS_QUALIDADE.
- [ ] [G6-A1-T0852] Otimizar: PTAX fechamento.
- [ ] [G6-A1-T0853] Validar: INVALID_NEGATIVE.
- [ ] [G6-A1-T0854] Medir: VARIATION_SPIKE.
- [ ] [G6-A1-T0855] Automatizar: confianca<0.70.
- [ ] [G6-A1-T0856] Implementar: cobertura.
- [ ] [G6-A1-T0857] Testar: DIVERGENCIA_FONTE.
- [ ] [G6-A1-T0858] Revisar: margens derivadas.
- [ ] [G6-A1-T0859] Documentar: alavancagem.
- [ ] [G6-A1-T0860] Otimizar: severidades.

### G6-A2
- [ ] [G6-A2-T0861] Validar: dedup evidencias.
- [ ] [G6-A2-T0862] Medir: spike Chevron.
- [ ] [G6-A2-T0863] Automatizar: margem implausivel.
- [ ] [G6-A2-T0864] Implementar: EVIDENCIAS_QUALIDADE.
- [ ] [G6-A2-T0865] Testar: PTAX fechamento.
- [ ] [G6-A2-T0866] Revisar: INVALID_NEGATIVE.
- [ ] [G6-A2-T0867] Documentar: VARIATION_SPIKE.
- [ ] [G6-A2-T0868] Otimizar: confianca<0.70.
- [ ] [G6-A2-T0869] Validar: cobertura.
- [ ] [G6-A2-T0870] Medir: DIVERGENCIA_FONTE.

### G6-A3
- [ ] [G6-A3-T0871] Automatizar: alavancagem.
- [ ] [G6-A3-T0872] Implementar: severidades.
- [ ] [G6-A3-T0873] Testar: review ABERTO.
- [ ] [G6-A3-T0874] Revisar: dedup evidencias.
- [ ] [G6-A3-T0875] Documentar: spike Chevron.
- [ ] [G6-A3-T0876] Otimizar: margem implausivel.
- [ ] [G6-A3-T0877] Validar: EVIDENCIAS_QUALIDADE.
- [ ] [G6-A3-T0878] Medir: PTAX fechamento.
- [ ] [G6-A3-T0879] Automatizar: INVALID_NEGATIVE.
- [ ] [G6-A3-T0880] Implementar: VARIATION_SPIKE.

### G6-A4
- [ ] [G6-A4-T0881] Testar: cobertura.
- [ ] [G6-A4-T0882] Revisar: DIVERGENCIA_FONTE.
- [ ] [G6-A4-T0883] Documentar: margens derivadas.
- [ ] [G6-A4-T0884] Otimizar: alavancagem.
- [ ] [G6-A4-T0885] Validar: severidades.
- [ ] [G6-A4-T0886] Medir: review ABERTO.
- [ ] [G6-A4-T0887] Automatizar: dedup evidencias.
- [ ] [G6-A4-T0888] Implementar: spike Chevron.
- [ ] [G6-A4-T0889] Testar: margem implausivel.
- [ ] [G6-A4-T0890] Revisar: EVIDENCIAS_QUALIDADE.

### G6-A5
- [ ] [G6-A5-T0891] Documentar: INVALID_NEGATIVE.
- [ ] [G6-A5-T0892] Otimizar: VARIATION_SPIKE.
- [ ] [G6-A5-T0893] Validar: confianca<0.70.
- [ ] [G6-A5-T0894] Medir: cobertura.
- [ ] [G6-A5-T0895] Automatizar: DIVERGENCIA_FONTE.
- [ ] [G6-A5-T0896] Implementar: margens derivadas.
- [ ] [G6-A5-T0897] Testar: alavancagem.
- [ ] [G6-A5-T0898] Revisar: severidades.
- [ ] [G6-A5-T0899] Documentar: review ABERTO.
- [ ] [G6-A5-T0900] Otimizar: dedup evidencias.

### G6-A6
- [ ] [G6-A6-T0901] Validar: margem implausivel.
- [ ] [G6-A6-T0902] Medir: EVIDENCIAS_QUALIDADE.
- [ ] [G6-A6-T0903] Automatizar: PTAX fechamento.
- [ ] [G6-A6-T0904] Implementar: INVALID_NEGATIVE.
- [ ] [G6-A6-T0905] Testar: VARIATION_SPIKE.
- [ ] [G6-A6-T0906] Revisar: confianca<0.70.
- [ ] [G6-A6-T0907] Documentar: cobertura.
- [ ] [G6-A6-T0908] Otimizar: DIVERGENCIA_FONTE.
- [ ] [G6-A6-T0909] Validar: margens derivadas.
- [ ] [G6-A6-T0910] Medir: alavancagem.

### G6-A7
- [ ] [G6-A7-T0911] Automatizar: review ABERTO.
- [ ] [G6-A7-T0912] Implementar: dedup evidencias.
- [ ] [G6-A7-T0913] Testar: spike Chevron.
- [ ] [G6-A7-T0914] Revisar: margem implausivel.
- [ ] [G6-A7-T0915] Documentar: EVIDENCIAS_QUALIDADE.
- [ ] [G6-A7-T0916] Otimizar: PTAX fechamento.
- [ ] [G6-A7-T0917] Validar: INVALID_NEGATIVE.
- [ ] [G6-A7-T0918] Medir: VARIATION_SPIKE.
- [ ] [G6-A7-T0919] Automatizar: confianca<0.70.
- [ ] [G6-A7-T0920] Implementar: cobertura.

### G6-A8
- [ ] [G6-A8-T0921] Testar: margens derivadas.
- [ ] [G6-A8-T0922] Revisar: alavancagem.
- [ ] [G6-A8-T0923] Documentar: severidades.
- [ ] [G6-A8-T0924] Otimizar: review ABERTO.
- [ ] [G6-A8-T0925] Validar: dedup evidencias.
- [ ] [G6-A8-T0926] Medir: spike Chevron.
- [ ] [G6-A8-T0927] Automatizar: margem implausivel.
- [ ] [G6-A8-T0928] Implementar: EVIDENCIAS_QUALIDADE.
- [ ] [G6-A8-T0929] Testar: PTAX fechamento.
- [ ] [G6-A8-T0930] Revisar: INVALID_NEGATIVE.

### G6-A9
- [ ] [G6-A9-T0931] Documentar: confianca<0.70.
- [ ] [G6-A9-T0932] Otimizar: cobertura.
- [ ] [G6-A9-T0933] Validar: DIVERGENCIA_FONTE.
- [ ] [G6-A9-T0934] Medir: margens derivadas.
- [ ] [G6-A9-T0935] Automatizar: alavancagem.
- [ ] [G6-A9-T0936] Implementar: severidades.
- [ ] [G6-A9-T0937] Testar: review ABERTO.
- [ ] [G6-A9-T0938] Revisar: dedup evidencias.
- [ ] [G6-A9-T0939] Documentar: spike Chevron.
- [ ] [G6-A9-T0940] Otimizar: margem implausivel.

### G6-A10
- [ ] [G6-A10-T0941] Validar: PTAX fechamento.
- [ ] [G6-A10-T0942] Medir: INVALID_NEGATIVE.
- [ ] [G6-A10-T0943] Automatizar: VARIATION_SPIKE.
- [ ] [G6-A10-T0944] Implementar: confianca<0.70.
- [ ] [G6-A10-T0945] Testar: cobertura.
- [ ] [G6-A10-T0946] Revisar: DIVERGENCIA_FONTE.
- [ ] [G6-A10-T0947] Documentar: margens derivadas.
- [ ] [G6-A10-T0948] Otimizar: alavancagem.
- [ ] [G6-A10-T0949] Validar: severidades.
- [ ] [G6-A10-T0950] Medir: review ABERTO.

### G6-A11
- [ ] [G6-A11-T0951] Automatizar: spike Chevron.
- [ ] [G6-A11-T0952] Implementar: margem implausivel.
- [ ] [G6-A11-T0953] Testar: EVIDENCIAS_QUALIDADE.
- [ ] [G6-A11-T0954] Revisar: PTAX fechamento.
- [ ] [G6-A11-T0955] Documentar: INVALID_NEGATIVE.
- [ ] [G6-A11-T0956] Otimizar: VARIATION_SPIKE.
- [ ] [G6-A11-T0957] Validar: confianca<0.70.
- [ ] [G6-A11-T0958] Medir: cobertura.
- [ ] [G6-A11-T0959] Automatizar: DIVERGENCIA_FONTE.
- [ ] [G6-A11-T0960] Implementar: margens derivadas.

### G6-A12
- [ ] [G6-A12-T0961] Testar: severidades.
- [ ] [G6-A12-T0962] Revisar: review ABERTO.
- [ ] [G6-A12-T0963] Documentar: dedup evidencias.
- [ ] [G6-A12-T0964] Otimizar: spike Chevron.
- [ ] [G6-A12-T0965] Validar: margem implausivel.
- [ ] [G6-A12-T0966] Medir: EVIDENCIAS_QUALIDADE.
- [ ] [G6-A12-T0967] Automatizar: PTAX fechamento.
- [ ] [G6-A12-T0968] Implementar: INVALID_NEGATIVE.
- [ ] [G6-A12-T0969] Testar: VARIATION_SPIKE.
- [ ] [G6-A12-T0970] Revisar: confianca<0.70.

### G6-A13
- [ ] [G6-A13-T0971] Documentar: DIVERGENCIA_FONTE.
- [ ] [G6-A13-T0972] Otimizar: margens derivadas.
- [ ] [G6-A13-T0973] Validar: alavancagem.
- [ ] [G6-A13-T0974] Medir: severidades.
- [ ] [G6-A13-T0975] Automatizar: review ABERTO.
- [ ] [G6-A13-T0976] Implementar: dedup evidencias.
- [ ] [G6-A13-T0977] Testar: spike Chevron.
- [ ] [G6-A13-T0978] Revisar: margem implausivel.
- [ ] [G6-A13-T0979] Documentar: EVIDENCIAS_QUALIDADE.
- [ ] [G6-A13-T0980] Otimizar: PTAX fechamento.

### G6-A14
- [ ] [G6-A14-T0981] Validar: VARIATION_SPIKE.
- [ ] [G6-A14-T0982] Medir: confianca<0.70.
- [ ] [G6-A14-T0983] Automatizar: cobertura.
- [ ] [G6-A14-T0984] Implementar: DIVERGENCIA_FONTE.
- [ ] [G6-A14-T0985] Testar: margens derivadas.
- [ ] [G6-A14-T0986] Revisar: alavancagem.
- [ ] [G6-A14-T0987] Documentar: severidades.
- [ ] [G6-A14-T0988] Otimizar: review ABERTO.
- [ ] [G6-A14-T0989] Validar: dedup evidencias.
- [ ] [G6-A14-T0990] Medir: spike Chevron.

### G6-A15
- [ ] [G6-A15-T0991] Automatizar: EVIDENCIAS_QUALIDADE.
- [ ] [G6-A15-T0992] Implementar: PTAX fechamento.
- [ ] [G6-A15-T0993] Testar: INVALID_NEGATIVE.
- [ ] [G6-A15-T0994] Revisar: VARIATION_SPIKE.
- [ ] [G6-A15-T0995] Documentar: confianca<0.70.
- [ ] [G6-A15-T0996] Otimizar: cobertura.
- [ ] [G6-A15-T0997] Validar: DIVERGENCIA_FONTE.
- [ ] [G6-A15-T0998] Medir: margens derivadas.
- [ ] [G6-A15-T0999] Automatizar: alavancagem.
- [ ] [G6-A15-T1000] Implementar: severidades.

### G6-A16
- [ ] [G6-A16-T1001] Testar: dedup evidencias.
- [ ] [G6-A16-T1002] Revisar: spike Chevron.
- [ ] [G6-A16-T1003] Documentar: margem implausivel.
- [ ] [G6-A16-T1004] Otimizar: EVIDENCIAS_QUALIDADE.
- [ ] [G6-A16-T1005] Validar: PTAX fechamento.
- [ ] [G6-A16-T1006] Medir: INVALID_NEGATIVE.
- [ ] [G6-A16-T1007] Automatizar: VARIATION_SPIKE.
- [ ] [G6-A16-T1008] Implementar: confianca<0.70.
- [ ] [G6-A16-T1009] Testar: cobertura.
- [ ] [G6-A16-T1010] Revisar: DIVERGENCIA_FONTE.

### G6-A17
- [ ] [G6-A17-T1011] Documentar: alavancagem.
- [ ] [G6-A17-T1012] Otimizar: severidades.
- [ ] [G6-A17-T1013] Validar: review ABERTO.
- [ ] [G6-A17-T1014] Medir: dedup evidencias.
- [ ] [G6-A17-T1015] Automatizar: spike Chevron.
- [ ] [G6-A17-T1016] Implementar: margem implausivel.
- [ ] [G6-A17-T1017] Testar: EVIDENCIAS_QUALIDADE.
- [ ] [G6-A17-T1018] Revisar: PTAX fechamento.
- [ ] [G6-A17-T1019] Documentar: INVALID_NEGATIVE.
- [ ] [G6-A17-T1020] Otimizar: VARIATION_SPIKE.

## G7 — Views Web (170 tarefas)
_Modulos: `views/web_app.py`_

### G7-A1
- [ ] [G7-A1-T1021] Validar: KPI cards.
- [ ] [G7-A1-T1022] Medir: matriz + tooltips.
- [ ] [G7-A1-T1023] Automatizar: mercado strip.
- [ ] [G7-A1-T1024] Implementar: rentabilidade strip.
- [ ] [G7-A1-T1025] Testar: filtros qsel/empresa.
- [ ] [G7-A1-T1026] Revisar: moeda BRL.
- [ ] [G7-A1-T1027] Documentar: GRID_H preservado.
- [ ] [G7-A1-T1028] Otimizar: paginacao.
- [ ] [G7-A1-T1029] Validar: resize.
- [ ] [G7-A1-T1030] Medir: twrap.

### G7-A2
- [ ] [G7-A2-T1031] Automatizar: mailto.
- [ ] [G7-A2-T1032] Implementar: sidebar 25/75.
- [ ] [G7-A2-T1033] Testar: accordions.
- [ ] [G7-A2-T1034] Revisar: colapso total.
- [ ] [G7-A2-T1035] Documentar: tabs fora sidebar.
- [ ] [G7-A2-T1036] Otimizar: grid NxM.
- [ ] [G7-A2-T1037] Validar: temas light/dark.
- [ ] [G7-A2-T1038] Medir: barras Plotly.
- [ ] [G7-A2-T1039] Automatizar: series linhas.
- [ ] [G7-A2-T1040] Implementar: hover unificado.

### G7-A3
- [ ] [G7-A3-T1041] Testar: KPI cards.
- [ ] [G7-A3-T1042] Revisar: matriz + tooltips.
- [ ] [G7-A3-T1043] Documentar: mercado strip.
- [ ] [G7-A3-T1044] Otimizar: rentabilidade strip.
- [ ] [G7-A3-T1045] Validar: filtros qsel/empresa.
- [ ] [G7-A3-T1046] Medir: moeda BRL.
- [ ] [G7-A3-T1047] Automatizar: GRID_H preservado.
- [ ] [G7-A3-T1048] Implementar: paginacao.
- [ ] [G7-A3-T1049] Testar: resize.
- [ ] [G7-A3-T1050] Revisar: twrap.

### G7-A4
- [ ] [G7-A4-T1051] Documentar: mailto.
- [ ] [G7-A4-T1052] Otimizar: sidebar 25/75.
- [ ] [G7-A4-T1053] Validar: accordions.
- [ ] [G7-A4-T1054] Medir: colapso total.
- [ ] [G7-A4-T1055] Automatizar: tabs fora sidebar.
- [ ] [G7-A4-T1056] Implementar: grid NxM.
- [ ] [G7-A4-T1057] Testar: temas light/dark.
- [ ] [G7-A4-T1058] Revisar: barras Plotly.
- [ ] [G7-A4-T1059] Documentar: series linhas.
- [ ] [G7-A4-T1060] Otimizar: hover unificado.

### G7-A5
- [ ] [G7-A5-T1061] Validar: KPI cards.
- [ ] [G7-A5-T1062] Medir: matriz + tooltips.
- [ ] [G7-A5-T1063] Automatizar: mercado strip.
- [ ] [G7-A5-T1064] Implementar: rentabilidade strip.
- [ ] [G7-A5-T1065] Testar: filtros qsel/empresa.
- [ ] [G7-A5-T1066] Revisar: moeda BRL.
- [ ] [G7-A5-T1067] Documentar: GRID_H preservado.
- [ ] [G7-A5-T1068] Otimizar: paginacao.
- [ ] [G7-A5-T1069] Validar: resize.
- [ ] [G7-A5-T1070] Medir: twrap.

### G7-A6
- [ ] [G7-A6-T1071] Automatizar: mailto.
- [ ] [G7-A6-T1072] Implementar: sidebar 25/75.
- [ ] [G7-A6-T1073] Testar: accordions.
- [ ] [G7-A6-T1074] Revisar: colapso total.
- [ ] [G7-A6-T1075] Documentar: tabs fora sidebar.
- [ ] [G7-A6-T1076] Otimizar: grid NxM.
- [ ] [G7-A6-T1077] Validar: temas light/dark.
- [ ] [G7-A6-T1078] Medir: barras Plotly.
- [ ] [G7-A6-T1079] Automatizar: series linhas.
- [ ] [G7-A6-T1080] Implementar: hover unificado.

### G7-A7
- [ ] [G7-A7-T1081] Testar: KPI cards.
- [ ] [G7-A7-T1082] Revisar: matriz + tooltips.
- [ ] [G7-A7-T1083] Documentar: mercado strip.
- [ ] [G7-A7-T1084] Otimizar: rentabilidade strip.
- [ ] [G7-A7-T1085] Validar: filtros qsel/empresa.
- [ ] [G7-A7-T1086] Medir: moeda BRL.
- [ ] [G7-A7-T1087] Automatizar: GRID_H preservado.
- [ ] [G7-A7-T1088] Implementar: paginacao.
- [ ] [G7-A7-T1089] Testar: resize.
- [ ] [G7-A7-T1090] Revisar: twrap.

### G7-A8
- [ ] [G7-A8-T1091] Documentar: mailto.
- [ ] [G7-A8-T1092] Otimizar: sidebar 25/75.
- [ ] [G7-A8-T1093] Validar: accordions.
- [ ] [G7-A8-T1094] Medir: colapso total.
- [ ] [G7-A8-T1095] Automatizar: tabs fora sidebar.
- [ ] [G7-A8-T1096] Implementar: grid NxM.
- [ ] [G7-A8-T1097] Testar: temas light/dark.
- [ ] [G7-A8-T1098] Revisar: barras Plotly.
- [ ] [G7-A8-T1099] Documentar: series linhas.
- [ ] [G7-A8-T1100] Otimizar: hover unificado.

### G7-A9
- [ ] [G7-A9-T1101] Validar: KPI cards.
- [ ] [G7-A9-T1102] Medir: matriz + tooltips.
- [ ] [G7-A9-T1103] Automatizar: mercado strip.
- [ ] [G7-A9-T1104] Implementar: rentabilidade strip.
- [ ] [G7-A9-T1105] Testar: filtros qsel/empresa.
- [ ] [G7-A9-T1106] Revisar: moeda BRL.
- [ ] [G7-A9-T1107] Documentar: GRID_H preservado.
- [ ] [G7-A9-T1108] Otimizar: paginacao.
- [ ] [G7-A9-T1109] Validar: resize.
- [ ] [G7-A9-T1110] Medir: twrap.

### G7-A10
- [ ] [G7-A10-T1111] Automatizar: mailto.
- [ ] [G7-A10-T1112] Implementar: sidebar 25/75.
- [ ] [G7-A10-T1113] Testar: accordions.
- [ ] [G7-A10-T1114] Revisar: colapso total.
- [ ] [G7-A10-T1115] Documentar: tabs fora sidebar.
- [ ] [G7-A10-T1116] Otimizar: grid NxM.
- [ ] [G7-A10-T1117] Validar: temas light/dark.
- [ ] [G7-A10-T1118] Medir: barras Plotly.
- [ ] [G7-A10-T1119] Automatizar: series linhas.
- [ ] [G7-A10-T1120] Implementar: hover unificado.

### G7-A11
- [ ] [G7-A11-T1121] Testar: KPI cards.
- [ ] [G7-A11-T1122] Revisar: matriz + tooltips.
- [ ] [G7-A11-T1123] Documentar: mercado strip.
- [ ] [G7-A11-T1124] Otimizar: rentabilidade strip.
- [ ] [G7-A11-T1125] Validar: filtros qsel/empresa.
- [ ] [G7-A11-T1126] Medir: moeda BRL.
- [ ] [G7-A11-T1127] Automatizar: GRID_H preservado.
- [ ] [G7-A11-T1128] Implementar: paginacao.
- [ ] [G7-A11-T1129] Testar: resize.
- [ ] [G7-A11-T1130] Revisar: twrap.

### G7-A12
- [ ] [G7-A12-T1131] Documentar: mailto.
- [ ] [G7-A12-T1132] Otimizar: sidebar 25/75.
- [ ] [G7-A12-T1133] Validar: accordions.
- [ ] [G7-A12-T1134] Medir: colapso total.
- [ ] [G7-A12-T1135] Automatizar: tabs fora sidebar.
- [ ] [G7-A12-T1136] Implementar: grid NxM.
- [ ] [G7-A12-T1137] Testar: temas light/dark.
- [ ] [G7-A12-T1138] Revisar: barras Plotly.
- [ ] [G7-A12-T1139] Documentar: series linhas.
- [ ] [G7-A12-T1140] Otimizar: hover unificado.

### G7-A13
- [ ] [G7-A13-T1141] Validar: KPI cards.
- [ ] [G7-A13-T1142] Medir: matriz + tooltips.
- [ ] [G7-A13-T1143] Automatizar: mercado strip.
- [ ] [G7-A13-T1144] Implementar: rentabilidade strip.
- [ ] [G7-A13-T1145] Testar: filtros qsel/empresa.
- [ ] [G7-A13-T1146] Revisar: moeda BRL.
- [ ] [G7-A13-T1147] Documentar: GRID_H preservado.
- [ ] [G7-A13-T1148] Otimizar: paginacao.
- [ ] [G7-A13-T1149] Validar: resize.
- [ ] [G7-A13-T1150] Medir: twrap.

### G7-A14
- [ ] [G7-A14-T1151] Automatizar: mailto.
- [ ] [G7-A14-T1152] Implementar: sidebar 25/75.
- [ ] [G7-A14-T1153] Testar: accordions.
- [ ] [G7-A14-T1154] Revisar: colapso total.
- [ ] [G7-A14-T1155] Documentar: tabs fora sidebar.
- [ ] [G7-A14-T1156] Otimizar: grid NxM.
- [ ] [G7-A14-T1157] Validar: temas light/dark.
- [ ] [G7-A14-T1158] Medir: barras Plotly.
- [ ] [G7-A14-T1159] Automatizar: series linhas.
- [ ] [G7-A14-T1160] Implementar: hover unificado.

### G7-A15
- [ ] [G7-A15-T1161] Testar: KPI cards.
- [ ] [G7-A15-T1162] Revisar: matriz + tooltips.
- [ ] [G7-A15-T1163] Documentar: mercado strip.
- [ ] [G7-A15-T1164] Otimizar: rentabilidade strip.
- [ ] [G7-A15-T1165] Validar: filtros qsel/empresa.
- [ ] [G7-A15-T1166] Medir: moeda BRL.
- [ ] [G7-A15-T1167] Automatizar: GRID_H preservado.
- [ ] [G7-A15-T1168] Implementar: paginacao.
- [ ] [G7-A15-T1169] Testar: resize.
- [ ] [G7-A15-T1170] Revisar: twrap.

### G7-A16
- [ ] [G7-A16-T1171] Documentar: mailto.
- [ ] [G7-A16-T1172] Otimizar: sidebar 25/75.
- [ ] [G7-A16-T1173] Validar: accordions.
- [ ] [G7-A16-T1174] Medir: colapso total.
- [ ] [G7-A16-T1175] Automatizar: tabs fora sidebar.
- [ ] [G7-A16-T1176] Implementar: grid NxM.
- [ ] [G7-A16-T1177] Testar: temas light/dark.
- [ ] [G7-A16-T1178] Revisar: barras Plotly.
- [ ] [G7-A16-T1179] Documentar: series linhas.
- [ ] [G7-A16-T1180] Otimizar: hover unificado.

### G7-A17
- [ ] [G7-A17-T1181] Validar: KPI cards.
- [ ] [G7-A17-T1182] Medir: matriz + tooltips.
- [ ] [G7-A17-T1183] Automatizar: mercado strip.
- [ ] [G7-A17-T1184] Implementar: rentabilidade strip.
- [ ] [G7-A17-T1185] Testar: filtros qsel/empresa.
- [ ] [G7-A17-T1186] Revisar: moeda BRL.
- [ ] [G7-A17-T1187] Documentar: GRID_H preservado.
- [ ] [G7-A17-T1188] Otimizar: paginacao.
- [ ] [G7-A17-T1189] Validar: resize.
- [ ] [G7-A17-T1190] Medir: twrap.

## G8 — Views GUI (170 tarefas)
_Modulos: `views/gui_app.py`_

### G8-A1
- [ ] [G8-A1-T1191] Automatizar: periodo/moeda form.
- [ ] [G8-A1-T1192] Implementar: QTabWidget 4 abas.
- [ ] [G8-A1-T1193] Testar: pyqtgraph barras.
- [ ] [G8-A1-T1194] Revisar: cores por empresa.
- [ ] [G8-A1-T1195] Documentar: media tracejada.
- [ ] [G8-A1-T1196] Otimizar: headroom rotulos.
- [ ] [G8-A1-T1197] Validar: stagger colisao.
- [ ] [G8-A1-T1198] Medir: paginacao tabelas.
- [ ] [G8-A1-T1199] Automatizar: temas QSS.
- [ ] [G8-A1-T1200] Implementar: status bar.

### G8-A2
- [ ] [G8-A2-T1201] Testar: moeda reativa.
- [ ] [G8-A2-T1202] Revisar: colapso total.
- [ ] [G8-A2-T1203] Documentar: show_btn.
- [ ] [G8-A2-T1204] Otimizar: QSplitter 25/75.
- [ ] [G8-A2-T1205] Validar: handle estilizado.
- [ ] [G8-A2-T1206] Medir: QToolBox topo.
- [ ] [G8-A2-T1207] Automatizar: empresas em grid.
- [ ] [G8-A2-T1208] Implementar: periodo/moeda form.
- [ ] [G8-A2-T1209] Testar: QTabWidget 4 abas.
- [ ] [G8-A2-T1210] Revisar: pyqtgraph barras.

### G8-A3
- [ ] [G8-A3-T1211] Documentar: media tracejada.
- [ ] [G8-A3-T1212] Otimizar: headroom rotulos.
- [ ] [G8-A3-T1213] Validar: stagger colisao.
- [ ] [G8-A3-T1214] Medir: paginacao tabelas.
- [ ] [G8-A3-T1215] Automatizar: temas QSS.
- [ ] [G8-A3-T1216] Implementar: status bar.
- [ ] [G8-A3-T1217] Testar: periodo reativo.
- [ ] [G8-A3-T1218] Revisar: moeda reativa.
- [ ] [G8-A3-T1219] Documentar: colapso total.
- [ ] [G8-A3-T1220] Otimizar: show_btn.

### G8-A4
- [ ] [G8-A4-T1221] Validar: handle estilizado.
- [ ] [G8-A4-T1222] Medir: QToolBox topo.
- [ ] [G8-A4-T1223] Automatizar: empresas em grid.
- [ ] [G8-A4-T1224] Implementar: periodo/moeda form.
- [ ] [G8-A4-T1225] Testar: QTabWidget 4 abas.
- [ ] [G8-A4-T1226] Revisar: pyqtgraph barras.
- [ ] [G8-A4-T1227] Documentar: cores por empresa.
- [ ] [G8-A4-T1228] Otimizar: media tracejada.
- [ ] [G8-A4-T1229] Validar: headroom rotulos.
- [ ] [G8-A4-T1230] Medir: stagger colisao.

### G8-A5
- [ ] [G8-A5-T1231] Automatizar: temas QSS.
- [ ] [G8-A5-T1232] Implementar: status bar.
- [ ] [G8-A5-T1233] Testar: periodo reativo.
- [ ] [G8-A5-T1234] Revisar: moeda reativa.
- [ ] [G8-A5-T1235] Documentar: colapso total.
- [ ] [G8-A5-T1236] Otimizar: show_btn.
- [ ] [G8-A5-T1237] Validar: QSplitter 25/75.
- [ ] [G8-A5-T1238] Medir: handle estilizado.
- [ ] [G8-A5-T1239] Automatizar: QToolBox topo.
- [ ] [G8-A5-T1240] Implementar: empresas em grid.

### G8-A6
- [ ] [G8-A6-T1241] Testar: QTabWidget 4 abas.
- [ ] [G8-A6-T1242] Revisar: pyqtgraph barras.
- [ ] [G8-A6-T1243] Documentar: cores por empresa.
- [ ] [G8-A6-T1244] Otimizar: media tracejada.
- [ ] [G8-A6-T1245] Validar: headroom rotulos.
- [ ] [G8-A6-T1246] Medir: stagger colisao.
- [ ] [G8-A6-T1247] Automatizar: paginacao tabelas.
- [ ] [G8-A6-T1248] Implementar: temas QSS.
- [ ] [G8-A6-T1249] Testar: status bar.
- [ ] [G8-A6-T1250] Revisar: periodo reativo.

### G8-A7
- [ ] [G8-A7-T1251] Documentar: colapso total.
- [ ] [G8-A7-T1252] Otimizar: show_btn.
- [ ] [G8-A7-T1253] Validar: QSplitter 25/75.
- [ ] [G8-A7-T1254] Medir: handle estilizado.
- [ ] [G8-A7-T1255] Automatizar: QToolBox topo.
- [ ] [G8-A7-T1256] Implementar: empresas em grid.
- [ ] [G8-A7-T1257] Testar: periodo/moeda form.
- [ ] [G8-A7-T1258] Revisar: QTabWidget 4 abas.
- [ ] [G8-A7-T1259] Documentar: pyqtgraph barras.
- [ ] [G8-A7-T1260] Otimizar: cores por empresa.

### G8-A8
- [ ] [G8-A8-T1261] Validar: headroom rotulos.
- [ ] [G8-A8-T1262] Medir: stagger colisao.
- [ ] [G8-A8-T1263] Automatizar: paginacao tabelas.
- [ ] [G8-A8-T1264] Implementar: temas QSS.
- [ ] [G8-A8-T1265] Testar: status bar.
- [ ] [G8-A8-T1266] Revisar: periodo reativo.
- [ ] [G8-A8-T1267] Documentar: moeda reativa.
- [ ] [G8-A8-T1268] Otimizar: colapso total.
- [ ] [G8-A8-T1269] Validar: show_btn.
- [ ] [G8-A8-T1270] Medir: QSplitter 25/75.

### G8-A9
- [ ] [G8-A9-T1271] Automatizar: QToolBox topo.
- [ ] [G8-A9-T1272] Implementar: empresas em grid.
- [ ] [G8-A9-T1273] Testar: periodo/moeda form.
- [ ] [G8-A9-T1274] Revisar: QTabWidget 4 abas.
- [ ] [G8-A9-T1275] Documentar: pyqtgraph barras.
- [ ] [G8-A9-T1276] Otimizar: cores por empresa.
- [ ] [G8-A9-T1277] Validar: media tracejada.
- [ ] [G8-A9-T1278] Medir: headroom rotulos.
- [ ] [G8-A9-T1279] Automatizar: stagger colisao.
- [ ] [G8-A9-T1280] Implementar: paginacao tabelas.

### G8-A10
- [ ] [G8-A10-T1281] Testar: status bar.
- [ ] [G8-A10-T1282] Revisar: periodo reativo.
- [ ] [G8-A10-T1283] Documentar: moeda reativa.
- [ ] [G8-A10-T1284] Otimizar: colapso total.
- [ ] [G8-A10-T1285] Validar: show_btn.
- [ ] [G8-A10-T1286] Medir: QSplitter 25/75.
- [ ] [G8-A10-T1287] Automatizar: handle estilizado.
- [ ] [G8-A10-T1288] Implementar: QToolBox topo.
- [ ] [G8-A10-T1289] Testar: empresas em grid.
- [ ] [G8-A10-T1290] Revisar: periodo/moeda form.

### G8-A11
- [ ] [G8-A11-T1291] Documentar: pyqtgraph barras.
- [ ] [G8-A11-T1292] Otimizar: cores por empresa.
- [ ] [G8-A11-T1293] Validar: media tracejada.
- [ ] [G8-A11-T1294] Medir: headroom rotulos.
- [ ] [G8-A11-T1295] Automatizar: stagger colisao.
- [ ] [G8-A11-T1296] Implementar: paginacao tabelas.
- [ ] [G8-A11-T1297] Testar: temas QSS.
- [ ] [G8-A11-T1298] Revisar: status bar.
- [ ] [G8-A11-T1299] Documentar: periodo reativo.
- [ ] [G8-A11-T1300] Otimizar: moeda reativa.

### G8-A12
- [ ] [G8-A12-T1301] Validar: show_btn.
- [ ] [G8-A12-T1302] Medir: QSplitter 25/75.
- [ ] [G8-A12-T1303] Automatizar: handle estilizado.
- [ ] [G8-A12-T1304] Implementar: QToolBox topo.
- [ ] [G8-A12-T1305] Testar: empresas em grid.
- [ ] [G8-A12-T1306] Revisar: periodo/moeda form.
- [ ] [G8-A12-T1307] Documentar: QTabWidget 4 abas.
- [ ] [G8-A12-T1308] Otimizar: pyqtgraph barras.
- [ ] [G8-A12-T1309] Validar: cores por empresa.
- [ ] [G8-A12-T1310] Medir: media tracejada.

### G8-A13
- [ ] [G8-A13-T1311] Automatizar: stagger colisao.
- [ ] [G8-A13-T1312] Implementar: paginacao tabelas.
- [ ] [G8-A13-T1313] Testar: temas QSS.
- [ ] [G8-A13-T1314] Revisar: status bar.
- [ ] [G8-A13-T1315] Documentar: periodo reativo.
- [ ] [G8-A13-T1316] Otimizar: moeda reativa.
- [ ] [G8-A13-T1317] Validar: colapso total.
- [ ] [G8-A13-T1318] Medir: show_btn.
- [ ] [G8-A13-T1319] Automatizar: QSplitter 25/75.
- [ ] [G8-A13-T1320] Implementar: handle estilizado.

### G8-A14
- [ ] [G8-A14-T1321] Testar: empresas em grid.
- [ ] [G8-A14-T1322] Revisar: periodo/moeda form.
- [ ] [G8-A14-T1323] Documentar: QTabWidget 4 abas.
- [ ] [G8-A14-T1324] Otimizar: pyqtgraph barras.
- [ ] [G8-A14-T1325] Validar: cores por empresa.
- [ ] [G8-A14-T1326] Medir: media tracejada.
- [ ] [G8-A14-T1327] Automatizar: headroom rotulos.
- [ ] [G8-A14-T1328] Implementar: stagger colisao.
- [ ] [G8-A14-T1329] Testar: paginacao tabelas.
- [ ] [G8-A14-T1330] Revisar: temas QSS.

### G8-A15
- [ ] [G8-A15-T1331] Documentar: periodo reativo.
- [ ] [G8-A15-T1332] Otimizar: moeda reativa.
- [ ] [G8-A15-T1333] Validar: colapso total.
- [ ] [G8-A15-T1334] Medir: show_btn.
- [ ] [G8-A15-T1335] Automatizar: QSplitter 25/75.
- [ ] [G8-A15-T1336] Implementar: handle estilizado.
- [ ] [G8-A15-T1337] Testar: QToolBox topo.
- [ ] [G8-A15-T1338] Revisar: empresas em grid.
- [ ] [G8-A15-T1339] Documentar: periodo/moeda form.
- [ ] [G8-A15-T1340] Otimizar: QTabWidget 4 abas.

### G8-A16
- [ ] [G8-A16-T1341] Validar: cores por empresa.
- [ ] [G8-A16-T1342] Medir: media tracejada.
- [ ] [G8-A16-T1343] Automatizar: headroom rotulos.
- [ ] [G8-A16-T1344] Implementar: stagger colisao.
- [ ] [G8-A16-T1345] Testar: paginacao tabelas.
- [ ] [G8-A16-T1346] Revisar: temas QSS.
- [ ] [G8-A16-T1347] Documentar: status bar.
- [ ] [G8-A16-T1348] Otimizar: periodo reativo.
- [ ] [G8-A16-T1349] Validar: moeda reativa.
- [ ] [G8-A16-T1350] Medir: colapso total.

### G8-A17
- [ ] [G8-A17-T1351] Automatizar: QSplitter 25/75.
- [ ] [G8-A17-T1352] Implementar: handle estilizado.
- [ ] [G8-A17-T1353] Testar: QToolBox topo.
- [ ] [G8-A17-T1354] Revisar: empresas em grid.
- [ ] [G8-A17-T1355] Documentar: periodo/moeda form.
- [ ] [G8-A17-T1356] Otimizar: QTabWidget 4 abas.
- [ ] [G8-A17-T1357] Validar: pyqtgraph barras.
- [ ] [G8-A17-T1358] Medir: cores por empresa.
- [ ] [G8-A17-T1359] Automatizar: media tracejada.
- [ ] [G8-A17-T1360] Implementar: headroom rotulos.

## G9 — Controllers e CLI (170 tarefas)
_Modulos: `controllers/, app_main.py, main_vis.bat`_

### G9-A1
- [ ] [G9-A1-T1361] Testar: status/reset.
- [ ] [G9-A1-T1362] Revisar: bat 10 opcoes.
- [ ] [G9-A1-T1363] Documentar: RI prevalece.
- [ ] [G9-A1-T1364] Otimizar: gap-only SEC.
- [ ] [G9-A1-T1365] Validar: full chain.
- [ ] [G9-A1-T1366] Medir: trimestre end-to-end.
- [ ] [G9-A1-T1367] Automatizar: Pipeline/etl/auditoria.
- [ ] [G9-A1-T1368] Implementar: Analytics ranking/insight.
- [ ] [G9-A1-T1369] Testar: Source CRUD.
- [ ] [G9-A1-T1370] Revisar: full/etl/web/gui/sec.

### G9-A2
- [ ] [G9-A2-T1371] Documentar: coleta/pdf/email/trimestre.
- [ ] [G9-A2-T1372] Otimizar: status/reset.
- [ ] [G9-A2-T1373] Validar: bat 10 opcoes.
- [ ] [G9-A2-T1374] Medir: RI prevalece.
- [ ] [G9-A2-T1375] Automatizar: gap-only SEC.
- [ ] [G9-A2-T1376] Implementar: full chain.
- [ ] [G9-A2-T1377] Testar: trimestre end-to-end.
- [ ] [G9-A2-T1378] Revisar: Pipeline/etl/auditoria.
- [ ] [G9-A2-T1379] Documentar: Analytics ranking/insight.
- [ ] [G9-A2-T1380] Otimizar: Source CRUD.

### G9-A3
- [ ] [G9-A3-T1381] Validar: efetivo/derivados/powerbi.
- [ ] [G9-A3-T1382] Medir: coleta/pdf/email/trimestre.
- [ ] [G9-A3-T1383] Automatizar: status/reset.
- [ ] [G9-A3-T1384] Implementar: bat 10 opcoes.
- [ ] [G9-A3-T1385] Testar: RI prevalece.
- [ ] [G9-A3-T1386] Revisar: gap-only SEC.
- [ ] [G9-A3-T1387] Documentar: full chain.
- [ ] [G9-A3-T1388] Otimizar: trimestre end-to-end.
- [ ] [G9-A3-T1389] Validar: Pipeline/etl/auditoria.
- [ ] [G9-A3-T1390] Medir: Analytics ranking/insight.

### G9-A4
- [ ] [G9-A4-T1391] Automatizar: full/etl/web/gui/sec.
- [ ] [G9-A4-T1392] Implementar: efetivo/derivados/powerbi.
- [ ] [G9-A4-T1393] Testar: coleta/pdf/email/trimestre.
- [ ] [G9-A4-T1394] Revisar: status/reset.
- [ ] [G9-A4-T1395] Documentar: bat 10 opcoes.
- [ ] [G9-A4-T1396] Otimizar: RI prevalece.
- [ ] [G9-A4-T1397] Validar: gap-only SEC.
- [ ] [G9-A4-T1398] Medir: full chain.
- [ ] [G9-A4-T1399] Automatizar: trimestre end-to-end.
- [ ] [G9-A4-T1400] Implementar: Pipeline/etl/auditoria.

### G9-A5
- [ ] [G9-A5-T1401] Testar: Source CRUD.
- [ ] [G9-A5-T1402] Revisar: full/etl/web/gui/sec.
- [ ] [G9-A5-T1403] Documentar: efetivo/derivados/powerbi.
- [ ] [G9-A5-T1404] Otimizar: coleta/pdf/email/trimestre.
- [ ] [G9-A5-T1405] Validar: status/reset.
- [ ] [G9-A5-T1406] Medir: bat 10 opcoes.
- [ ] [G9-A5-T1407] Automatizar: RI prevalece.
- [ ] [G9-A5-T1408] Implementar: gap-only SEC.
- [ ] [G9-A5-T1409] Testar: full chain.
- [ ] [G9-A5-T1410] Revisar: trimestre end-to-end.

### G9-A6
- [ ] [G9-A6-T1411] Documentar: Analytics ranking/insight.
- [ ] [G9-A6-T1412] Otimizar: Source CRUD.
- [ ] [G9-A6-T1413] Validar: full/etl/web/gui/sec.
- [ ] [G9-A6-T1414] Medir: efetivo/derivados/powerbi.
- [ ] [G9-A6-T1415] Automatizar: coleta/pdf/email/trimestre.
- [ ] [G9-A6-T1416] Implementar: status/reset.
- [ ] [G9-A6-T1417] Testar: bat 10 opcoes.
- [ ] [G9-A6-T1418] Revisar: RI prevalece.
- [ ] [G9-A6-T1419] Documentar: gap-only SEC.
- [ ] [G9-A6-T1420] Otimizar: full chain.

### G9-A7
- [ ] [G9-A7-T1421] Validar: Pipeline/etl/auditoria.
- [ ] [G9-A7-T1422] Medir: Analytics ranking/insight.
- [ ] [G9-A7-T1423] Automatizar: Source CRUD.
- [ ] [G9-A7-T1424] Implementar: full/etl/web/gui/sec.
- [ ] [G9-A7-T1425] Testar: efetivo/derivados/powerbi.
- [ ] [G9-A7-T1426] Revisar: coleta/pdf/email/trimestre.
- [ ] [G9-A7-T1427] Documentar: status/reset.
- [ ] [G9-A7-T1428] Otimizar: bat 10 opcoes.
- [ ] [G9-A7-T1429] Validar: RI prevalece.
- [ ] [G9-A7-T1430] Medir: gap-only SEC.

### G9-A8
- [ ] [G9-A8-T1431] Automatizar: trimestre end-to-end.
- [ ] [G9-A8-T1432] Implementar: Pipeline/etl/auditoria.
- [ ] [G9-A8-T1433] Testar: Analytics ranking/insight.
- [ ] [G9-A8-T1434] Revisar: Source CRUD.
- [ ] [G9-A8-T1435] Documentar: full/etl/web/gui/sec.
- [ ] [G9-A8-T1436] Otimizar: efetivo/derivados/powerbi.
- [ ] [G9-A8-T1437] Validar: coleta/pdf/email/trimestre.
- [ ] [G9-A8-T1438] Medir: status/reset.
- [ ] [G9-A8-T1439] Automatizar: bat 10 opcoes.
- [ ] [G9-A8-T1440] Implementar: RI prevalece.

### G9-A9
- [ ] [G9-A9-T1441] Testar: full chain.
- [ ] [G9-A9-T1442] Revisar: trimestre end-to-end.
- [ ] [G9-A9-T1443] Documentar: Pipeline/etl/auditoria.
- [ ] [G9-A9-T1444] Otimizar: Analytics ranking/insight.
- [ ] [G9-A9-T1445] Validar: Source CRUD.
- [ ] [G9-A9-T1446] Medir: full/etl/web/gui/sec.
- [ ] [G9-A9-T1447] Automatizar: efetivo/derivados/powerbi.
- [ ] [G9-A9-T1448] Implementar: coleta/pdf/email/trimestre.
- [ ] [G9-A9-T1449] Testar: status/reset.
- [ ] [G9-A9-T1450] Revisar: bat 10 opcoes.

### G9-A10
- [ ] [G9-A10-T1451] Documentar: gap-only SEC.
- [ ] [G9-A10-T1452] Otimizar: full chain.
- [ ] [G9-A10-T1453] Validar: trimestre end-to-end.
- [ ] [G9-A10-T1454] Medir: Pipeline/etl/auditoria.
- [ ] [G9-A10-T1455] Automatizar: Analytics ranking/insight.
- [ ] [G9-A10-T1456] Implementar: Source CRUD.
- [ ] [G9-A10-T1457] Testar: full/etl/web/gui/sec.
- [ ] [G9-A10-T1458] Revisar: efetivo/derivados/powerbi.
- [ ] [G9-A10-T1459] Documentar: coleta/pdf/email/trimestre.
- [ ] [G9-A10-T1460] Otimizar: status/reset.

### G9-A11
- [ ] [G9-A11-T1461] Validar: RI prevalece.
- [ ] [G9-A11-T1462] Medir: gap-only SEC.
- [ ] [G9-A11-T1463] Automatizar: full chain.
- [ ] [G9-A11-T1464] Implementar: trimestre end-to-end.
- [ ] [G9-A11-T1465] Testar: Pipeline/etl/auditoria.
- [ ] [G9-A11-T1466] Revisar: Analytics ranking/insight.
- [ ] [G9-A11-T1467] Documentar: Source CRUD.
- [ ] [G9-A11-T1468] Otimizar: full/etl/web/gui/sec.
- [ ] [G9-A11-T1469] Validar: efetivo/derivados/powerbi.
- [ ] [G9-A11-T1470] Medir: coleta/pdf/email/trimestre.

### G9-A12
- [ ] [G9-A12-T1471] Automatizar: bat 10 opcoes.
- [ ] [G9-A12-T1472] Implementar: RI prevalece.
- [ ] [G9-A12-T1473] Testar: gap-only SEC.
- [ ] [G9-A12-T1474] Revisar: full chain.
- [ ] [G9-A12-T1475] Documentar: trimestre end-to-end.
- [ ] [G9-A12-T1476] Otimizar: Pipeline/etl/auditoria.
- [ ] [G9-A12-T1477] Validar: Analytics ranking/insight.
- [ ] [G9-A12-T1478] Medir: Source CRUD.
- [ ] [G9-A12-T1479] Automatizar: full/etl/web/gui/sec.
- [ ] [G9-A12-T1480] Implementar: efetivo/derivados/powerbi.

### G9-A13
- [ ] [G9-A13-T1481] Testar: status/reset.
- [ ] [G9-A13-T1482] Revisar: bat 10 opcoes.
- [ ] [G9-A13-T1483] Documentar: RI prevalece.
- [ ] [G9-A13-T1484] Otimizar: gap-only SEC.
- [ ] [G9-A13-T1485] Validar: full chain.
- [ ] [G9-A13-T1486] Medir: trimestre end-to-end.
- [ ] [G9-A13-T1487] Automatizar: Pipeline/etl/auditoria.
- [ ] [G9-A13-T1488] Implementar: Analytics ranking/insight.
- [ ] [G9-A13-T1489] Testar: Source CRUD.
- [ ] [G9-A13-T1490] Revisar: full/etl/web/gui/sec.

### G9-A14
- [ ] [G9-A14-T1491] Documentar: coleta/pdf/email/trimestre.
- [ ] [G9-A14-T1492] Otimizar: status/reset.
- [ ] [G9-A14-T1493] Validar: bat 10 opcoes.
- [ ] [G9-A14-T1494] Medir: RI prevalece.
- [ ] [G9-A14-T1495] Automatizar: gap-only SEC.
- [ ] [G9-A14-T1496] Implementar: full chain.
- [ ] [G9-A14-T1497] Testar: trimestre end-to-end.
- [ ] [G9-A14-T1498] Revisar: Pipeline/etl/auditoria.
- [ ] [G9-A14-T1499] Documentar: Analytics ranking/insight.
- [ ] [G9-A14-T1500] Otimizar: Source CRUD.

### G9-A15
- [ ] [G9-A15-T1501] Validar: efetivo/derivados/powerbi.
- [ ] [G9-A15-T1502] Medir: coleta/pdf/email/trimestre.
- [ ] [G9-A15-T1503] Automatizar: status/reset.
- [ ] [G9-A15-T1504] Implementar: bat 10 opcoes.
- [ ] [G9-A15-T1505] Testar: RI prevalece.
- [ ] [G9-A15-T1506] Revisar: gap-only SEC.
- [ ] [G9-A15-T1507] Documentar: full chain.
- [ ] [G9-A15-T1508] Otimizar: trimestre end-to-end.
- [ ] [G9-A15-T1509] Validar: Pipeline/etl/auditoria.
- [ ] [G9-A15-T1510] Medir: Analytics ranking/insight.

### G9-A16
- [ ] [G9-A16-T1511] Automatizar: full/etl/web/gui/sec.
- [ ] [G9-A16-T1512] Implementar: efetivo/derivados/powerbi.
- [ ] [G9-A16-T1513] Testar: coleta/pdf/email/trimestre.
- [ ] [G9-A16-T1514] Revisar: status/reset.
- [ ] [G9-A16-T1515] Documentar: bat 10 opcoes.
- [ ] [G9-A16-T1516] Otimizar: RI prevalece.
- [ ] [G9-A16-T1517] Validar: gap-only SEC.
- [ ] [G9-A16-T1518] Medir: full chain.
- [ ] [G9-A16-T1519] Automatizar: trimestre end-to-end.
- [ ] [G9-A16-T1520] Implementar: Pipeline/etl/auditoria.

### G9-A17
- [ ] [G9-A17-T1521] Testar: Source CRUD.
- [ ] [G9-A17-T1522] Revisar: full/etl/web/gui/sec.
- [ ] [G9-A17-T1523] Documentar: efetivo/derivados/powerbi.
- [ ] [G9-A17-T1524] Otimizar: coleta/pdf/email/trimestre.
- [ ] [G9-A17-T1525] Validar: status/reset.
- [ ] [G9-A17-T1526] Medir: bat 10 opcoes.
- [ ] [G9-A17-T1527] Automatizar: RI prevalece.
- [ ] [G9-A17-T1528] Implementar: gap-only SEC.
- [ ] [G9-A17-T1529] Testar: full chain.
- [ ] [G9-A17-T1530] Revisar: trimestre end-to-end.

## G10 — Docs e entrega (170 tarefas)
_Modulos: `docs/`_

### G10-A1
- [ ] [G10-A1-T1531] Documentar: SLIDES md+pdf.
- [ ] [G10-A1-T1532] Otimizar: CATALOGO.
- [ ] [G10-A1-T1533] Validar: EVIDENCIAS.
- [ ] [G10-A1-T1534] Medir: INSTRUCOES.
- [ ] [G10-A1-T1535] Automatizar: DAX.
- [ ] [G10-A1-T1536] Implementar: PLANO 520/2000.
- [ ] [G10-A1-T1537] Testar: LEIAME powerbi.
- [ ] [G10-A1-T1538] Revisar: limitacoes honestas.
- [ ] [G10-A1-T1539] Documentar: ARQUITETURA.
- [ ] [G10-A1-T1540] Otimizar: PREMISSAS téc/fin.

### G10-A2
- [ ] [G10-A2-T1541] Validar: SLIDES md+pdf.
- [ ] [G10-A2-T1542] Medir: CATALOGO.
- [ ] [G10-A2-T1543] Automatizar: EVIDENCIAS.
- [ ] [G10-A2-T1544] Implementar: INSTRUCOES.
- [ ] [G10-A2-T1545] Testar: DAX.
- [ ] [G10-A2-T1546] Revisar: PLANO 520/2000.
- [ ] [G10-A2-T1547] Documentar: LEIAME powerbi.
- [ ] [G10-A2-T1548] Otimizar: limitacoes honestas.
- [ ] [G10-A2-T1549] Validar: ARQUITETURA.
- [ ] [G10-A2-T1550] Medir: PREMISSAS téc/fin.

### G10-A3
- [ ] [G10-A3-T1551] Automatizar: SLIDES md+pdf.
- [ ] [G10-A3-T1552] Implementar: CATALOGO.
- [ ] [G10-A3-T1553] Testar: EVIDENCIAS.
- [ ] [G10-A3-T1554] Revisar: INSTRUCOES.
- [ ] [G10-A3-T1555] Documentar: DAX.
- [ ] [G10-A3-T1556] Otimizar: PLANO 520/2000.
- [ ] [G10-A3-T1557] Validar: LEIAME powerbi.
- [ ] [G10-A3-T1558] Medir: limitacoes honestas.
- [ ] [G10-A3-T1559] Automatizar: ARQUITETURA.
- [ ] [G10-A3-T1560] Implementar: PREMISSAS téc/fin.

### G10-A4
- [ ] [G10-A4-T1561] Testar: SLIDES md+pdf.
- [ ] [G10-A4-T1562] Revisar: CATALOGO.
- [ ] [G10-A4-T1563] Documentar: EVIDENCIAS.
- [ ] [G10-A4-T1564] Otimizar: INSTRUCOES.
- [ ] [G10-A4-T1565] Validar: DAX.
- [ ] [G10-A4-T1566] Medir: PLANO 520/2000.
- [ ] [G10-A4-T1567] Automatizar: LEIAME powerbi.
- [ ] [G10-A4-T1568] Implementar: limitacoes honestas.
- [ ] [G10-A4-T1569] Testar: ARQUITETURA.
- [ ] [G10-A4-T1570] Revisar: PREMISSAS téc/fin.

### G10-A5
- [ ] [G10-A5-T1571] Documentar: SLIDES md+pdf.
- [ ] [G10-A5-T1572] Otimizar: CATALOGO.
- [ ] [G10-A5-T1573] Validar: EVIDENCIAS.
- [ ] [G10-A5-T1574] Medir: INSTRUCOES.
- [ ] [G10-A5-T1575] Automatizar: DAX.
- [ ] [G10-A5-T1576] Implementar: PLANO 520/2000.
- [ ] [G10-A5-T1577] Testar: LEIAME powerbi.
- [ ] [G10-A5-T1578] Revisar: limitacoes honestas.
- [ ] [G10-A5-T1579] Documentar: ARQUITETURA.
- [ ] [G10-A5-T1580] Otimizar: PREMISSAS téc/fin.

### G10-A6
- [ ] [G10-A6-T1581] Validar: SLIDES md+pdf.
- [ ] [G10-A6-T1582] Medir: CATALOGO.
- [ ] [G10-A6-T1583] Automatizar: EVIDENCIAS.
- [ ] [G10-A6-T1584] Implementar: INSTRUCOES.
- [ ] [G10-A6-T1585] Testar: DAX.
- [ ] [G10-A6-T1586] Revisar: PLANO 520/2000.
- [ ] [G10-A6-T1587] Documentar: LEIAME powerbi.
- [ ] [G10-A6-T1588] Otimizar: limitacoes honestas.
- [ ] [G10-A6-T1589] Validar: ARQUITETURA.
- [ ] [G10-A6-T1590] Medir: PREMISSAS téc/fin.

### G10-A7
- [ ] [G10-A7-T1591] Automatizar: SLIDES md+pdf.
- [ ] [G10-A7-T1592] Implementar: CATALOGO.
- [ ] [G10-A7-T1593] Testar: EVIDENCIAS.
- [ ] [G10-A7-T1594] Revisar: INSTRUCOES.
- [ ] [G10-A7-T1595] Documentar: DAX.
- [ ] [G10-A7-T1596] Otimizar: PLANO 520/2000.
- [ ] [G10-A7-T1597] Validar: LEIAME powerbi.
- [ ] [G10-A7-T1598] Medir: limitacoes honestas.
- [ ] [G10-A7-T1599] Automatizar: ARQUITETURA.
- [ ] [G10-A7-T1600] Implementar: PREMISSAS téc/fin.

### G10-A8
- [ ] [G10-A8-T1601] Testar: SLIDES md+pdf.
- [ ] [G10-A8-T1602] Revisar: CATALOGO.
- [ ] [G10-A8-T1603] Documentar: EVIDENCIAS.
- [ ] [G10-A8-T1604] Otimizar: INSTRUCOES.
- [ ] [G10-A8-T1605] Validar: DAX.
- [ ] [G10-A8-T1606] Medir: PLANO 520/2000.
- [ ] [G10-A8-T1607] Automatizar: LEIAME powerbi.
- [ ] [G10-A8-T1608] Implementar: limitacoes honestas.
- [ ] [G10-A8-T1609] Testar: ARQUITETURA.
- [ ] [G10-A8-T1610] Revisar: PREMISSAS téc/fin.

### G10-A9
- [ ] [G10-A9-T1611] Documentar: SLIDES md+pdf.
- [ ] [G10-A9-T1612] Otimizar: CATALOGO.
- [ ] [G10-A9-T1613] Validar: EVIDENCIAS.
- [ ] [G10-A9-T1614] Medir: INSTRUCOES.
- [ ] [G10-A9-T1615] Automatizar: DAX.
- [ ] [G10-A9-T1616] Implementar: PLANO 520/2000.
- [ ] [G10-A9-T1617] Testar: LEIAME powerbi.
- [ ] [G10-A9-T1618] Revisar: limitacoes honestas.
- [ ] [G10-A9-T1619] Documentar: ARQUITETURA.
- [ ] [G10-A9-T1620] Otimizar: PREMISSAS téc/fin.

### G10-A10
- [ ] [G10-A10-T1621] Validar: SLIDES md+pdf.
- [ ] [G10-A10-T1622] Medir: CATALOGO.
- [ ] [G10-A10-T1623] Automatizar: EVIDENCIAS.
- [ ] [G10-A10-T1624] Implementar: INSTRUCOES.
- [ ] [G10-A10-T1625] Testar: DAX.
- [ ] [G10-A10-T1626] Revisar: PLANO 520/2000.
- [ ] [G10-A10-T1627] Documentar: LEIAME powerbi.
- [ ] [G10-A10-T1628] Otimizar: limitacoes honestas.
- [ ] [G10-A10-T1629] Validar: ARQUITETURA.
- [ ] [G10-A10-T1630] Medir: PREMISSAS téc/fin.

### G10-A11
- [ ] [G10-A11-T1631] Automatizar: SLIDES md+pdf.
- [ ] [G10-A11-T1632] Implementar: CATALOGO.
- [ ] [G10-A11-T1633] Testar: EVIDENCIAS.
- [ ] [G10-A11-T1634] Revisar: INSTRUCOES.
- [ ] [G10-A11-T1635] Documentar: DAX.
- [ ] [G10-A11-T1636] Otimizar: PLANO 520/2000.
- [ ] [G10-A11-T1637] Validar: LEIAME powerbi.
- [ ] [G10-A11-T1638] Medir: limitacoes honestas.
- [ ] [G10-A11-T1639] Automatizar: ARQUITETURA.
- [ ] [G10-A11-T1640] Implementar: PREMISSAS téc/fin.

### G10-A12
- [ ] [G10-A12-T1641] Testar: SLIDES md+pdf.
- [ ] [G10-A12-T1642] Revisar: CATALOGO.
- [ ] [G10-A12-T1643] Documentar: EVIDENCIAS.
- [ ] [G10-A12-T1644] Otimizar: INSTRUCOES.
- [ ] [G10-A12-T1645] Validar: DAX.
- [ ] [G10-A12-T1646] Medir: PLANO 520/2000.
- [ ] [G10-A12-T1647] Automatizar: LEIAME powerbi.
- [ ] [G10-A12-T1648] Implementar: limitacoes honestas.
- [ ] [G10-A12-T1649] Testar: ARQUITETURA.
- [ ] [G10-A12-T1650] Revisar: PREMISSAS téc/fin.

### G10-A13
- [ ] [G10-A13-T1651] Documentar: SLIDES md+pdf.
- [ ] [G10-A13-T1652] Otimizar: CATALOGO.
- [ ] [G10-A13-T1653] Validar: EVIDENCIAS.
- [ ] [G10-A13-T1654] Medir: INSTRUCOES.
- [ ] [G10-A13-T1655] Automatizar: DAX.
- [ ] [G10-A13-T1656] Implementar: PLANO 520/2000.
- [ ] [G10-A13-T1657] Testar: LEIAME powerbi.
- [ ] [G10-A13-T1658] Revisar: limitacoes honestas.
- [ ] [G10-A13-T1659] Documentar: ARQUITETURA.
- [ ] [G10-A13-T1660] Otimizar: PREMISSAS téc/fin.

### G10-A14
- [ ] [G10-A14-T1661] Validar: SLIDES md+pdf.
- [ ] [G10-A14-T1662] Medir: CATALOGO.
- [ ] [G10-A14-T1663] Automatizar: EVIDENCIAS.
- [ ] [G10-A14-T1664] Implementar: INSTRUCOES.
- [ ] [G10-A14-T1665] Testar: DAX.
- [ ] [G10-A14-T1666] Revisar: PLANO 520/2000.
- [ ] [G10-A14-T1667] Documentar: LEIAME powerbi.
- [ ] [G10-A14-T1668] Otimizar: limitacoes honestas.
- [ ] [G10-A14-T1669] Validar: ARQUITETURA.
- [ ] [G10-A14-T1670] Medir: PREMISSAS téc/fin.

### G10-A15
- [ ] [G10-A15-T1671] Automatizar: SLIDES md+pdf.
- [ ] [G10-A15-T1672] Implementar: CATALOGO.
- [ ] [G10-A15-T1673] Testar: EVIDENCIAS.
- [ ] [G10-A15-T1674] Revisar: INSTRUCOES.
- [ ] [G10-A15-T1675] Documentar: DAX.
- [ ] [G10-A15-T1676] Otimizar: PLANO 520/2000.
- [ ] [G10-A15-T1677] Validar: LEIAME powerbi.
- [ ] [G10-A15-T1678] Medir: limitacoes honestas.
- [ ] [G10-A15-T1679] Automatizar: ARQUITETURA.
- [ ] [G10-A15-T1680] Implementar: PREMISSAS téc/fin.

### G10-A16
- [ ] [G10-A16-T1681] Testar: SLIDES md+pdf.
- [ ] [G10-A16-T1682] Revisar: CATALOGO.
- [ ] [G10-A16-T1683] Documentar: EVIDENCIAS.
- [ ] [G10-A16-T1684] Otimizar: INSTRUCOES.
- [ ] [G10-A16-T1685] Validar: DAX.
- [ ] [G10-A16-T1686] Medir: PLANO 520/2000.
- [ ] [G10-A16-T1687] Automatizar: LEIAME powerbi.
- [ ] [G10-A16-T1688] Implementar: limitacoes honestas.
- [ ] [G10-A16-T1689] Testar: ARQUITETURA.
- [ ] [G10-A16-T1690] Revisar: PREMISSAS téc/fin.

### G10-A17
- [ ] [G10-A17-T1691] Documentar: SLIDES md+pdf.
- [ ] [G10-A17-T1692] Otimizar: CATALOGO.
- [ ] [G10-A17-T1693] Validar: EVIDENCIAS.
- [ ] [G10-A17-T1694] Medir: INSTRUCOES.
- [ ] [G10-A17-T1695] Automatizar: DAX.
- [ ] [G10-A17-T1696] Implementar: PLANO 520/2000.
- [ ] [G10-A17-T1697] Testar: LEIAME powerbi.
- [ ] [G10-A17-T1698] Revisar: limitacoes honestas.
- [ ] [G10-A17-T1699] Documentar: ARQUITETURA.
- [ ] [G10-A17-T1700] Otimizar: PREMISSAS téc/fin.

## G11 — Testes (170 tarefas)
_Modulos: `tests/test_poc.py`_

### G11-A1
- [ ] [G11-A1-T1701] Validar: doc-year.
- [ ] [G11-A1-T1702] Medir: frase3.
- [ ] [G11-A1-T1703] Automatizar: EPS GAAP.
- [ ] [G11-A1-T1704] Implementar: moeda.
- [ ] [G11-A1-T1705] Testar: grid.
- [ ] [G11-A1-T1706] Revisar: coleta offline.
- [ ] [G11-A1-T1707] Documentar: FAQ I10.
- [ ] [G11-A1-T1708] Otimizar: CIK.
- [ ] [G11-A1-T1709] Validar: robustez.
- [ ] [G11-A1-T1710] Medir: derivados.

### G11-A2
- [ ] [G11-A2-T1711] Automatizar: series linha.
- [ ] [G11-A2-T1712] Implementar: grid height.
- [ ] [G11-A2-T1713] Testar: harness Node.
- [ ] [G11-A2-T1714] Revisar: schema.
- [ ] [G11-A2-T1715] Documentar: depara.
- [ ] [G11-A2-T1716] Otimizar: hash.
- [ ] [G11-A2-T1717] Validar: parse_tab real.
- [ ] [G11-A2-T1718] Medir: quality.
- [ ] [G11-A2-T1719] Automatizar: web html.
- [ ] [G11-A2-T1720] Implementar: sec frame/FY.

### G11-A3
- [ ] [G11-A3-T1721] Testar: gui abas.
- [ ] [G11-A3-T1722] Revisar: trailing-year.
- [ ] [G11-A3-T1723] Documentar: sentence2.
- [ ] [G11-A3-T1724] Otimizar: multibloco.
- [ ] [G11-A3-T1725] Validar: doc-year.
- [ ] [G11-A3-T1726] Medir: frase3.
- [ ] [G11-A3-T1727] Automatizar: EPS GAAP.
- [ ] [G11-A3-T1728] Implementar: moeda.
- [ ] [G11-A3-T1729] Testar: grid.
- [ ] [G11-A3-T1730] Revisar: coleta offline.

### G11-A4
- [ ] [G11-A4-T1731] Documentar: CIK.
- [ ] [G11-A4-T1732] Otimizar: robustez.
- [ ] [G11-A4-T1733] Validar: derivados.
- [ ] [G11-A4-T1734] Medir: trimestre.
- [ ] [G11-A4-T1735] Automatizar: series linha.
- [ ] [G11-A4-T1736] Implementar: grid height.
- [ ] [G11-A4-T1737] Testar: harness Node.
- [ ] [G11-A4-T1738] Revisar: schema.
- [ ] [G11-A4-T1739] Documentar: depara.
- [ ] [G11-A4-T1740] Otimizar: hash.

### G11-A5
- [ ] [G11-A5-T1741] Validar: quality.
- [ ] [G11-A5-T1742] Medir: web html.
- [ ] [G11-A5-T1743] Automatizar: sec frame/FY.
- [ ] [G11-A5-T1744] Implementar: efetivo anchors.
- [ ] [G11-A5-T1745] Testar: gui abas.
- [ ] [G11-A5-T1746] Revisar: trailing-year.
- [ ] [G11-A5-T1747] Documentar: sentence2.
- [ ] [G11-A5-T1748] Otimizar: multibloco.
- [ ] [G11-A5-T1749] Validar: doc-year.
- [ ] [G11-A5-T1750] Medir: frase3.

### G11-A6
- [ ] [G11-A6-T1751] Automatizar: moeda.
- [ ] [G11-A6-T1752] Implementar: grid.
- [ ] [G11-A6-T1753] Testar: coleta offline.
- [ ] [G11-A6-T1754] Revisar: FAQ I10.
- [ ] [G11-A6-T1755] Documentar: CIK.
- [ ] [G11-A6-T1756] Otimizar: robustez.
- [ ] [G11-A6-T1757] Validar: derivados.
- [ ] [G11-A6-T1758] Medir: trimestre.
- [ ] [G11-A6-T1759] Automatizar: series linha.
- [ ] [G11-A6-T1760] Implementar: grid height.

### G11-A7
- [ ] [G11-A7-T1761] Testar: schema.
- [ ] [G11-A7-T1762] Revisar: depara.
- [ ] [G11-A7-T1763] Documentar: hash.
- [ ] [G11-A7-T1764] Otimizar: parse_tab real.
- [ ] [G11-A7-T1765] Validar: quality.
- [ ] [G11-A7-T1766] Medir: web html.
- [ ] [G11-A7-T1767] Automatizar: sec frame/FY.
- [ ] [G11-A7-T1768] Implementar: efetivo anchors.
- [ ] [G11-A7-T1769] Testar: gui abas.
- [ ] [G11-A7-T1770] Revisar: trailing-year.

### G11-A8
- [ ] [G11-A8-T1771] Documentar: multibloco.
- [ ] [G11-A8-T1772] Otimizar: doc-year.
- [ ] [G11-A8-T1773] Validar: frase3.
- [ ] [G11-A8-T1774] Medir: EPS GAAP.
- [ ] [G11-A8-T1775] Automatizar: moeda.
- [ ] [G11-A8-T1776] Implementar: grid.
- [ ] [G11-A8-T1777] Testar: coleta offline.
- [ ] [G11-A8-T1778] Revisar: FAQ I10.
- [ ] [G11-A8-T1779] Documentar: CIK.
- [ ] [G11-A8-T1780] Otimizar: robustez.

### G11-A9
- [ ] [G11-A9-T1781] Validar: trimestre.
- [ ] [G11-A9-T1782] Medir: series linha.
- [ ] [G11-A9-T1783] Automatizar: grid height.
- [ ] [G11-A9-T1784] Implementar: harness Node.
- [ ] [G11-A9-T1785] Testar: schema.
- [ ] [G11-A9-T1786] Revisar: depara.
- [ ] [G11-A9-T1787] Documentar: hash.
- [ ] [G11-A9-T1788] Otimizar: parse_tab real.
- [ ] [G11-A9-T1789] Validar: quality.
- [ ] [G11-A9-T1790] Medir: web html.

### G11-A10
- [ ] [G11-A10-T1791] Automatizar: efetivo anchors.
- [ ] [G11-A10-T1792] Implementar: gui abas.
- [ ] [G11-A10-T1793] Testar: trailing-year.
- [ ] [G11-A10-T1794] Revisar: sentence2.
- [ ] [G11-A10-T1795] Documentar: multibloco.
- [ ] [G11-A10-T1796] Otimizar: doc-year.
- [ ] [G11-A10-T1797] Validar: frase3.
- [ ] [G11-A10-T1798] Medir: EPS GAAP.
- [ ] [G11-A10-T1799] Automatizar: moeda.
- [ ] [G11-A10-T1800] Implementar: grid.

### G11-A11
- [ ] [G11-A11-T1801] Testar: FAQ I10.
- [ ] [G11-A11-T1802] Revisar: CIK.
- [ ] [G11-A11-T1803] Documentar: robustez.
- [ ] [G11-A11-T1804] Otimizar: derivados.
- [ ] [G11-A11-T1805] Validar: trimestre.
- [ ] [G11-A11-T1806] Medir: series linha.
- [ ] [G11-A11-T1807] Automatizar: grid height.
- [ ] [G11-A11-T1808] Implementar: harness Node.
- [ ] [G11-A11-T1809] Testar: schema.
- [ ] [G11-A11-T1810] Revisar: depara.

### G11-A12
- [ ] [G11-A12-T1811] Documentar: parse_tab real.
- [ ] [G11-A12-T1812] Otimizar: quality.
- [ ] [G11-A12-T1813] Validar: web html.
- [ ] [G11-A12-T1814] Medir: sec frame/FY.
- [ ] [G11-A12-T1815] Automatizar: efetivo anchors.
- [ ] [G11-A12-T1816] Implementar: gui abas.
- [ ] [G11-A12-T1817] Testar: trailing-year.
- [ ] [G11-A12-T1818] Revisar: sentence2.
- [ ] [G11-A12-T1819] Documentar: multibloco.
- [ ] [G11-A12-T1820] Otimizar: doc-year.

### G11-A13
- [ ] [G11-A13-T1821] Validar: EPS GAAP.
- [ ] [G11-A13-T1822] Medir: moeda.
- [ ] [G11-A13-T1823] Automatizar: grid.
- [ ] [G11-A13-T1824] Implementar: coleta offline.
- [ ] [G11-A13-T1825] Testar: FAQ I10.
- [ ] [G11-A13-T1826] Revisar: CIK.
- [ ] [G11-A13-T1827] Documentar: robustez.
- [ ] [G11-A13-T1828] Otimizar: derivados.
- [ ] [G11-A13-T1829] Validar: trimestre.
- [ ] [G11-A13-T1830] Medir: series linha.

### G11-A14
- [ ] [G11-A14-T1831] Automatizar: harness Node.
- [ ] [G11-A14-T1832] Implementar: schema.
- [ ] [G11-A14-T1833] Testar: depara.
- [ ] [G11-A14-T1834] Revisar: hash.
- [ ] [G11-A14-T1835] Documentar: parse_tab real.
- [ ] [G11-A14-T1836] Otimizar: quality.
- [ ] [G11-A14-T1837] Validar: web html.
- [ ] [G11-A14-T1838] Medir: sec frame/FY.
- [ ] [G11-A14-T1839] Automatizar: efetivo anchors.
- [ ] [G11-A14-T1840] Implementar: gui abas.

### G11-A15
- [ ] [G11-A15-T1841] Testar: sentence2.
- [ ] [G11-A15-T1842] Revisar: multibloco.
- [ ] [G11-A15-T1843] Documentar: doc-year.
- [ ] [G11-A15-T1844] Otimizar: frase3.
- [ ] [G11-A15-T1845] Validar: EPS GAAP.
- [ ] [G11-A15-T1846] Medir: moeda.
- [ ] [G11-A15-T1847] Automatizar: grid.
- [ ] [G11-A15-T1848] Implementar: coleta offline.
- [ ] [G11-A15-T1849] Testar: FAQ I10.
- [ ] [G11-A15-T1850] Revisar: CIK.

### G11-A16
- [ ] [G11-A16-T1851] Documentar: derivados.
- [ ] [G11-A16-T1852] Otimizar: trimestre.
- [ ] [G11-A16-T1853] Validar: series linha.
- [ ] [G11-A16-T1854] Medir: grid height.
- [ ] [G11-A16-T1855] Automatizar: harness Node.
- [ ] [G11-A16-T1856] Implementar: schema.
- [ ] [G11-A16-T1857] Testar: depara.
- [ ] [G11-A16-T1858] Revisar: hash.
- [ ] [G11-A16-T1859] Documentar: parse_tab real.
- [ ] [G11-A16-T1860] Otimizar: quality.

### G11-A17
- [ ] [G11-A17-T1861] Validar: sec frame/FY.
- [ ] [G11-A17-T1862] Medir: efetivo anchors.
- [ ] [G11-A17-T1863] Automatizar: gui abas.
- [ ] [G11-A17-T1864] Implementar: trailing-year.
- [ ] [G11-A17-T1865] Testar: sentence2.
- [ ] [G11-A17-T1866] Revisar: multibloco.
- [ ] [G11-A17-T1867] Documentar: doc-year.
- [ ] [G11-A17-T1868] Otimizar: frase3.
- [ ] [G11-A17-T1869] Validar: EPS GAAP.
- [ ] [G11-A17-T1870] Medir: moeda.

## G12 — Operacao e escala (170 tarefas)
_Modulos: `config.py + todos`_

### G12-A1
- [ ] [G12-A1-T1871] Automatizar: schedulers (nao).
- [ ] [G12-A1-T1872] Implementar: custo operacional.
- [ ] [G12-A1-T1873] Testar: repetibilidade.
- [ ] [G12-A1-T1874] Revisar: backup .db.
- [ ] [G12-A1-T1875] Documentar: novo trimestre.
- [ ] [G12-A1-T1876] Otimizar: nova empresa (+CIK).
- [ ] [G12-A1-T1877] Validar: novo indicador (+regra).
- [ ] [G12-A1-T1878] Medir: nova moeda.
- [ ] [G12-A1-T1879] Automatizar: 4 anos 2023-2026.
- [ ] [G12-A1-T1880] Implementar: Docker roadmap.

### G12-A2
- [ ] [G12-A2-T1881] Testar: produtividade roadmap.
- [ ] [G12-A2-T1882] Revisar: DLQ roadmap.
- [ ] [G12-A2-T1883] Documentar: 304 roadmap.
- [ ] [G12-A2-T1884] Otimizar: schedulers (nao).
- [ ] [G12-A2-T1885] Validar: custo operacional.
- [ ] [G12-A2-T1886] Medir: repetibilidade.
- [ ] [G12-A2-T1887] Automatizar: backup .db.
- [ ] [G12-A2-T1888] Implementar: novo trimestre.
- [ ] [G12-A2-T1889] Testar: nova empresa (+CIK).
- [ ] [G12-A2-T1890] Revisar: novo indicador (+regra).

### G12-A3
- [ ] [G12-A3-T1891] Documentar: 4 anos 2023-2026.
- [ ] [G12-A3-T1892] Otimizar: Docker roadmap.
- [ ] [G12-A3-T1893] Validar: OCR roadmap.
- [ ] [G12-A3-T1894] Medir: produtividade roadmap.
- [ ] [G12-A3-T1895] Automatizar: DLQ roadmap.
- [ ] [G12-A3-T1896] Implementar: 304 roadmap.
- [ ] [G12-A3-T1897] Testar: schedulers (nao).
- [ ] [G12-A3-T1898] Revisar: custo operacional.
- [ ] [G12-A3-T1899] Documentar: repetibilidade.
- [ ] [G12-A3-T1900] Otimizar: backup .db.

### G12-A4
- [ ] [G12-A4-T1901] Validar: nova empresa (+CIK).
- [ ] [G12-A4-T1902] Medir: novo indicador (+regra).
- [ ] [G12-A4-T1903] Automatizar: nova moeda.
- [ ] [G12-A4-T1904] Implementar: 4 anos 2023-2026.
- [ ] [G12-A4-T1905] Testar: Docker roadmap.
- [ ] [G12-A4-T1906] Revisar: OCR roadmap.
- [ ] [G12-A4-T1907] Documentar: produtividade roadmap.
- [ ] [G12-A4-T1908] Otimizar: DLQ roadmap.
- [ ] [G12-A4-T1909] Validar: 304 roadmap.
- [ ] [G12-A4-T1910] Medir: schedulers (nao).

### G12-A5
- [ ] [G12-A5-T1911] Automatizar: repetibilidade.
- [ ] [G12-A5-T1912] Implementar: backup .db.
- [ ] [G12-A5-T1913] Testar: novo trimestre.
- [ ] [G12-A5-T1914] Revisar: nova empresa (+CIK).
- [ ] [G12-A5-T1915] Documentar: novo indicador (+regra).
- [ ] [G12-A5-T1916] Otimizar: nova moeda.
- [ ] [G12-A5-T1917] Validar: 4 anos 2023-2026.
- [ ] [G12-A5-T1918] Medir: Docker roadmap.
- [ ] [G12-A5-T1919] Automatizar: OCR roadmap.
- [ ] [G12-A5-T1920] Implementar: produtividade roadmap.

### G12-A6
- [ ] [G12-A6-T1921] Testar: 304 roadmap.
- [ ] [G12-A6-T1922] Revisar: schedulers (nao).
- [ ] [G12-A6-T1923] Documentar: custo operacional.
- [ ] [G12-A6-T1924] Otimizar: repetibilidade.
- [ ] [G12-A6-T1925] Validar: backup .db.
- [ ] [G12-A6-T1926] Medir: novo trimestre.
- [ ] [G12-A6-T1927] Automatizar: nova empresa (+CIK).
- [ ] [G12-A6-T1928] Implementar: novo indicador (+regra).
- [ ] [G12-A6-T1929] Testar: nova moeda.
- [ ] [G12-A6-T1930] Revisar: 4 anos 2023-2026.

### G12-A7
- [ ] [G12-A7-T1931] Documentar: OCR roadmap.
- [ ] [G12-A7-T1932] Otimizar: produtividade roadmap.
- [ ] [G12-A7-T1933] Validar: DLQ roadmap.
- [ ] [G12-A7-T1934] Medir: 304 roadmap.
- [ ] [G12-A7-T1935] Automatizar: schedulers (nao).
- [ ] [G12-A7-T1936] Implementar: custo operacional.
- [ ] [G12-A7-T1937] Testar: repetibilidade.
- [ ] [G12-A7-T1938] Revisar: backup .db.
- [ ] [G12-A7-T1939] Documentar: novo trimestre.
- [ ] [G12-A7-T1940] Otimizar: nova empresa (+CIK).

### G12-A8
- [ ] [G12-A8-T1941] Validar: nova moeda.
- [ ] [G12-A8-T1942] Medir: 4 anos 2023-2026.
- [ ] [G12-A8-T1943] Automatizar: Docker roadmap.
- [ ] [G12-A8-T1944] Implementar: OCR roadmap.
- [ ] [G12-A8-T1945] Testar: produtividade roadmap.
- [ ] [G12-A8-T1946] Revisar: DLQ roadmap.
- [ ] [G12-A8-T1947] Documentar: 304 roadmap.
- [ ] [G12-A8-T1948] Otimizar: schedulers (nao).
- [ ] [G12-A8-T1949] Validar: custo operacional.
- [ ] [G12-A8-T1950] Medir: repetibilidade.

### G12-A9
- [ ] [G12-A9-T1951] Automatizar: novo trimestre.
- [ ] [G12-A9-T1952] Implementar: nova empresa (+CIK).
- [ ] [G12-A9-T1953] Testar: novo indicador (+regra).
- [ ] [G12-A9-T1954] Revisar: nova moeda.
- [ ] [G12-A9-T1955] Documentar: 4 anos 2023-2026.
- [ ] [G12-A9-T1956] Otimizar: Docker roadmap.
- [ ] [G12-A9-T1957] Validar: OCR roadmap.
- [ ] [G12-A9-T1958] Medir: produtividade roadmap.
- [ ] [G12-A9-T1959] Automatizar: DLQ roadmap.
- [ ] [G12-A9-T1960] Implementar: 304 roadmap.

### G12-A10
- [ ] [G12-A10-T1961] Testar: custo operacional.
- [ ] [G12-A10-T1962] Revisar: repetibilidade.
- [ ] [G12-A10-T1963] Documentar: backup .db.
- [ ] [G12-A10-T1964] Otimizar: novo trimestre.
- [ ] [G12-A10-T1965] Validar: nova empresa (+CIK).
- [ ] [G12-A10-T1966] Medir: novo indicador (+regra).
- [ ] [G12-A10-T1967] Automatizar: nova moeda.
- [ ] [G12-A10-T1968] Implementar: 4 anos 2023-2026.
- [ ] [G12-A10-T1969] Testar: Docker roadmap.
- [ ] [G12-A10-T1970] Revisar: OCR roadmap.

### G12-A11
- [ ] [G12-A11-T1971] Documentar: DLQ roadmap.
- [ ] [G12-A11-T1972] Otimizar: 304 roadmap.
- [ ] [G12-A11-T1973] Validar: schedulers (nao).
- [ ] [G12-A11-T1974] Medir: custo operacional.
- [ ] [G12-A11-T1975] Automatizar: repetibilidade.
- [ ] [G12-A11-T1976] Implementar: backup .db.
- [ ] [G12-A11-T1977] Testar: novo trimestre.
- [ ] [G12-A11-T1978] Revisar: nova empresa (+CIK).
- [ ] [G12-A11-T1979] Documentar: novo indicador (+regra).
- [ ] [G12-A11-T1980] Otimizar: nova moeda.

### G12-A12
- [ ] [G12-A12-T1981] Validar: Docker roadmap.
- [ ] [G12-A12-T1982] Medir: OCR roadmap.
- [ ] [G12-A12-T1983] Automatizar: produtividade roadmap.
- [ ] [G12-A12-T1984] Implementar: DLQ roadmap.
- [ ] [G12-A12-T1985] Testar: 304 roadmap.
- [ ] [G12-A12-T1986] Revisar: schedulers (nao).
- [ ] [G12-A12-T1987] Documentar: custo operacional.
- [ ] [G12-A12-T1988] Otimizar: repetibilidade.
- [ ] [G12-A12-T1989] Validar: backup .db.
- [ ] [G12-A12-T1990] Medir: novo trimestre.

### G12-A13
- [ ] [G12-A13-T1991] Automatizar: novo indicador (+regra).
- [ ] [G12-A13-T1992] Implementar: nova moeda.
- [ ] [G12-A13-T1993] Testar: 4 anos 2023-2026.
- [ ] [G12-A13-T1994] Revisar: Docker roadmap.
- [ ] [G12-A13-T1995] Documentar: OCR roadmap.
- [ ] [G12-A13-T1996] Otimizar: produtividade roadmap.
- [ ] [G12-A13-T1997] Validar: DLQ roadmap.
- [ ] [G12-A13-T1998] Medir: 304 roadmap.
- [ ] [G12-A13-T1999] Automatizar: schedulers (nao).
- [ ] [G12-A13-T2000] Implementar: custo operacional.

### G12-A14
- [ ] [G12-A14-T2001] Testar: backup .db.
- [ ] [G12-A14-T2002] Revisar: novo trimestre.
- [ ] [G12-A14-T2003] Documentar: nova empresa (+CIK).
- [ ] [G12-A14-T2004] Otimizar: novo indicador (+regra).
- [ ] [G12-A14-T2005] Validar: nova moeda.
- [ ] [G12-A14-T2006] Medir: 4 anos 2023-2026.
- [ ] [G12-A14-T2007] Automatizar: Docker roadmap.
- [ ] [G12-A14-T2008] Implementar: OCR roadmap.
- [ ] [G12-A14-T2009] Testar: produtividade roadmap.
- [ ] [G12-A14-T2010] Revisar: DLQ roadmap.

### G12-A15
- [ ] [G12-A15-T2011] Documentar: schedulers (nao).
- [ ] [G12-A15-T2012] Otimizar: custo operacional.
- [ ] [G12-A15-T2013] Validar: repetibilidade.
- [ ] [G12-A15-T2014] Medir: backup .db.
- [ ] [G12-A15-T2015] Automatizar: novo trimestre.
- [ ] [G12-A15-T2016] Implementar: nova empresa (+CIK).
- [ ] [G12-A15-T2017] Testar: novo indicador (+regra).
- [ ] [G12-A15-T2018] Revisar: nova moeda.
- [ ] [G12-A15-T2019] Documentar: 4 anos 2023-2026.
- [ ] [G12-A15-T2020] Otimizar: Docker roadmap.

### G12-A16
- [ ] [G12-A16-T2021] Validar: produtividade roadmap.
- [ ] [G12-A16-T2022] Medir: DLQ roadmap.
- [ ] [G12-A16-T2023] Automatizar: 304 roadmap.
- [ ] [G12-A16-T2024] Implementar: schedulers (nao).
- [ ] [G12-A16-T2025] Testar: custo operacional.
- [ ] [G12-A16-T2026] Revisar: repetibilidade.
- [ ] [G12-A16-T2027] Documentar: backup .db.
- [ ] [G12-A16-T2028] Otimizar: novo trimestre.
- [ ] [G12-A16-T2029] Validar: nova empresa (+CIK).
- [ ] [G12-A16-T2030] Medir: novo indicador (+regra).

### G12-A17
- [ ] [G12-A17-T2031] Automatizar: 4 anos 2023-2026.
- [ ] [G12-A17-T2032] Implementar: Docker roadmap.
- [ ] [G12-A17-T2033] Testar: OCR roadmap.
- [ ] [G12-A17-T2034] Revisar: produtividade roadmap.
- [ ] [G12-A17-T2035] Documentar: DLQ roadmap.
- [ ] [G12-A17-T2036] Otimizar: 304 roadmap.
- [ ] [G12-A17-T2037] Validar: schedulers (nao).
- [ ] [G12-A17-T2038] Medir: custo operacional.
- [ ] [G12-A17-T2039] Automatizar: repetibilidade.
- [ ] [G12-A17-T2040] Implementar: backup .db.

**Total: 2040 tarefas.**