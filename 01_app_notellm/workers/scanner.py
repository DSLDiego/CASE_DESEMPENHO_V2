"""Workers: varredura do Container (coleta local idempotente via SHA-256)."""
from __future__ import annotations

import re
from pathlib import Path

import config
from config import COMPANIES, CONTAINER_DIR
from models.repositories import FonteRepository, sha256_file

EXT_TIPO = {".pdf": "PDF", ".xlsx": "XLSX", ".xls": "XLS", ".xlsm": "XLSM",
            ".csv": "CSV", ".txt": "TXT", ".docx": "DOCX", ".json": "JSON",
            ".htm": "HTML", ".html": "HTML"}

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


# Marcas de "cópia" no nome: quando dois arquivos têm o MESMO conteúdo, o
# catálogo deve ficar com o nome mais descritivo, não com a cópia.
MARCA_COPIA = re.compile(r"\(\d+\)|^\s*[_~]|copy|copia|cópia|duplic|untitled|"
                         r"novo|new|teste|test|\bbackup\b|\bbak\b", re.IGNORECASE)


def score_nome(path: Path) -> tuple[int, int, int]:
    """Ranking do arquivo a manter quando o conteúdo é idêntico (maior vence).

    A penalidade entra **negativa** porque o vencedor é escolhido com `max`: se
    ficasse positiva, "cópia" (1) ganharia de "original" (0) na primeira chave.
    """
    nome = path.name
    penalidade = -1 if MARCA_COPIA.search(nome) else 0
    # nome mais longo = mais descritivo; caminho mais curto = mais canônico
    return (penalidade, len(nome.strip()), -len(path.parts))


def melhor_arquivo(arquivos: list[Path]) -> Path:
    return max(arquivos, key=score_nome)


def scan_container(repo: FonteRepository | None = None,
                   raiz: Path | None = None,
                   novos_ids: set[int] | None = None,
                   incluir_downloads: bool = True) -> dict[str, int]:
    """Registra todos os arquivos do Container; agrupa duplicados por hash.

    Quando dois arquivos têm o mesmo conteúdo (ex.: "DF 1T26.pdf" e
    "DF 1T26 (1).pdf"), registra só o de nome **mais descritivo** — no Windows a
    ordenação de Path ignora maiúsculas, então sem isso a cópia podia ser a
    escolhida e a proveniência ficava com nome pior.
    Com `incluir_downloads`, varre também `data/downloads/<EMPRESA>/`, onde a
    descoberta (workers/discovery.py) deixa o que baixou da SEC: sem essa raiz o
    ciclo "descoberta -> download -> etl --novos" não fecha.
    Se `novos_ids` for informado, recebe os ids das fontes recem-descobertas
    (o padrao para o ETL incremental: processar so o que entrou no inventario).
    """
    repo = repo or FonteRepository()
    raiz = raiz or CONTAINER_DIR          # resolvido aqui: permite override/testes
    stats = {"novos": 0, "duplicados": 0, "erros": 0}
    if not raiz.exists():
        return {"novos": 0, "duplicados": 0, "erros": 0, "aviso": f"pasta ausente: {raiz}"}

    raizes = [raiz]
    downloads = config.DOWNLOADS_DIR
    if (incluir_downloads and downloads.exists()
            and str(downloads).lower() != str(raiz).lower()):
        raizes.append(downloads)

    grupos: dict[str, list[Path]] = {}
    for base in raizes:
        for arquivo in sorted(base.rglob("*")):
            if not arquivo.is_file():
                continue
            if EXT_TIPO.get(arquivo.suffix.lower()) is None:
                continue
            try:
                digest = sha256_file(arquivo)
            except OSError:
                stats["erros"] += 1
                continue
            # dedup entre as duas raizes: o mesmo arquivo aparece so uma vez
            grupos.setdefault(digest, []).append(arquivo)

    for digest, arquivos in grupos.items():
        stats["duplicados"] += len(arquivos) - 1
        if repo.existe_hash(digest):
            continue                      # ja estava no catalogo
        arquivo = melhor_arquivo(arquivos)
        try:
            empresa = empresa_do_caminho(arquivo)
            cik = COMPANIES.get(empresa, {}).get("cik")
            novo_id = repo.registrar(nome_empresa=empresa, url=RI_URLS.get(empresa, ""),
                                     tipo=EXT_TIPO[arquivo.suffix.lower()],
                                     caminho=str(arquivo), cik=cik, status="CATALOGADO")
            if novos_ids is not None and novo_id is not None:
                novos_ids.add(int(novo_id))
            stats["novos"] += 1
        except OSError:
            stats["erros"] += 1
    return stats
