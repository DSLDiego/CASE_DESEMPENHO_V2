"""Repository SQLite (SOLID: DIP — servicos dependem desta abstracao, nao de SQL)."""
from __future__ import annotations
import csv
import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
DB_PATH = BASE / "database" / "benchmarking.sqlite"
SCHEMA = BASE / "database" / "schema.sql"


class SQLiteRepository:
    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def init_schema(self) -> None:
        sql = SCHEMA.read_text(encoding="utf-8")
        with self.connect() as con:
            con.executescript(sql)
            self._seed(con)

    def _seed(self, con: sqlite3.Connection) -> None:
        companies = json.loads((BASE / "config" / "companies.json").read_text(encoding="utf-8"))["companies"]
        for cid, c in companies.items():
            con.execute("INSERT OR IGNORE INTO company VALUES (?,?,?,?,?,?)",
                        (cid, c["name"], c.get("country", ""), c.get("currency", "USD"), 1, 1 if c.get("in_poc") else 0))
        indicators = json.loads((BASE / "config" / "indicators.json").read_text(encoding="utf-8"))["indicators"]
        for iid, ind in indicators.items():
            con.execute("INSERT OR IGNORE INTO indicator VALUES (?,?,?,?,?)",
                        (iid, ind["name"], ind.get("category", ""), ind.get("unit", "USD_M"), ind.get("definition", "")))
        for per in ["4T2025", "1T2026", "2T2026", "3T2026"]:
            q, y = int(per[0]), int(per[2:])
            con.execute("INSERT OR IGNORE INTO period VALUES (?,?,?,?,?,?)",
                        (per, y, q, per, "QUARTER", 0))

    # ---- escrita idempotente ----
    def upsert_source(self, con: sqlite3.Connection, source_id: str, company: str, doc: str,
                      url: str = "", sha: str = "", local_path: str = "", is_demo: bool = False,
                      authority: str = "UNKNOWN") -> None:
        con.execute("""INSERT INTO source (source_id, company_id, document, url, sha256, local_path, is_demo, authority)
                       VALUES (?,?,?,?,?,?,?,?)
                       ON CONFLICT(source_id) DO UPDATE SET sha256=excluded.sha256, version=version+1,
                         local_path=excluded.local_path""",
                    (source_id, company, doc, url, sha, local_path, 1 if is_demo else 0, authority))

    def insert_observation(self, con: sqlite3.Connection, company: str, period: str, indicator: str,
                           value: float | None, currency: str = "USD", unit: str = "USD_M",
                           source_id: str = "", confidence: float = 0.6, evidence: str = "",
                           method: str = "", is_demo: bool = False) -> str | None:
        """Retorna 'SOURCE_CHANGE:...' se substituiu valor existente diferente."""
        cur = con.execute("""SELECT value, obs_id FROM observation
                             WHERE company_id=? AND period_id=? AND indicator_id=? AND source_id=?""",
                          (company, period, indicator, source_id))
        row = cur.fetchone()
        if row is None:
            con.execute("""INSERT INTO observation
                           (company_id, period_id, indicator_id, value, currency, unit, source_id,
                            confidence, evidence, method, is_demo)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (company, period, indicator, value, currency, unit, source_id,
                         confidence, evidence[:500], method, 1 if is_demo else 0))
            return None
        old = row["value"]
        con.execute("""UPDATE observation SET value=?, confidence=?, evidence=?, method=?, created_at=datetime('now')
                       WHERE obs_id=?""", (value, confidence, evidence[:500], method, row["obs_id"]))
        if old is not None and value is not None and abs(old - value) > 1e-9:
            pct = abs(value - old) / max(abs(old), 1e-9)
            return f"SOURCE_CHANGE WARNING Valor anterior {old} substituido por {value} ({pct:.1%})"
        return None

    def load_demo_csv(self, csv_path: Path | None = None) -> int:
        csv_path = csv_path or (BASE / "data" / "demo_metrics.csv")
        n = 0
        with self.connect() as con:
            with open(csv_path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    sid = f"DEMO|{row['company']}|{row['period']}|{row['source_doc']}"
                    self.upsert_source(con, sid, row["company"], row["source_doc"], row.get("source_url", ""),
                                       "", "", True, "UNKNOWN")
                    try:
                        val = float(row["value"]) if row["value"] not in ("", None) else None
                    except ValueError:
                        val = None
                    self.insert_observation(con, row["company"], row["period"], row["indicator"], val,
                                            row.get("currency", "USD") or "USD", row.get("unit", "USD_M") or "USD_M",
                                            sid, float(row.get("confidence", 0.6) or 0.6),
                                            row.get("evidence", ""), "DEMO_CSV", True)
                    n += 1
        return n

    # ---- leitura p/ dashboard ----
    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.connect() as con:
            return [dict(r) for r in con.execute(sql, params).fetchall()]

    def pivot(self, period: str) -> list[dict]:
        return self.query("""SELECT o.company_id, o.indicator_id, o.value, o.unit, o.confidence, o.evidence
                             FROM metric_current o WHERE o.period_id=?""", (period,))

    def history(self, company: str, indicator: str) -> list[dict]:
        return self.query("""SELECT period_id, value FROM metric_current
                             WHERE company_id=? AND indicator_id=? ORDER BY period_id""", (company, indicator))

    def quality_issues(self, limit: int = 200) -> list[dict]:
        return self.query("SELECT * FROM quality_issue ORDER BY created_at DESC LIMIT ?", (limit,))

    def add_quality_issue(self, rule: str, severity: str, message: str, company: str = "",
                          period: str = "", indicator: str = "", value=None, prev=None,
                          _con: sqlite3.Connection | None = None) -> None:
        sql = """INSERT INTO quality_issue
                 (company_id, period_id, indicator_id, rule, severity, message, value, previous_value)
                 VALUES (?,?,?,?,?,?,?,?)"""
        params = (company, period, indicator, rule, severity, message[:800], value, prev)
        if _con is not None:
            _con.execute(sql, params)
            return
        with self.connect() as con:
            con.execute(sql, params)
