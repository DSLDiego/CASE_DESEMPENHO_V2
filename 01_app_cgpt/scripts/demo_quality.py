"""Demonstra controle SOURCE_CHANGE: 10 -> 20 gera WARNING com %."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.repositories.sqlite_repo import SQLiteRepository

if __name__ == "__main__":
    import tempfile
    tmp = Path(tempfile.mkdtemp()) / "demo_q.sqlite"
    repo = SQLiteRepository(tmp)
    repo.init_schema()
    with repo.connect() as con:
        repo.upsert_source(con, "DEMO_Q", "SHELL", "demo", "", "", "", True)
        repo.insert_observation(con, "SHELL", "2T2026", "REVENUE", 10.0, "USD", "USD_M",
                                "DEMO_Q", 0.9, "demo", "demo", True)
        msg = repo.insert_observation(con, "SHELL", "2T2026", "REVENUE", 20.0, "USD", "USD_M",
                                      "DEMO_Q", 0.9, "demo revisado", "demo", True)
        if msg:
            repo.add_quality_issue("SOURCE_CHANGE", "WARNING", msg, "SHELL", "2T2026", "REVENUE", 20.0, 10.0,
                                   _con=con)
        print(msg or "sem mudanca")
