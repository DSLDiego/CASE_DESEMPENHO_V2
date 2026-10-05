"""Rotina de novidades: verifica paginas de RI e baixa o que for novo.

Uso: python scripts/check_new.py [--download] [--min-score 50] [--id FONTE_ID]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.etl import source_check as SC
from src.services.source_registry import SourceRegistry


def main() -> int:
    do_dl = "--download" in sys.argv
    min_score = 50
    only = None
    for i, t in enumerate(sys.argv):
        if t == "--min-score":
            min_score = int(sys.argv[i + 1])
        if t == "--id":
            only = sys.argv[i + 1]
    reg = SourceRegistry()
    srcs = [reg.get(only)] if only else reg.list(only_active=True)
    total_new = 0
    for s in srcs:
        if s is None:
            print(f"fonte {only} nao encontrada")
            return 2
        rep = SC.check_source(s, reg)
        if not rep["ok"]:
            print(f"[{s['id']}] FALHA: {rep['error']}")
            continue
        print(f"[{s['id']}] {len(rep['new'])} novos / {rep['known']} ja conhecidos (total {rep['total']})")
        for c in rep["new"][:10]:
            print(f"   + [{c['score']}] {c['authority']} {c['title'][:60]} :: {c['url'][:90]}")
        total_new += len(rep["new"])
        if do_dl and rep["new"]:
            for r in SC.download_new(rep, reg, min_score=min_score):
                print(f"   {'OK ' if r['ok'] else 'FAIL'} {r['url'][:90]}")
    print(f"total novos: {total_new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
