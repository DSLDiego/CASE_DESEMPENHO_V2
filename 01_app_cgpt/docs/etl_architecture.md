# Arquitetura ETL (v0 consolidada)
```
RI / Internet → Discovery (seed/sitemap/busca/links, score autoridade+periodo+tipo)
→ Qualification (DocumentCandidate, PeriodResolver, SourceAuthorityValidator)
→ Download (threads, retry/backoff, ETag/304, streaming, .part+rename, SHA-256, manifest)
→ RAW imutável data/raw/<empresa>/<periodo>
→ Batch (PROCESS/THREAD/SUBPROCESS, lote 5–100/Auto, scheduler FIFO…FAIR-SHARE, FIRST_COMPLETED, cancel)
→ Parser (PDF/XLS/XLSX/XLSM/CSV/DOC/DOCX/TXT/HTML → CanonicalDocument, streaming)
→ Extractor (tabela > especifico > secao > semantico > regex; evidencia + confidence)
→ Normalizacao (moeda/escala/sinal, Quarter≠YTD, adjusted≠reportado)
→ Quality/Reconciliacao (completude, desvio, source_change, quorum de fontes)
→ Load idempotente (1 coordinator → SQLite WAL) → metric_current → Painel MVC
```
I/O-bound=threads · CPU-bound=processos · instável=subprocess. Backpressure por filas limitadas.
