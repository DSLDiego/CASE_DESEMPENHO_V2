"""Renderiza slides do PPTX em PNG, para conferir layout de verdade.

python-pptx não renderiza: ele só escreve o XML. Quem mostra se o texto estourou,
se a tabela coureu ou se o contraste funciona é o PowerPoint — e aqui não há
PowerPoint. Com PowerPoint ou LibreOffice instalado, converte e olha o PNG.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SOFFICE = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "soffice",
]
PDFS = [
    r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16\POWERPNT.EXE",
]


def disponivel() -> str | None:
    """Caminho do conversor, ou None se não houver PowerPoint/LibreOffice."""
    for caminho in SOFFICE + PDFS:
        achado = shutil.which(caminho) or (caminho if Path(caminho).exists() else None)
        if achado:
            return achado
    return None


def converter(pptx: Path, saida: Path) -> int:
    """PPTX -> PDF. Devolve o código de saída do conversor."""
    saida.mkdir(parents=True, exist_ok=True)
    exe = disponivel()
    if exe is None:
        print("sem PowerPoint/LibreOffice para renderizar — "
              "confie no validador estrutural (workers/validar_pptx.py)")
        return 2
    cmd = ([exe, "--headless", "--convert-to", "pdf", "--outdir", str(saida), str(pptx)]
           if "soffice" in exe.lower() or exe.lower().endswith("soffice.exe")
           else ["/S", "/M", "macro-less-open", str(pptx)])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    print(proc.stdout.strip() or proc.stderr.strip() or "(sem saída)")
    return proc.returncode


def main() -> int:
    pptx = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/APRESENTACAO_PETROBRAS.pptx")
    return converter(pptx, Path("docs/_preview_pptx"))


if __name__ == "__main__":
    raise SystemExit(main())