# Roteiro de apresentação executiva (15 min)

| Tempo | Tópico | Fala-guia |
|---|---|---|
| 0–2 | Contexto | RI de 7 petroleiras publicam o mesmo fato em 7 dialetos; consolidamos tudo numa base única, rastreável e atualizável por trimestre. |
| 2–5 | Arquitetura | MVC-W + SQLite: Model (6 tabelas), Workers (scan, parse_*, SEC, qualidade), Controllers finos, Views duplas. Demo: `app_main.py status`. |
| 5–8 | ETL ao vivo | `app_main.py etl`: 133 arquivos, hash anti-duplicidade, De-Para PT/EN, escala milhões→bi, auditoria (negativos, spikes, cobertura). Mostrar `sources_catalog.csv` + fila de revisão. |
| 8–12 | Painel | Web: sidebar 25% + tabs + grid; executiva 2T26, comparação, evolução; GUI PySide6 com mesmo dado. Leitura: líder de receita/margem no trimestre. |
| 12–15 | Atualização e escala | Novo trimestre = soltar arquivos + `etl` (sem rebuild). Escalar = +1 linha por empresa, +1 regra por indicador. Limites honestos: efetivo parcial, FX de fechamento. Convite a perguntas. |

Checklist demo: `full` rodado antes; `data/painel_benchmark.html` aberto; `status` com insight do 2T26 na ponta da língua.
