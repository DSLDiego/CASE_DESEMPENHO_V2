"""Bootstrap: cria schema + carga demo + garante pastas."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.repositories.sqlite_repo import SQLiteRepository

if __name__ == "__main__":
    repo = SQLiteRepository()
    repo.init_schema()
    n = repo.load_demo_csv()
    print(f"OK schema + {n} obs demo -> {repo.db_path}")
