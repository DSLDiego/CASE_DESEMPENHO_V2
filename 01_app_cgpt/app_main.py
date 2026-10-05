"""app_main.py — ponto de entrada da PoC v0 (GUI PySide6 + CLI fallback).

Uso:
  python app_main.py                 -> abre o painel (GUI)
  python app_main.py --cli status    -> resumo executivo no terminal
  python app_main.py --init          -> (re)cria banco + carga demo
  python app_main.py --import f.csv  -> importa CSV padrao
  python app_main.py --etl "pasta"   -> batch ETL sobre arquivos locais
  python app_main.py --test          -> roda testes embutidos
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from src.repositories.sqlite_repo import SQLiteRepository


def cmd_init() -> None:
    repo = SQLiteRepository()
    repo.init_schema()
    n = repo.load_demo_csv()
    print(f"[init] schema ok + {n} observacoes DEMO carregadas -> {repo.db_path}")


def cmd_status() -> None:
    from src.services.app_services import DashboardService
    svc = DashboardService()
    for per in svc.periods():
        data = svc.executive_view(per)
        print(f"\n== {per} ==")
        for comp, inds in data["table"].items():
            print(f"  {comp}: " + " | ".join(f"{k}={v}" for k, v in inds.items()))
        print("  " + data["narrative"])


def cmd_import(csv_path: str) -> None:
    from src.services.app_services import BatchETLService
    n = BatchETLService().import_csv(csv_path)
    print(f"[import] {n} observacoes de {csv_path}")


def cmd_etl(folder: str, mode="PROCESS", batch="10", scheduler="FIFO", workers=8) -> None:
    from src.services.app_services import BatchETLService
    exts = {".pdf", ".xlsx", ".xlsm", ".xls", ".csv", ".doc", ".docx", ".txt", ".html"}
    files = [str(p) for p in Path(folder).rglob("*") if p.suffix.lower() in exts]
    print(f"[etl] {len(files)} arquivo(s) mode={mode} batch={batch} sched={scheduler} workers={workers}")

    def prog(res, done, total):
        print(f"  [{done}/{total}] {Path(res.path).name} ok={res.ok} {res.elapsed_ms}ms n={len(res.extractions)} {res.error[:100]}")

    b = batch if batch == "Auto" else int(batch)
    out = BatchETLService().run(files, mode, b, scheduler, workers, prog)
    print(f"[etl] {out['ok']}/{out['total']} OK em {out['elapsed_s']}s run={out['run_id']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Benchmarking financeiro trimestral — PoC v0")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--cli", choices=["status"], help="modo terminal")
    ap.add_argument("--import", dest="imp", help="importar CSV padrao")
    ap.add_argument("--etl", help="pasta p/ batch ETL")
    ap.add_argument("--mode", default="PROCESS")
    ap.add_argument("--batch", default="10")
    ap.add_argument("--scheduler", default="FIFO")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args(argv)

    repo = SQLiteRepository()
    if not repo.db_path.exists():
        repo.init_schema()
        repo.load_demo_csv()

    if args.init:
        cmd_init()
        return 0
    if args.cli == "status":
        cmd_status()
        return 0
    if args.imp:
        cmd_import(args.imp)
        return 0
    if args.etl:
        cmd_etl(args.etl, args.mode, args.batch, args.scheduler, args.workers)
        return 0
    if args.test:
        import pytest
        return pytest.main(["-q", "tests"])
    # GUI
    try:
        from src.views.main_window import run_gui
        return run_gui()
    except Exception as e:  # fallback CLI (sem display / sem PySide6)
        print(f"[gui indisponivel: {e}] caindo para CLI --status")
        cmd_status()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
