"""Screenshot das abas do painel (Chrome headless) para a entrega visual.

python-pptx não renderiza, e a pasta `1_PAINEL_E_IMAGENS` precisa de telas reais —
uma figura desenhada à mão seria exatamente o tipo de "print" que o projeto recusa
(ela好看ia, mas não provaria nada).

Requisito: o painel precisa estar SERVINDO (`app_main.py web --serve`) porque a aba
Gestão ETL, a Auditoria e a Qualidade carregam dados da API por `fetch` — no arquivo
estático elas ficariam vazias, e o print mostraria o produto quebrado.

O que precisa aparecer na tela (e por que precisa de --serve):
- **Gestão ETL**: KPIs e colunas de métrica de PDF vêm de /api/etl (M8.12);
- **Auditoria**: KPIs e a trilha de decisão vêm de /api/auditoria (M2);
- **Qualidade**: o histórico do DQS vem de /api/qualidade (M7.23).
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DOCS_DIR, WEB_HTML

DESTINO = DOCS_DIR / "ENTREGAVEIS" / "1_PAINEL_E_IMAGENS"
LARGURA, ALTURA = 1500, 1000
# chrome/edge headless; sem isso não há como provar que a tela abre
NAVEGADORES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# (indice da aba, nome do arquivo, altura da janela, [recorte de interes])
#
# A altura NÃO é uniforme de propósito: o conteúdo novo das três abas de governança
# (métrica de PDF no ETL, relatório de auditoria, evolução do DQS) está ABAIXO da
# dobra. Numa janela de 1000px o print sai certo e não mostra nada disso — a
# entrega profileria um produto sem as features que ela deveria provar.
#
# `recorte` é o pedaço vertical que interessa (topo_esq, altura). Sem ele fica a
# tela inteira; com ele, o recorte mostra o gráfico e a tabela da feature e larga
# a lista de 67 scorecards, que é ruído para a apresentação.
ABAS = [
    (0, "aba_00_visao_executiva", 1000, None),
    (1, "aba_01_comparacao", 1000, None),
    (2, "aba_02_expandidos", 1000, None),
    (3, "aba_03_evolucao_historica", 1000, None),
    (4, "aba_04_efetivo", 1000, None),
    (5, "aba_05_fontes_gestao", 1000, None),
    # métrica de PDF: a 2ª faixa de KPIs e as colunas Págs./Lidas/Tab./Pág-s
    (6, "aba_06_gestao_etl", 2050, (55, 720)),
    (7, "aba_07_auditoria", 1450, None),
    (8, "aba_08_projecoes", 1600, None),
    # evolução do DQS (M7.23): título, KPIs, gráfico e o começo da tabela
    (9, "aba_09_qualidade", 2350, (1090, 1000)),
    (10, "aba_10_glossario", 1000, None),
]


def navegador() -> str | None:
    for caminho in NAVEGADORES:
        achado = shutil.which(caminho) or (caminho if Path(caminho).exists() else None)
        if achado:
            return achado
    return None


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def esperar_servidor(rota: str, tentativas: int = 40) -> bool:
    """A API tem de responder antes do print: sem dado, sai tela vazia."""
    for _ in range(tentativas):
        try:
            with urllib.request.urlopen(rota, timeout=3) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


def capturar(exe: str, url: str, saida: Path, espera_ms: int, altura: int) -> bool:
    """`--headless --screenshot`: o Chrome renderiza e sai. Perfil temporário porque
    o perfil do usuário pode ter extensão/lock que impede o headless.

    `--hide-scrollbars` é obrigatório: com a barra visível, a coluna da direita da
    tabela some do print (o print some na largura da barra) e o print da auditoria
    entregaria uma coluna de status cortada sem ninguém perceber.
    """
    with tempfile.TemporaryDirectory() as perfil:
        cmd = [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
               f"--window-size={LARGURA},{altura}",
               f"--user-data-dir={perfil}",
               f"--virtual-time-budget={espera_ms}",
               "--no-first-run", "--no-default-browser-check",
               f"--screenshot={saida}", url]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    return saida.exists() and saida.stat().st_size > 5000


def main() -> int:
    exe = navegador()
    if exe is None:
        print("sem Chrome/Edge para screenshot — instale um dos dois")
        return 2
    porta = porta_livre()
    base = f"http://127.0.0.1:{porta}/"
    servidor = subprocess.Popen(
        [sys.executable, "app_main.py", "web", "--serve",
         "--porta", str(porta), "--sem-abrir"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not esperar_servidor(base + WEB_HTML.name):
            print("o servidor não respondeu — o painel não subiu")
            return 1
        if not esperar_servidor(base + "api/etl"):
            print("a API não respondeu: as abas de ETL/Auditoria/Qualidade sairiam vazias")
            return 1
        DESTINO.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WEB_HTML, DESTINO / WEB_HTML.name)
        feitas: list[str] = []
        for indice, nome, altura, recorte in ABAS:
            destino = DESTINO / f"{nome}.png"
            bruto = destino.with_name(f"_bruta_{nome}.png")
            # as abas dinâmicas (6,7,9) só pintam depois do fetch: 6 s de espera
            espera = 6500 if indice in (6, 7, 9) else 3000
            url = f"{base}{WEB_HTML.name}?tab={indice}"
            if capturar(exe, url, bruto, espera, altura):
                if recorte:
                    from PIL import Image
                    topo, alt = recorte
                    imagem = Image.open(bruto)
                    # recorte acima da altura real seria tela preta: o print
                    # pode ter saído menor que a janela pedida
                    alt = min(alt, imagem.height - topo)
                    imagem.crop((0, topo, imagem.width, topo + alt)).save(destino)
                    bruto.unlink()
                else:
                    bruto.replace(destino)
                feitas.append(nome)
                print(f"  {destino.name}  ({destino.stat().st_size // 1024} KB)")
            else:
                bruto.unlink(missing_ok=True)
                print(f"  ! falhou: {nome}")
    finally:
        servidor.terminate()
        try:
            servidor.wait(timeout=10)
        except subprocess.TimeoutExpired:      # pragma: no cover
            servidor.kill()
    print(json.dumps({"abas": feitas}, ensure_ascii=False))
    return 0 if len(feitas) == len(ABAS) else 1


if __name__ == "__main__":
    raise SystemExit(main())