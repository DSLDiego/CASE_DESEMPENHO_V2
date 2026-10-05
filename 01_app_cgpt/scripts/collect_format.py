"""Coleta pelo subsistema do formato (pdf/planilha/doc/txt).

Uso:
  python scripts/collect_format.py URL [--company C] [--source ID] [--out DIR]
  python scripts/collect_format.py --from-map [--ext .pdf] [--company X] [--limit N] [--min-score S]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.etl.formats import dispatch as D
from src.services.source_registry import SourceRegistry


def main() -> int:
    reg = SourceRegistry()
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 2
    if a[0] == "--from-map":
        kw = {}
        for i, t in enumerate(a):
            if t == "--ext":
                kw["ext_filter"] = a[i + 1]
            if t == "--company":
                kw["company"] = a[i + 1].upper()
            if t == "--limit":
                kw["limit"] = int(a[i + 1])
            if t == "--min-score":
                kw["min_score"] = int(a[i + 1])
        for r in D.collect_from_map("data/source_map.csv", "data/raw", reg, **kw):
            print(("OK " if r["ok"] else "FAIL"), r.get("handler", ""), r["url"][:90],
                  r.get("warnings") or r.get("error", ""))
        return 0
    url = a[0]
    company, sid, out = "", "", None
    for i, t in enumerate(a):
        if t == "--company":
            company = a[i + 1].upper()
        if t == "--source":
            sid = a[i + 1]
        if t == "--out":
            out = Path(a[i + 1])
    src = reg.get(sid) if sid else None
    dest = out or Path("data/raw") / (company or "INBOX") / "INBOX"
    cf = D.collect_one(url, dest, reg, sid, src["name"] if src else "", company)
    print(f"OK [{type(D.handler_for(url)).__name__}] {cf.local_path} sha={cf.sha256[:12]}")
    print("meta:", cf.meta)
    if cf.warnings:
        print("warnings:", cf.warnings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
