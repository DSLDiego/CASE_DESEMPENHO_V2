"""Mapeia fontes na internet e lista sites + documentos (JSON + CSV + MD).

Uso: python scripts/map_sources.py [--no-extra]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.etl import mapping as M
from src.services.source_registry import SourceRegistry


def main() -> int:
    extras = [] if "--no-extra" in sys.argv else M.EXTRAS
    mp = M.run_mapping(SourceRegistry(), extras)
    arts = M.save_artifacts(mp)
    for s in mp["sources"]:
        print(f"[{s['source_id']}] {s['total']} docs @ {s['site']}"
              + (f" | erros: {'; '.join(s['errors'])}" if s["errors"] else ""))
    print("totais:", mp["totals"])
    print("artefatos:", arts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
