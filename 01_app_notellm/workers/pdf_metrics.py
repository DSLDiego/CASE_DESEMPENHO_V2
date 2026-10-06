"""Backfill da métrica de leitura dos PDFs (M8.12).

`n_paginas`/`n_tabelas` nascem no parse. Os 714 PDFs já processados antes da
métrica existir ficariam sem número para sempre, e o painel mostraria "0 PDFs
medidos" — que parece "nenhum PDF tem métrica" em vez de "ninguém foi medido".

Este worker mede o que já está no acervo **sem reprocessar**: só conta páginas e
detecta tabelas, o que custa ~0,2 s por documento (a leitura de texto e a
extração ficam de fora — extrair de novo seria jogar fora o trabalho do ETL). A
contagem roda em processos, porque é CPU-bound e não toca no banco.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from models.database import DatabaseManager
from models.repositories import FonteRepository


def _medir(caminho_str: str) -> tuple[str, int, int]:
    """(caminho, páginas, tabelas). Nunca levanta exceção."""
    from workers.parse_pdf import metricas
    try:
        m = metricas(Path(caminho_str), max_pages=12)
        return (caminho_str, int(m["paginas"]), int(m["tabelas"]))
    except Exception:                             # noqa: BLE001
        return (caminho_str, 0, 0)


def _rodar_serial(trabalhos: list[str]) -> list[tuple[str, int, int]]:
    return [_medir(c) for c in trabalhos]


def medir_metricas_pdf(db: DatabaseManager | None = None, apenas_sem_metrica: bool = True,
                        limite: int | None = None, jobs: int | None = None,
                        verbose: bool = False) -> dict[str, Any]:
    """Mede páginas/tabelas dos PDFs já catalogados e grava em `tb_fonte_dados`.

    `apenas_sem_metrica=True` (padrão) pula o que já foi medido, então rodar de novo
    é barato. Documento whose file sumiu ou não é PDF é pulado, não zerado — zero
    aqui significaria "mediu e não tem página".
    """
    db = db or DatabaseManager()
    fontes = FonteRepository(db)
    linhas = [f for f in fontes.listar() if (f.get("extensao") or "") == ".pdf"]
    if apenas_sem_metrica:
        linhas = [f for f in linhas if f.get("n_paginas") is None]
    trabalhos: list[str] = []
    sem_arquivo = 0
    for f in linhas:
        caminho = f.get("caminho_local") or ""
        if not caminho or not Path(caminho).is_file():
            sem_arquivo += 1
            continue
        trabalhos.append(caminho)
        if limite and len(trabalhos) >= limite:
            break
    n_cpus = os.cpu_count() or 2
    jobs = max(1, min(jobs if jobs is not None else max(1, n_cpus - 1), 8))
    if not trabalhos:
        return {"medidos": 0, "paginas": 0, "tabelas": 0, "sem_arquivo": sem_arquivo,
                "jobs": jobs, "restantes": len(linhas) - len(trabalhos)}
    resultados: list[tuple[str, int, int]] = []
    if jobs > 1 and len(trabalhos) > 1:
        from concurrent.futures import ProcessPoolExecutor
        from concurrent.futures.process import BrokenProcessPool
        try:
            with ProcessPoolExecutor(max_workers=jobs) as pool:
                resultados = list(pool.map(_medir, trabalhos))
        except (BrokenProcessPool, OSError, ImportError, AttributeError, TypeError):
            resultados = _rodar_serial(trabalhos)
        except Exception:                          # noqa: BLE001
            resultados = _rodar_serial(trabalhos)
    else:
        resultados = _rodar_serial(trabalhos)

    por_caminho = {c: (p, t) for c, p, t in resultados if p > 0}
    gravados = paginas = tabelas = 0
    with db.connect() as conn:
        for f in linhas:
            caminho = f.get("caminho_local") or ""
            if caminho not in por_caminho:
                continue
            p, t = por_caminho[caminho]
            conn.execute("UPDATE tb_fonte_dados SET n_paginas = ?, n_paginas_lidas = ?,"
                         " n_tabelas = ? WHERE id_fonte = ?",
                         (p, min(p, 12), t, f["id_fonte"]))
            gravados += 1
            paginas += p
            tabelas += t
            if verbose and gravados % 50 == 0:
                print(f"  {gravados}/{len(trabalhos)} medidos...")
        conn.commit()
    return {"medidos": gravados, "paginas": paginas, "tabelas": tabelas,
            "sem_arquivo": sem_arquivo, "jobs": jobs,
            "restantes": len(linhas) - gravados - sem_arquivo}