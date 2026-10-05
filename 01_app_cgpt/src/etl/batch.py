"""Motor batch: PROCESS / THREAD / SUBPROCESS, lotes limitados (FIRST_COMPLETED),
fila ordenada por scheduler, cancelamento, metricas por arquivo, quarantine/DLQ."""
from __future__ import annotations
import concurrent.futures as cf
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.etl import parsers, extractors
from src.etl.scheduler import make_jobs, order_jobs
from src.utils.bigstring import sha256_file
from src.utils.period import resolve_period


@dataclass
class FileTask:
    path: str
    company: str = ""
    period: str = ""


@dataclass
class FileResult:
    path: str
    ok: bool
    extractions: list = field(default_factory=list)
    elapsed_ms: int = 0
    sha256: str = ""
    error: str = ""
    stage: str = "PARSED"


class CancelToken:
    def __init__(self) -> None:
        self._ev = threading.Event()

    def cancel(self) -> None:
        self._ev.set()

    @property
    def cancelled(self) -> bool:
        return self._ev.is_set()


def _company_period_from_path(path: str) -> tuple[str, str]:
    import re
    up = path.upper()
    comp = ""
    for c in ("PETROBRAS", "EQUINOR", "SHELL", "TOTAL", "BP", "CHEVRON", "EXXON"):
        if c in up:
            comp = "TOTALENERGIES" if c == "TOTAL" else (c if c != "EXXON" else "EXXONMOBIL")
            break
    m = re.search(r"([1-4])T(\d{4})", up)
    per = f"{m.group(1)}T{m.group(2)}" if m else ""
    return comp, per


def process_single(path: str, company: str = "", period: str = "") -> FileResult:
    t0 = time.perf_counter()
    try:
        p = Path(path)
        if not p.exists():
            return FileResult(path, False, [], 0, "", f"arquivo nao encontrado", "READ")
        sha, _ = sha256_file(p)
        comp = company or _company_period_from_path(path)[0]
        per = period or _company_period_from_path(path)[1]
        if not per:
            try:
                head = p.read_bytes()[:20000].decode("utf-8", "ignore")
            except Exception:
                head = p.stem
            ctx = resolve_period(head, p.stem)
            per = ctx.label if ctx else ""
        doc = parsers.parse_file(p, comp, per)
        exts = extractors.extract(doc)
        el = int((time.perf_counter() - t0) * 1000)
        return FileResult(path, True, exts, el, sha, "", "PARSED")
    except Exception as e:  # noqa: BLE001
        return FileResult(path, False, [], int((time.perf_counter() - t0) * 1000), "", str(e), "PARSER_FAILED")


def _subprocess_one(path: str, company: str, period: str) -> FileResult:
    code = (
        "import sys; sys.path.insert(0, '.');"
        "from src.etl.batch import process_single;"
        f"r = process_single({path!r}, {company!r}, {period!r});"
        "import json; print(json.dumps({'ok': r.ok, 'elapsed_ms': r.elapsed_ms, 'sha256': r.sha256,"
        " 'error': r.error, 'stage': r.stage,"
        " 'exts': [{'company_id': e.company_id, 'period_id': e.period_id, 'indicator_id': e.indicator_id,"
        " 'value': e.value, 'currency': e.currency, 'unit': e.unit, 'confidence': e.confidence,"
        " 'evidence': e.evidence, 'method': e.method} for e in r.extractions]}))"
    )
    try:
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
        if out.returncode != 0:
            return FileResult(path, False, [], 0, "", (out.stderr or "subprocess fail")[:500], "SUBPROCESS")
        import json
        data = json.loads(out.stdout.strip().splitlines()[-1])
        from src.models.entities import Extraction
        exts = [Extraction(**e) for e in data.get("exts", [])]
        return FileResult(path, bool(data["ok"]), exts, data["elapsed_ms"], data["sha256"], data["error"], data["stage"])
    except Exception as e:  # noqa: BLE001
        return FileResult(path, False, [], 0, "", str(e)[:500], "SUBPROCESS")


def run_batch(tasks: list[FileTask], mode: str = "PROCESS", batch_size: int | str = 10,
              scheduler: str = "FIFO", max_workers: int = 8,
              on_progress=None, cancel: CancelToken | None = None) -> list[FileResult]:
    mode = (mode or "PROCESS").upper()
    if isinstance(batch_size, str) and batch_size.lower() == "auto":
        import os as _os
        batch_size = max(2, min(_os.cpu_count() or 4, 15))
    batch_size = max(1, int(batch_size))
    sizes = {}
    for t in tasks:
        try:
            sizes[t.path] = Path(t.path).stat().st_size
        except OSError:
            sizes[t.path] = 0
    jobs = make_jobs([t.path for t in tasks], sizes)
    ordered = order_jobs(jobs, scheduler)
    by_path = {t.path: t for t in tasks}
    tasks = [by_path[j.path] for j in ordered]

    results: list[FileResult] = []
    idx = 0

    def submit_one(ex, task: FileTask):
        if mode == "THREAD":
            return ex.submit(process_single, task.path, task.company, task.period)
        if mode == "SUBPROCESS":
            return ex.submit(_subprocess_one, task.path, task.company, task.period)
        return ex.submit(process_single, task.path, task.company, task.period)

    Executor = cf.ProcessPoolExecutor if mode == "PROCESS" else cf.ThreadPoolExecutor
    # SUBPROCESS usa threads coordenando subprocessos isolados
    with Executor(max_workers=max_workers) as ex:
        in_flight: dict = {}
        while idx < len(tasks) or in_flight:
            if cancel and cancel.cancelled:
                for f in in_flight:
                    f.cancel()
                break
            while idx < len(tasks) and len(in_flight) < batch_size:
                fut = submit_one(ex, tasks[idx])
                in_flight[fut] = tasks[idx]
                idx += 1
            if not in_flight:
                break
            done, _ = cf.wait(list(in_flight), return_when=cf.FIRST_COMPLETED)
            for fut in done:
                task = in_flight.pop(fut)
                try:
                    res = fut.result()
                except Exception as e:  # noqa: BLE001
                    res = FileResult(task.path, False, [], 0, "", str(e)[:500], "FAILED")
                results.append(res)
                if on_progress:
                    try:
                        on_progress(res, len(results), len(tasks))
                    except Exception:
                        pass
    # preserva ordem de conclusao; chamador pode reordenar se quiser
    return results
