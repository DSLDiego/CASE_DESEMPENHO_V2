# Performance e paralelismo
- Lote configurável 5/10/15/20/50/100/Auto (=min(logicos,15)); workers até 128.
- PROCESS (ProcessPool): único paralelismo real p/ regex/parsing (GIL); recomendado p/ docs grandes.
- THREAD: leve; ganha em arquivos pequenos e I/O (pyarrow/C libera GIL).
- SUBPROCESS (`python -m` por arquivo): isolamento total; overhead ~0.6s/arquivo — usar p/ .doc/.xls/OCR.
- Scheduler SJF≈tamanho×fator-formato; SRTF/RR/MLFQ na fila (sem preempção no parse).
- Economias: SHA sobre bytes já lidos, skip por hash, cache HTTP (ETag/304) + manifest JSONL.
- Hardware: psutil→os.cpu_count; nvidia-smi→torch→nenhum (informativo; GPU não acelera regex).
- Medir: tempo/arquivo, arq/s, parse P50/P95, retry%, cache-hit% (aba ETL + `etl_item.elapsed_ms`).
