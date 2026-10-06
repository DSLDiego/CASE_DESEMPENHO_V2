"""Worker coleta web: portais de RI + Investidor10 (descoberta, download, snapshot).

Fontes oficiais (RI) e agregador publico (Investidor10). Toda informacao carrega
proveniencia (URL + data) registrada em tb_fonte_dados.
"""
from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
from datetime import date
from html.parser import HTMLParser

from config import COMPANIES, DOWNLOADS_DIR, USER_AGENT
from models.repositories import FonteRepository, sha256_file

RI_SITES: dict[str, str] = {
    "EQUINOR": "https://www.equinor.com/investors/quarterly-results",
    "PETROBRAS": "https://www.investidorpetrobras.com.br/resultados-e-comunicados/central-de-resultados/",
    "SHELL": "https://www.shell.com/investors/results-and-reporting/quarterly-results.html",
    "TOTALENERGIES": "https://totalenergies.com/investors/results",
    "BP": "https://www.bp.com/investors/results-reporting-and-presentations/archive-of-results-reports-and-presentations/2026",
    "EXXONMOBIL": "https://investor.exxonmobil.com/earnings/financial-results",
    "CHEVRON": "https://www.chevron.com/investors/",
}

I10_SITES: dict[str, str] = {
    "CHEVRON": "https://investidor10.com.br/stocks/cvx/",
    "EQUINOR": "https://investidor10.com.br/stocks/eqnr/",
    "EXXONMOBIL": "https://investidor10.com.br/stocks/xom/",
    "PETROBRAS": "https://investidor10.com.br/stocks/pbr/",
    "BP": "https://investidor10.com.br/stocks/bp/",
    "TOTALENERGIES": "https://investidor10.com.br/stocks/tte/",
    "SHELL": "https://investidor10.com.br/stocks/shel/",
}

DOC_EXTS = (".pdf", ".xlsx", ".xlsm", ".xls", ".csv")
_LAST = 0.0

MAGIC = {".pdf": (b"%pdf",), ".xlsx": (b"pk\x03\x04",), ".xlsm": (b"pk\x03\x04",),
         ".xls": (b"\xd0\xcf\x11\xe0",), ".csv": None}  # minusculas: head e lower() antes de comparar
HTML_START = (b"<!doctype", b"<html", b"<head")


def validar_conteudo(caminho, ext: str) -> str:
    """Checa magic bytes: 'OK', 'HTML_REJEITADO' (login/erro) ou 'TIPO_DUVIDOSO'."""
    with open(caminho, "rb") as fh:
        head = fh.read(16).lstrip().lower()
    if head.startswith(HTML_START):
        return "HTML_REJEITADO"
    assinaturas = MAGIC.get(ext.lower())
    if assinaturas is None:
        return "OK"
    return "OK" if head.startswith(assinaturas) else "TIPO_DUVIDOSO"


def canonical_url(url: str) -> str:
    """Identidade canonica do documento: mesma URL com tracking diferente = igual."""
    parts = urllib.parse.urlsplit(url)
    qs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    qs = sorted((k, v) for k, v in qs if not k.lower().startswith(("utm_", "fbclid", "gclid")))
    netloc = parts.netloc.lower().rstrip(":80").rstrip(":443")
    return urllib.parse.urlunsplit((parts.scheme.lower(), netloc, parts.path.rstrip("/"),
                                    urllib.parse.urlencode(qs), ""))


def _abrir_com_retry(req: urllib.request.Request, timeout: int, tentativas: int = 3):
    ultimo_erro: Exception | None = None
    for tentativa in range(tentativas):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - rede instavel, tenta de novo
            ultimo_erro = exc
            time.sleep(2 ** tentativa)
    raise RuntimeError(f"falha apos {tentativas} tentativas: {ultimo_erro}")


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href:
                self.links.append((href, ""))

    def handle_data(self, data: str) -> None:
        if self.links and data.strip():
            href, _ = self.links[-1]
            self.links[-1] = (href, (self.links[-1][1] + " " + data.strip()).strip())


# Portais em que a página útil é desenhada por JS: a requisição pura devolve o
# esqueleto. Para esses, o render (playwright) é default; nos demais, o fetch puro.
_RI_JS_PESADO = {"CHEVRON", "BP", "PETROBRAS", "EQUINOR"}


def fetch_pagina_ri(empresa: str, fallback_sem_js: bool = True) -> tuple[str, str]:
    """Retorna (html_renderizado, modo) para o portal de RI da empresa.

    modo: 'playwright' | 'http' | 'http-fallback'.
    Em Chevron/BP/Petrobras/Equinor o HTML base chega vazio sem JS: tentamos
    renderizar; sem playwright instalado, cai para o download puro e avisa
    ('http-fallback') para o chamador já saber que a página pode vir em branco.
    """
    empresa = empresa.upper()
    url = RI_SITES.get(empresa)
    if not url:
        raise ValueError(f"empresa sem portal RI mapeado: {empresa}")
    if empresa in _RI_JS_PESADO:
        try:
            from workers.jsrender import fetch_renderizado
            return fetch_renderizado(url), "playwright"
        except RuntimeError:
            if not fallback_sem_js:
                raise
            return fetch(url), "http-fallback"
    return fetch(url), "http"


def fetch(url: str, timeout: int = 25) -> str:
    """Baixa HTML com throttle educado + User-Agent identificado."""
    global _LAST
    espera = 1.0 - (time.monotonic() - _LAST)
    if espera > 0:
        time.sleep(espera)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _abrir_com_retry(req, timeout) as resp:
        raw = resp.read()
    _LAST = time.monotonic()
    charset = "utf-8"
    try:
        ctype = resp.headers.get_content_charset()
        if ctype:
            charset = ctype
    except Exception:
        pass
    return raw.decode(charset, errors="ignore")


def discover_links(page_url: str, html: str | None = None) -> list[dict[str, str]]:
    """Extrai links de documentos (pdf/xlsx/...) de uma pagina, com URLs absolutas."""
    html = html if html is not None else fetch(page_url)
    parser = _Links()
    parser.feed(html)
    vistos, out = set(), []
    for href, texto in parser.links:
        abs_url = urllib.parse.urljoin(page_url, href.split("#")[0])
        low = abs_url.lower()
        if any(low.endswith(ext) for ext in DOC_EXTS) and abs_url not in vistos:
            vistos.add(abs_url)
            out.append({"titulo": texto[:120] or abs_url.rsplit("/", 1)[-1],
                        "url": abs_url,
                        "tipo": low.rsplit(".", 1)[-1].upper()})
    return out


def download_doc(url: str, empresa: str, repo: FonteRepository | None = None) -> dict:
    """Baixa um documento com dedup por SHA-256; registra a fonte. Retorna resumo."""
    repo = repo or FonteRepository()
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    nome = urllib.parse.unquote(url.rsplit("/", 1)[-1].split("?")[0]) or "documento"
    destino = DOWNLOADS_DIR / f"{empresa}_{nome}"
    if destino.exists():
        digest = sha256_file(destino)
        if repo.existe_hash(digest):
            return {"url": url, "status": "DUPLICADO", "caminho": str(destino)}
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _abrir_com_retry(req, 60) as resp, open(destino, "wb") as fh:
        while chunk := resp.read(65536):
            fh.write(chunk)
    ext = destino.suffix.lower()
    veredito = validar_conteudo(destino, ext)
    if veredito == "HTML_REJEITADO":
        destino.unlink(missing_ok=True)
        repo.registrar(empresa, url, "HTML", None, COMPANIES.get(empresa, {}).get("cik"), "AUTH_REQUIRED")
        return {"url": url, "status": "HTML_REJEITADO"}
    if veredito == "TIPO_DUVIDOSO":
        repo.registrar(empresa, url, destino.suffix.lstrip(".").upper() or "BIN",
                        str(destino), COMPANIES.get(empresa, {}).get("cik"), "REVISAR_TIPO")
        return {"url": url, "status": "TIPO_DUVIDOSO", "caminho": str(destino)}
    id_fonte = repo.registrar(empresa, url, destino.suffix.lstrip(".").upper() or "BIN",
                              str(destino), COMPANIES.get(empresa, {}).get("cik"), "DOWNLOADED")
    return {"url": url, "status": "DOWNLOADED", "caminho": str(destino), "id_fonte": id_fonte}


def _num_br(texto: str) -> float | None:
    try:
        return float(texto.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def parse_investidor10(html: str) -> dict[str, float]:
    """Snapshot de mercado via FAQ JSON-LD ('vale a pena?') — preciso e auditavel.

    Retorna chaves normalizadas; COTACAO leva sufixo da moeda na chave interna.
    Usa apenas a resposta avaliativa (cotada a X, P/L de Y, DY de Z%).
    """
    faq = re.search(r"vale a pena\?.*?acceptedAnswer.*?text.*?:\s*\"(.*?)\"\s*\}",
                    html, re.IGNORECASE | re.DOTALL)
    texto = re.sub(r"\s+", " ", faq.group(1)) if faq else re.sub(r"<[^>]+>", " ", html)
    out: dict[str, float] = {}
    num = r"(\d[\d.,]*\d|\d)"  # nunca termina em separador (',', '.')
    m = re.search(rf"cotada a\s+(US\$|R\$)\s*{num}", texto)
    if m:
        val = _num_br(m.group(2))
        if val:
            out["COTACAO"] = val
            out["_MOEDA"] = m.group(1)
    m = re.search(rf"P/L de\s*{num}", texto)
    if m and _num_br(m.group(1)) is not None:
        out["P/L"] = _num_br(m.group(1))
    m = re.search(rf"Dividend Yield.*?de\s*{num}%", texto)
    if m and _num_br(m.group(1)) is not None:
        out["DY"] = _num_br(m.group(1))
    return out


def trimestre_corrente(hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    return f"{hoje.year}Q{(hoje.month - 1) // 3 + 1}"


def collect_site(empresa: str, origem: str, baixar: bool = False,
                 repo: FonteRepository | None = None) -> dict:
    """Descobre documentos de um site (RI ou i10); baixa se pedido. Nunca quebra o pipeline."""
    repo = repo or FonteRepository()
    url = (RI_SITES if origem == "RI" else I10_SITES)[empresa]
    resumo: dict = {"empresa": empresa, "origem": origem, "url": url,
                    "links": [], "downloads": [], "snapshot": {}, "erro": None}
    try:
        links = discover_links(url)
    except Exception as exc:
        resumo["erro"] = f"{type(exc).__name__}: {exc}"
        return resumo
    resumo["links"] = links
    for item in links:
        try:
            fid = repo.registrar(empresa, item["url"], item["tipo"], None,
                                 COMPANIES.get(empresa, {}).get("cik"), "DESCOBERTO")
        except Exception:
            fid = None
        item["id_fonte"] = fid
        if baixar:
            try:
                resumo["downloads"].append(download_doc(item["url"], empresa, repo))
            except Exception as exc:
                resumo["downloads"].append({"url": item["url"], "status": f"ERRO: {exc}"})
    if origem == "I10":
        try:
            resumo["snapshot"] = parse_investidor10(fetch(url))
        except Exception as exc:
            resumo["erro"] = f"snapshot: {exc}"
    repo.exportar()
    return resumo
