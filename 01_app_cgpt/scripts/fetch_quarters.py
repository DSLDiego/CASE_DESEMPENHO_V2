"""Baixa PDFs de teste: melhores por trimestre p/ 2023-2026 (via PdfHandler).

Uso: python scripts/fetch_quarters.py [--years 2023,2024,2025,2026] [--per-year 4] [--company TOTALENERGIES]
Destino: data/raw/<COMPANY>/QUARTERTEST/
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.etl.formats import dispatch as D
from src.services.source_registry import SourceRegistry
import csv


def pick(map_csv: str, company: str, years: list[int], per_year: int) -> list[dict]:
    rows = [r for r in csv.DictReader(open(map_csv, encoding="utf-8"))
            if r["ext"] == ".pdf" and r["company"] == company]
    def yq(r):
        import re
        m = re.match(r"([1-4])T(\d{4})", r.get("periodo", ""))
        return (int(m.group(2)), int(m.group(1))) if m else None
    by_q: dict[tuple, list] = {}
    for r in rows:
        k = yq(r)
        if k and k[0] in years:
            by_q.setdefault(k, []).append(r)
    pref = ("press-release", "results")
    chosen = []
    for (y, _), rs in sorted(by_q.items()):
        rs.sort(key=lambda r: (any(p in r["url"] for p in pref), int(r.get("score") or 0)), reverse=True)
        chosen.append(rs[0])
    # limita por ano mantendo ordem cronologica
    out = []
    for y in years:
        out += [c for c in chosen if yq(c)[0] == y][:per_year]
    return out


def main() -> int:
    years, per_year, company = [2023, 2024, 2025, 2026], 4, "TOTALENERGIES"
    for i, t in enumerate(sys.argv):
        if t == "--years":
            years = [int(y) for y in sys.argv[i + 1].split(",")]
        if t == "--per-year":
            per_year = int(sys.argv[i + 1])
        if t == "--company":
            company = sys.argv[i + 1].upper()
    reg = SourceRegistry()
    dest = Path("data/raw") / company / "QUARTERTEST"
    ok, fail = 0, []
    for r in pick("data/source_map.csv", company, years, per_year):
        try:
            cf = D.collect_one(r["url"], dest, reg, r["source_id"], "", company)
            print(f"OK [{cf.meta.get('pages_detected')}p/{cf.meta.get('profile')}] {r['periodo']} {cf.local_path}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append((r["url"], str(e)[:120]))
            print("FAIL", r["url"][:90], str(e)[:120])
    print(f"{ok} baixados, {len(fail)} falhas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
