"""Verifica o ambiente do projeto antes de rodar: Python + bibliotecas.

Uso:
  python check_env.py           # só verifica (sem instalar)
  python check_env.py --instalar  # instala o que faltar

A lista de bibliotecas vem do requirements.txt do próprio projeto — nenhuma
duplo catálogo para divergir. Se faltar alguma, o ETL inteiro sofre (pdfl,
openpyxl, pandas...), então a checagem fica na porta do ETL.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# mapeia "entidade de import" para o nome pip (nem sempre é igual ao --pip name)
_IMPORT_PIPAME = {
    "pymupdf": "pymupdf",
    "pdfplumber": "pdfplumber",
    "pdf_oxide": "pdf_oxide",
    "docx": "python-docx",
    "openpyxl": "openpyxl",
    "PySide6": "PySide6",
    "pyqtgraph": "pyqtgraph",
    "pptx": "python-pptx",
    "PIL": "pillow",
    "plotly": "plotly",
    "kaleido": "kaleido",
    "reportlab": "reportlab",
    "requests": "requests",
    "pandas": "pandas",
    "pytest": "pytest",
}

# requisitos que NÃO são pip-importaveis de forma trivial (navegador, etc.)
_NAO_IMPORT = {"kaleido": "kaleido"}  # import check trivial; chromium é outro item

_REQS = Path(__file__).with_name("requirements.txt")


def _libs_do_requirements() -> list[tuple[str, str]]:
    """(nome_pip, nome_import) de cada linha não-comentada."""
    libs: list[tuple[str, str]] = []
    for linha in _REQS.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or linha.startswith("-"):
            continue
        # remove ambiente extras, versões, comentarios
        nome = (linha.split("#")[0].split(">=")[0].split("<=")[0]
                .split("==")[0].split(";")[0].split("[")[0].strip())
        if not nome:
            continue
        # nome de import: quase sempre o próprio, com exceções conhecidas
        imp = {"python-docx": "docx", "python-pptx": "pptx", "pillow": "PIL",
               "pymupdf": "fitz", "pdf_oxide": "pdf_oxide",
               "python-pptx": "pptx", "pillow": "PIL"}.get(nome, nome)
        libs.append((nome, imp))
    return libs


def verificar_python() -> tuple[bool, str]:
    """True se a versão é >= 3.10 (o código usa | de tipos e outros 3.10+)."""
    v = sys.version_info
    ok = v >= (3, 10)
    return ok, f"{v.major}.{v.minor}.{v.micro}"


def verificar_bibliotecas() -> list[tuple[str, str, bool]]:
    """(nome_pip, import, presente) para cada lib do requirements."""
    resultado = []
    for pip_nome, imp in _libs_do_requirements():
        try:
            __import__(imp)
            resultado.append((pip_nome, imp, True))
        except ImportError:
            resultado.append((pip_nome, imp, False))
    return resultado


def instalar(pip_nomes: list[str]) -> bool:
    if not pip_nomes:
        return True
    print(f"\nInstalando {len(pip_nomes)} pacote(s): {', '.join(pip_nomes)}")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", *pip_nomes],
                       check=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"FALHA na instalação (código {exc.returncode}).")
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Verifica o ambiente (Python + libs do projeto)")
    ap.add_argument("--instalar", action="store_true",
                    help="instala as bibliotecas ausentes via pip")
    args = ap.parse_args()

    print("== Verificação do ambiente ==\n")

    # --- 1. Python ---
    ok_py, versao = verificar_python()
    print(f"Python: {sys.executable}")
    print(f"Versão: {versao} {'OK (>= 3.10)' if ok_py else 'INSUFICIENTE (exige >= 3.10)'}")
    if not ok_py:
        print("\nAtualize o Python em https://www.python.org/downloads/ e reinstale.")
        return 1

    # --- 2. Bibliotecas ---
    libs = verificar_bibliotecas()
    faltantes = [pip for pip, _, presente in libs if not presente]
    print(f"\nBibliotecas do requirements.txt: {len(libs)} conferidas")
    for pip, imp, presente in libs:
        marca = "OK" if presente else "AUSENTE"
        print(f"  [{marca:<6}] {pip:<16} (import: {imp})")
    if not faltantes:
        print("\nTudo certo! Ambiente pronto para rodar o ETL.")
        return 0

    print(f"\nFaltando: {len(faltantes)} -> {', '.join(faltantes)}")
    if args.instalar:
        if instalar(faltantes):
            print("\nReinstale e rode de novo: python check_env.py")
            return 0
        return 1
    print("\nPara instalar: python check_env.py --instalar")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())