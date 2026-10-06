"""M9.13 — render de JS para portais de RI (Chevron/BP/Equinor/Petrobras).

Três portais de RI carregam a parte útil da página em JavaScript; uma requisição
HTTP pura devolve o esqueleto vazio e o coletor conclui (erroneamente) que o
arquivo está ausente. Aqui tratamos o render como um worker opcional: só ativa
quando o `playwright` (pip install playwright + browsers) está presente, com
queda clara para o caminho sem JS — e aviso explícito quando não está.
"""
from __future__ import annotations

from typing import Any

from config import USER_AGENT


def playwright_disponivel() -> bool:
    try:
        __import__("playwright")
        return True
    except ImportError:
        return False


def fetch_renderizado(url: str, wait_ms: int = 4000) -> str:
    """Baixa a página JÁ renderizada; levanta erro claro se não puder.

    O chamador escolhe: quando a página é HTML e o fetch puro não acha os
    números, chamar isso aqui. Sem o playwright instalado, levantar aqui é o
    comportamento honesto — fingir que buscou e agiu em cima de HTML vazio
    devolvia "página em branco" mais adiante e mascarava o problema.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright ausente: `pip install playwright` + `playwright install chromium` "
            "para renderizar os portais de RI (M9.13)") from exc
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(wait_ms)
            return page.content()
        finally:
            browser.close()


def diff_render(html_bruto: str, html_renderizado: str) -> dict[str, Any]:
    """Quanto a renderização mudou a página: se é como se a página fosse estática
    mas não é, o HTML muda muito (JS despejou dados na página)."""
    from html.parser import HTMLParser

    class _T(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tabelas = 0
            self.texto: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag == "table":
                self.tabelas += 1

        def handle_data(self, data):
            t = data.strip()
            if t:
                self.texto.append(t)

    def _meta(html: str) -> tuple[int, int]:
        p = _T()
        try:
            p.feed(html)
        except Exception:  # noqa: BLE001
            return 0, 0
        return p.tabelas, len(" ".join(p.texto))

    t1, w1 = _meta(html_bruto)
    t2, w2 = _meta(html_renderizado)
    ganho = (w2 - w1) / max(w1, 1)
    return {"tabelas_antes": t1, "tabelas_depois": t2,
            "palavras_antes": w1, "palavras_depois": w2,
            "cresceu_pct": round(ganho * 100, 1),
            "precisa_js": ganho > 0.5 or (t2 > t1 and w2 > 1.3 * max(w1, 10))}
