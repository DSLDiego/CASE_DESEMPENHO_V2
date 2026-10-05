"""Servicos de aplicacao (casos de uso)."""
from __future__ import annotations
import csv
import time
from pathlib import Path

from src.etl import batch as batch_engine
from src.etl import quality as Q
from src.repositories.sqlite_repo import SQLiteRepository

BASE = Path(__file__).resolve().parents[2]


class DashboardService:
    def __init__(self, repo: SQLiteRepository | None = None) -> None:
        self.repo = repo or SQLiteRepository()

    def periods(self) -> list[str]:
        rows = self.repo.query("SELECT period_id FROM period ORDER BY year, quarter")
        return [r["period_id"] for r in rows] or ["4T2025", "1T2026", "2T2026"]

    def executive_view(self, period: str) -> dict:
        rows = self.repo.pivot(period)
        table: dict[str, dict[str, float | None]] = {}
        for r in rows:
            table.setdefault(r["company_id"], {})[r["indicator_id"]] = r["value"]
        narrative = self._narrative(period, table)
        return {"period": period, "table": table, "narrative": narrative,
                "is_demo": any(True for _ in rows)}

    def _narrative(self, period: str, table: dict) -> str:
        if not table:
            return "Sem dados para o periodo. Importe o demo ou colete documentos de RI."
        def get(c, i):
            v = table.get(c, {}).get(i)
            return v if v is not None else float("nan")
        import math
        eb = {c: get(c, "EBITDA_ADJ") for c in table}
        eb_ok = {c: v for c, v in eb.items() if not math.isnan(v)}
        top = max(eb_ok, key=eb_ok.get) if eb_ok else "-"
        rev = {c: (get(c, "REVENUE") or 0) / max(get(c, "EMPLOYEES") or 1, 1) for c in table}
        prod = max(rev, key=rev.get) if rev else "-"
        return (f"No trimestre {period}, {top} lidera o EBITDA ajustado entre os pares da PoC. "
                f"{prod} apresenta a maior receita por empregado, sugerindo elevada produtividade relativa. "
                f"Base marcada como demonstrativa quando is_demo=1 — substituir por coleta oficial de RI.")

    def history(self, indicator: str) -> dict[str, list]:
        out: dict[str, list] = {}
        for c in ("PETROBRAS", "EQUINOR", "SHELL", "TOTALENERGIES"):
            out[c] = self.repo.history(c, indicator)
        return out

    def productivity(self, period: str) -> dict[str, float]:
        rows = self.repo.pivot(period)
        by: dict[str, dict] = {}
        for r in rows:
            by.setdefault(r["company_id"], {})[r["indicator_id"]] = r["value"]
        out = {}
        for c, d in by.items():
            rev, emp = d.get("REVENUE"), d.get("EMPLOYEES")
            ebit, emp2 = d.get("EBITDA_ADJ"), d.get("EMPLOYEES")
            if rev and emp:
                out[f"{c} receita/empregado"] = rev * 1e6 / emp
            if ebit and emp2:
                out[f"{c} ebitda/empregado"] = ebit * 1e6 / emp2
        return out


class BatchETLService:
    """Orquestra batch -> normalizacao -> qualidade -> load (1 Load Coordinator)."""

    def __init__(self, repo: SQLiteRepository | None = None) -> None:
        self.repo = repo or SQLiteRepository()

    def run(self, files: list[str], mode: str = "PROCESS", batch_size=10,
            scheduler: str = "FIFO", max_workers: int = 8,
            on_progress=None, cancel=None, company_hint: str = "") -> dict:
        t0 = time.perf_counter()
        with self.repo.connect() as con:
            con.execute("INSERT INTO etl_run (mode) VALUES (?)", ("BATCH_" + mode,))
            run_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        tasks = [batch_engine.FileTask(p, company_hint, "") for p in files]
        results = batch_engine.run_batch(tasks, mode, batch_size, scheduler, max_workers, on_progress, cancel)
        ok = sum(1 for r in results if r.ok)
        failed = [r for r in results if not r.ok]
        # LOAD coordenado + qualidade
        expected = {"REVENUE", "EBITDA_ADJ", "NET_INCOME", "NET_INCOME_ADJ", "OCF", "EMPLOYEES"}
        with self.repo.connect() as con:
            for r in results:
                sid = f"ETL|{Path(r.path).name}|{r.sha256[:12] if r.sha256 else 'nosha'}"
                comp = (r.extractions[0].company_id if r.extractions else "") or company_hint or "UNKNOWN"
                per = r.extractions[0].period_id if r.extractions else ""
                self.repo.upsert_source(con, sid, comp, Path(r.path).name, "", r.sha256, r.path, False)
                found: set[str] = set()
                for e in r.extractions:
                    c = e.company_id or comp or "UNKNOWN"
                    p = e.period_id or per or "2T2026"
                    self.repo.insert_observation(con, c, p, e.indicator_id, e.value, e.currency,
                                                 e.unit, sid, e.confidence, e.evidence, e.method, False)
                    found.add(e.indicator_id)
                    if e.confidence < 0.70:
                        self.repo.add_quality_issue("LOW_CONFIDENCE", "WARNING",
                                                    f"Confianca {e.confidence:.2f} exige revisao ({e.method})",
                                                    c, p, e.indicator_id, e.value, _con=con)
                for iss in Q.check_completeness(found, expected, comp, per or "?"):
                    self.repo.add_quality_issue(iss.rule, iss.severity, iss.message, iss.company_id,
                                                iss.period_id, iss.indicator_id, _con=con)
                con.execute("""INSERT INTO etl_item (run_id, file_path, company_id, period_id, status, message, elapsed_ms, sha256)
                               VALUES (?,?,?,?,?,?,?,?)""",
                            (run_id, r.path, comp, per, "OK" if r.ok else "FAILED",
                             r.error[:500], r.elapsed_ms, r.sha256))
                if not r.ok:
                    con.execute("INSERT INTO quarantine (file_path, error, stage) VALUES (?,?,?)",
                                (r.path, r.error[:800], r.stage))
            con.execute("""UPDATE etl_run SET finished_at=datetime('now'), files_total=?, files_ok=?,
                           files_failed=?, notes=? WHERE run_id=?""",
                        (len(results), ok, len(failed), f"scheduler={scheduler} batch={batch_size}", run_id))
        return {"run_id": run_id, "total": len(results), "ok": ok, "failed": len(failed),
                "elapsed_s": round(time.perf_counter() - t0, 2), "results": results}

    def import_csv(self, csv_path: str) -> int:
        n = 0
        with self.repo.connect() as con:
            with open(csv_path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    sid = f"CSV|{row.get('company')}|{row.get('period')}|{row.get('source_doc', 'csv')}"
                    self.repo.upsert_source(con, sid, row["company"], row.get("source_doc", "csv"),
                                            row.get("source_url", ""), "", csv_path, False)
                    self.repo.insert_observation(con, row["company"], row["period"], row["indicator"],
                                                 float(row["value"]), row.get("currency", "USD") or "USD",
                                                 row.get("unit", "USD_M") or "USD_M", sid,
                                                 float(row.get("confidence", 0.9) or 0.9),
                                                 row.get("evidence", ""), "CSV_IMPORT", False)
                    n += 1
        return n


class CollectionService:
    def __init__(self, repo: SQLiteRepository | None = None) -> None:
        self.repo = repo or SQLiteRepository()

    def download_urls(self, urls: list[str], company: str, period: str, max_workers: int = 16,
                      registry=None, source_id: str = "", source_name: str = "") -> list[dict]:
        import concurrent.futures as cf
        from src.etl.acquisition import download_one
        raw = BASE / "data" / "raw" / company / period
        out: list[dict] = []

        class _Limiter:
            def __init__(self, per_host: int = 8):
                import threading
                self.per_host = per_host
                self._locks: dict[str, threading.Semaphore] = {}
                self._mu = threading.Lock()

            def _sem(self, url: str):
                import urllib.parse
                host = urllib.parse.urlparse(url).netloc
                with self._mu:
                    return self._locks.setdefault(host, __import__("threading").Semaphore(self.per_host))

            def acquire(self, url: str):
                self._sem(url).acquire()

            def release(self, url: str):
                self._sem(url).release()

        lim = _Limiter()

        def one(u: str) -> dict:
            try:
                r = download_one(u, raw, per_host_limiter=lim)
                rec = {"url": u, "ok": True, "path": r.local_path, "sha": r.sha256}
            except Exception as e:  # noqa: BLE001
                rec = {"url": u, "ok": False, "error": str(e)[:300]}
            if registry is not None:  # controle anti-repeticao em CSV (9.1/9.2)
                registry.log_download(company, source_id, source_name, u,
                                      rec.get("path", ""), rec.get("sha", ""), 0, "",
                                      "OK" if rec["ok"] else f"FAILED: {rec.get('error', '')}"[:200])
            return rec

        with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
            for rec in ex.map(one, urls):
                out.append(rec)
        return out
