"""Workers: varredura do Container (coleta local idempotente via SHA-256)."""
from __future__ import annotations

from pathlib import Path

from config import COMPANIES, CONTAINER_DIR
from models.repositories import FonteRepository, sha256_file

EXT_TIPO = {".pdf": "PDF", ".xlsx": "XLSX", ".xls": "XLS", ".xlsm": "XLSM",
            ".csv": "CSV", ".txt": "TXT", ".docx": "DOCX", ".json": "JSON"}

RI_URLS = {
    "PETROBRAS": "https://www.investidorpetrobras.com.br/resultados-e-comunicados/relatorios-trimestrais/",
    "SHELL": "https://www.shell.com/investors/results-and-reporting/quarterly-results.html",
    "BP": "https://www.bp.com/en/global/corporate/investors/results-and-reporting/quarterly-results.html",
    "CHEVRON": "https://www.chevron.com/investors/financial-information/quarterly-results",
    "EXXONMOBIL": "https://corporate.exxonmobil.com/investors/investor-resources/quarterly-earnings",
    "TOTALENERGIES": "https://totalenergies.com/investors/results",
    "EQUINOR": "https://www.equinor.com/investors/quarterly-results",
}


def empresa_do_caminho(path: Path) -> str:
    for empresa in COMPANIES:
        if empresa in (p.upper() for p in path.parts):
            return empresa
    return "DESCONHECIDA"


def scan_container(repo: FonteRepository | None = None,
                   raiz: Path = CONTAINER_DIR) -> dict[str, int]:
    """Registra todos os arquivos do Container; pula duplicados por hash."""
    repo = repo or FonteRepository()
    stats = {"novos": 0, "duplicados": 0, "erros": 0}
    if not raiz.exists():
        return {"novos": 0, "duplicados": 0, "erros": 0, "aviso": f"pasta ausente: {raiz}"}
    for arquivo in sorted(raiz.rglob("*")):
        if not arquivo.is_file():
            continue
        tipo = EXT_TIPO.get(arquivo.suffix.lower())
        if not tipo:
            continue
        try:
            digest = sha256_file(arquivo)
            if repo.existe_hash(digest):
                stats["duplicados"] += 1
                continue
            empresa = empresa_do_caminho(arquivo)
            cik = COMPANIES.get(empresa, {}).get("cik")
            repo.registrar(nome_empresa=empresa, url=RI_URLS.get(empresa, ""),
                           tipo=tipo, caminho=str(arquivo), cik=cik, status="CATALOGADO")
            stats["novos"] += 1
        except OSError:
            stats["erros"] += 1
    return stats
