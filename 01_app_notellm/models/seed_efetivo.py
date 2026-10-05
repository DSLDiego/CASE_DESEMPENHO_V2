"""Seed de ancoras anuais de EFETIVO_TOTAL (fontes publicas oficiales).

Contexto: os materiais trimestrais do Container nao trazem headcount por
trimestre; a serie trimestral permanece ausente (fila de revisao). Estas
ancoras anuais dao comparabilidade minima ao indicador obrigatorio, com
proveniencia total (URL registrada em tb_fonte_dados).
"""
from __future__ import annotations

ANCORAS: list[dict[str, str | int]] = [
    {"empresa": "PETROBRAS", "periodo": "2024A", "valor": 49000,
     "fonte_nome": "Petrobras Form 20-F 2024 (SEC)",
     "fonte_url": "https://www.sec.gov/Archives/edgar/data/1119639/000129281425001352/pbrform20f_2024.htm"},
    {"empresa": "SHELL", "periodo": "2024A", "valor": 96000,
     "fonte_nome": "Shell Annual Report 2024 (96k; 2023: 103k)",
     "fonte_url": "https://www.shell.no/media/reports/shell-annual-report-2024.pdf"},
    {"empresa": "BP", "periodo": "2024A", "valor": 100500,
     "fonte_nome": "bp Annual Report and Form 20-F 2024",
     "fonte_url": "https://cdn.prod.nntech.io/company-events/reports/5e65aa6b-62fd-3f00-bce9-4828e161bf24/report.pdf"},
    {"empresa": "CHEVRON", "periodo": "2024A", "valor": 45298,
     "fonte_nome": "Chevron Annual Report Supplement 2024",
     "fonte_url": "https://www.chevron.com/-/media/shared-media/documents/2024-chevron-annual-report-supplement.pdf"},
    {"empresa": "CHEVRON", "periodo": "2025A", "valor": 43039,
     "fonte_nome": "Chevron Annual Report Supplement 2025",
     "fonte_url": "https://www.chevron.com/-/media/shared-media/documents/2025-chevron-annual-report-supplement.pdf"},
    {"empresa": "EXXONMOBIL", "periodo": "2024A", "valor": 61000,
     "fonte_nome": "ExxonMobil 10-K 2024 (regular employees)",
     "fonte_url": "https://investor.exxonmobil.com/sec-filings/annual-reports/content/0001193125-25-073990/0001193125-25-073990.pdf"},
    {"empresa": "TOTALENERGIES", "periodo": "2024A", "valor": 102887,
     "fonte_nome": "TotalEnergies URD 2024",
     "fonte_url": "https://totalenergies.com/system/files/documents/totalenergies_universal-registration-document-2025_2026_en.pdf"},
    {"empresa": "TOTALENERGIES", "periodo": "2025A", "valor": 101513,
     "fonte_nome": "TotalEnergies URD 2025",
     "fonte_url": "https://totalenergies.com/system/files/documents/totalenergies_universal-registration-document-2025_2026_en.pdf"},
    {"empresa": "EQUINOR", "periodo": "2024A", "valor": 25000,
     "fonte_nome": "Equinor Annual Report 2024 (~25k)",
     "fonte_url": "https://www.equinor.com/investors/annual-report-2024"},
]


def aplicar(db=None) -> int:
    """Registra fontes + carrega fatos operacionais. Idempotente. Retorna cargas."""
    from config import COMPANIES
    from models.database import DatabaseManager
    from models.repositories import FatoRepository, FonteRepository
    db = db or DatabaseManager()
    fontes, fatos = FonteRepository(db), FatoRepository(db)
    cargas = 0
    for ancora in ANCORAS:
        empresa = str(ancora["empresa"])
        cik = COMPANIES.get(empresa, {}).get("cik")
        id_fonte = fontes.registrar(nome_empresa=empresa, url=str(ancora["fonte_url"]),
                                    tipo="DOC", caminho=None, cik=cik, status="PROCESSADO")
        fatos.upsert_operacional(empresa, str(ancora["periodo"]), "EFETIVO_TOTAL",
                                 float(ancora["valor"]), "pessoas", id_fonte)
        cargas += 1
    fontes.exportar()
    return cargas
