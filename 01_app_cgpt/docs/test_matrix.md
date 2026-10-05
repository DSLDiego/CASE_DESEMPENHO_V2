# Matriz de testes (v0 entregue)
| Frente | Caso | Resultado |
|---|---|---|
| PeriodResolver | 2Q26 / 2T2026 / YTD June 30 2026 | OK (11 passed) |
| Schedulers | FIFO FILO SJF SRTF RR PRIORITY MLQ MLFQ HRRN FAIR-SHARE | OK |
| Parsers | TXT CSV HTML DOCX-fallback | OK |
| Extractors | Revenue 86.3bi, headcount 101k | OK |
| Quality | SOURCE_CHANGE 10→20=100%, desvios, reconciliação, completude | OK |
| Batch THREAD lote 5/10 | 3 formatos | OK (0.9s) |
| Batch PROCESS lote 5 | 3 formatos | OK |
| Batch SUBPROCESS lote 5 | 3 formatos | OK |
| ETL real (txt+csv+xlsx) | THREAD 3/3, PROCESS 3/3 | OK |
| CLI status | 3 períodos + narrativa | OK |
| GUI offscreen | 9 abas, 4 empresas | OK |
