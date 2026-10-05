# Atualização trimestral (ex.: 3T2026)
1. `python scripts/collect_web.py PETROBRAS 3T2026 "<url release>"` (ou aba ETL).
2. Arquivos caem em `data/raw/PETROBRAS/3T2026/` com SHA + manifest (idempotente).
3. `python app_main.py --etl data/raw --mode PROCESS --batch Auto --scheduler SJF`.
4. Checar aba Qualidade; reconciliar release × DF.
5. Nada é reconstruído: só novas linhas em `observation`; `metric_current` publica a melhor.
Tempo estimado: minutos (cache HTTP + skip por SHA).
