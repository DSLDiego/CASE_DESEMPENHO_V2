"""Importa CSV padrao (mesmo layout de data/import_template.csv)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.services.app_services import BatchETLService

if __name__ == "__main__":
    f = sys.argv[1] if len(sys.argv) > 1 else "data/import_template.csv"
    print(f"importadas: {BatchETLService().import_csv(f)}")
