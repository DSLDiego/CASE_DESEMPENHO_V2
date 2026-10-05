"""Escalonadores de processos: FIFO, FILO, SJF, SRTF, RR, PRIORITY, MLQ, MLFQ, HRRN, FAIR-SHARE.

Premissas: parsing de arquivo nao e preemptivo de forma segura; SRTF/RR/MLFQ
atuam sobre a FILA nao despachada. Estimativa de custo = size * format_factor.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import heapq


FORMAT_FACTOR = {".pdf": 1.0, ".xlsx": 1.5, ".xlsm": 1.5, ".xls": 2.0,
                 ".csv": 0.5, ".txt": 0.4, ".html": 0.6, ".docx": 1.2,
                 ".doc": 2.5, "": 1.0}

PRIORITY_FMT = {".pdf": 2, ".xlsx": 2, ".xlsm": 2, ".xls": 3, ".csv": 1,
                ".txt": 1, ".html": 1, ".docx": 2, ".doc": 3}


@dataclass
class Job:
    path: str
    size: int = 0
    ext: str = ""
    priority: int = 5
    arrival: int = 0
    waited: int = 0
    history_ms: float = 0.0

    def cost(self) -> float:
        base = float(self.size or 50_000)
        f = FORMAT_FACTOR.get(self.ext.lower(), 1.0)
        hist = self.history_ms if self.history_ms > 0 else base / 1024.0
        return 0.3 * (base / 1024.0 * f) + 0.7 * hist


def _ext_of(path: str) -> str:
    i = path.lower().rfind(".")
    return path.lower()[i:] if i >= 0 else ""


def make_jobs(paths: list[str], sizes: dict[str, int] | None = None) -> list[Job]:
    sizes = sizes or {}
    jobs = []
    for i, p in enumerate(paths):
        ext = _ext_of(p)
        jobs.append(Job(path=p, size=sizes.get(p, 0), ext=ext,
                        priority=PRIORITY_FMT.get(ext, 5), arrival=i))
    return jobs


def order_jobs(jobs: list[Job], algo: str = "FIFO", quantum: int = 1) -> list[Job]:
    algo = (algo or "FIFO").upper()
    if algo == "FIFO":
        return sorted(jobs, key=lambda j: j.arrival)
    if algo == "FILO":
        return sorted(jobs, key=lambda j: -j.arrival)
    if algo == "SJF":
        return sorted(jobs, key=lambda j: (j.cost(), j.arrival))
    if algo == "SRTF":
        # nao-preemptivo na pratica: ordena por menor restante estimado
        return sorted(jobs, key=lambda j: (j.cost(), j.arrival))
    if algo == "RR":
        # round-robin = intercala por chegada (quantum aplicado no despacho em lotes)
        return sorted(jobs, key=lambda j: j.arrival)
    if algo == "PRIORITY":
        return sorted(jobs, key=lambda j: (j.priority, j.cost(), j.arrival))
    if algo == "MLQ":
        # filas: alta(p<=2) > media(p<=5) > baixa; FIFO dentro da fila
        return sorted(jobs, key=lambda j: (0 if j.priority <= 2 else 1 if j.priority <= 5 else 2, j.arrival))
    if algo == "MLFQ":
        # feedback: quem esperou muito sobe de nivel
        def level(j: Job) -> int:
            if j.priority <= 2 or j.waited > 10:
                return 0
            if j.priority <= 5 or j.waited > 5:
                return 1
            return 2
        return sorted(jobs, key=lambda j: (level(j), j.cost()))
    if algo == "HRRN":
        # response ratio = (waited + cost) / cost ; maior primeiro
        def rr(j: Job) -> float:
            c = max(j.cost(), 1e-6)
            return (j.waited + c) / c
        return sorted(jobs, key=lambda j: (-rr(j), j.arrival))
    if algo in ("FAIR-SHARE", "FAIRSHARE", "FAIR"):
        # alterna por empresa (prefixo do path) para divisao justa
        buckets: dict[str, list[Job]] = {}
        for j in jobs:
            key = j.path.split("\\")[-1].split("/")[-1][:3]
            buckets.setdefault(key, []).append(j)
        out: list[Job] = []
        while any(buckets.values()):
            for k in sorted(buckets):
                if buckets[k]:
                    out.append(buckets[k].pop(0))
        return out
    return sorted(jobs, key=lambda j: j.arrival)


ALGORITHMS = ["FIFO", "FILO", "SJF", "SRTF", "RR", "PRIORITY", "MLQ", "MLFQ", "HRRN", "FAIR-SHARE"]
