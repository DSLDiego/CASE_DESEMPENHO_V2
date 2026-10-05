"""Coleta web: download de URLs p/ data/raw/<empresa>/<periodo> (idempotente)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.services.app_services import CollectionService

if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 3:
        print("uso: python scripts/collect_web.py EMPRESA PERIODO URL [URL...]")
        sys.exit(2)
    company, period, *urls = args
    for r in CollectionService().download_urls(urls, company, period):
        print(r)
