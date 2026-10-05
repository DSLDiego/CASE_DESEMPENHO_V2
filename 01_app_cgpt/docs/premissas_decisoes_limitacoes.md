# Premissas, decisões e limitações
## Tecnológicas
- SQLite+WAL resolve a PoC; Repository permite migrar p/ Postgres/SQL Server sem reescrever domínio.
- Parsing CPU-bound → PROCESS recomendado; I/O → THREAD; conversores instáveis (.doc/.xls/OCR) → SUBPROCESS.
- Sem preempção no meio do parse (SRTF/RR/MLFQ atuam na fila).
- Limite 64+ threads = capacidade, não obrigação; por-host 8 p/ não agredir RI + retry/backoff.
- BigString: streaming, `join`, hash em chunks; sem 2ª leitura só p/ hash.
## Financeiras
- Total de Efetivo = operacional (não financeiro), incluído por exigência.
- Moeda: fonte preservada; comparável em USD_M (BRL×0.20 demo; produção = PTAX do período).
- Adjusted vs reportado são indicadores distintos; Quarter ≠ YTD (PeriodResolver marca is_ytd).
- Demo ≠ oficial: `is_demo=1`, confiança 0.6, substituir antes da banca.
