# Controles de qualidade (evidências)
1. **Completude**: matriz 4 emp × 3 trim × 6 ind = 72 obs esperadas; faltantes geram WARNING.
2. **Confianca**: extração < 0.70 → REVIEW_REQUIRED (tabela=1.0, texto-estruturado≈0.8, regex≈0.6).
3. **Desvio histórico**: limites por indicador (Receita ±30%, EBITDA ±50%, Lucro ±100%, Efetivo ±15%).
4. **SOURCE_CHANGE**: valor substituído gera WARNING com % (demo 10→20 = 100%).
5. **Reconciliação**: duas fontes do mesmo fato → RECONCILED ou RECONCILIATION_WARNING (tol 2%).
6. **Quarentena/DLQ**: arquivo com erro não para o lote; reprocessamento seletivo.
7. **Auditoria**: `etl_run/etl_item/file_manifest/source(sha,etag,versão)` + evidência (trecho/página/planilha).
Ver: aba Qualidade + `pytest tests/test_quality.py` + `python scripts/demo_quality.py`.
