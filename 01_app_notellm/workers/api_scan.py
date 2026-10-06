"""Worker: descobrir quais fontes publicas possuem API/servico JSON.

Requisito 1.2 do painel de gestao de fontes: "verificar se o site tem uma API ou
servico web publico para consumo de dados via JSON".

Estrategia (SRP, offline-safe):
- SEC EDGAR: endpoint publico `companyfacts` por CIK (fatos XBRL estruturados).
- Investidor10: dados estruturados embutidos na pagina (FAQ JSON-LD / __NEXT_DATA__).
- RI: sem API publica -> registra "SEM" (o consumo e por arquivo/parser).

O resultado e gravado em `tb_fonte_dados.api_json`, alimentando o CRUD e o catalogo.
"""
from __future__ import annotations

import time
from typing import Any

import requests

import config
from models.repositories import FonteRepository
from workers.sec_edgar import BASE

I10_STOCK_URL = "https://investidor10.com.br/stocks/{sigla}/"
CACHE_DIR = config.DATA_DIR / "api_scan_cache"


def _get_json(url: str, headers: dict[str, str] | None = None,
              timeout: int = 12) -> tuple[str, dict[str, Any] | None]:
    """Retorna (status, payload). Nunca levanta excecao de rede (Fluent Interface)."""
    try:
        resp = requests.get(url, headers=headers or {"User-Agent": config.USER_AGENT},
                            timeout=timeout)
    except requests.RequestException as exc:
        return f"ERRO_REDE:{type(exc).__name__}", None
    if resp.status_code != 200:
        return f"HTTP_{resp.status_code}", None
    try:
        return "OK", resp.json()
    except ValueError:
        return "SEM_JSON", None


# ------------------------------------------------- alerta de URL quebrada (M1.14)
# Chevron e BP devolvem 403 e Petrobras/Equinor usam página dinâmica: em ambos os
# casos a URL não está "errada", está INACESSÍVEL para automação. O alerta precisa
# distinguir as coisas, senão a recomendação ("corrigir o link") está errada.
HTTP_NAO_OK = (400, 401, 403, 404, 410, 451)
TENTATIVAS = 3
ESPERA_ENTRE_TENTATIVAS = 1.5     # segundos; 403/429 não melhoram com insistência


def _e_efemera(status: str) -> bool:
    """403/429 são bloqueios de bot: repetir não muda nada."""
    return status.startswith(("HTTP_403", "HTTP_429", "HTTP_401"))


def checar_url(url: str, tentativas: int = TENTATIVAS) -> dict[str, Any]:
    """Verifica se a URL da fonte ainda responde. Nunca levanta exceção de rede.

    403/429 não são retentados de propósito: são bloqueios de automação, e três
    requisições seguidas só transformam um bloqueio temporário em permanente.
    """
    if not (url or "").strip():
        return {"url": url, "ok": False, "status": "SEM_URL", "tentativas": 0,
                "diagnostico": "fonte sem URL de origem"}
    headers = {"User-Agent": config.USER_AGENT}
    ultima = {"status": "ERRO_REDE:desconhecido", "codigo": None, "tentativas": 0}
    for tentativa in range(1, max(1, tentativas) + 1):
        try:
            resp = requests.head(url, headers=headers, timeout=12, allow_redirects=True)
            codigo = resp.status_code
        except requests.RequestException as exc:
            ultima = {"status": f"ERRO_REDE:{type(exc).__name__}", "codigo": None,
                      "tentativas": tentativa}
        else:
            ultima = {"status": f"HTTP_{codigo}", "codigo": codigo, "tentativas": tentativa}
            if 200 <= codigo < 400:
                return {"url": url, "ok": True, "status": f"HTTP_{codigo}",
                        "codigo": codigo, "tentativas": tentativa,
                        "diagnostico": "responde"}
            if _e_efemera(ultima["status"]):
                return {**ultima, "url": url, "ok": False,
                        "diagnostico": ("bloqueio de automação (403/401/429): a URL pode "
                                         "existir, mas não responde a robô — não é link quebrado")}
        if tentativa < tentativas and not _e_efemera(ultima["status"]):
            time.sleep(ESPERA_ENTRE_TENTATIVAS)
    codigo = ultima["codigo"]
    if codigo in HTTP_NAO_OK:
        diag = (f"HTTP {codigo} — URL fora do ar ou inacessível"
                + (" (404/410: removida)" if codigo in (404, 410) else ""))
    else:
        diag = f"{ultima['status']} após {ultima['tentativas']} tentativa(s)"
    return {**ultima, "url": url, "ok": False, "diagnostico": diag}


def checar_fontes(repo: FonteRepository, limite: int | None = None) -> dict[str, Any]:
    """Varre o catálogo e devolve o que está quebrado, com o diagnóstico de cada."""
    quebradas: list[dict[str, Any]] = []
    checadas = 0
    for fonte in repo.listar():
        if limite and checadas >= limite:
            break
        url = fonte.get("url_fonte") or ""
        if not url.strip():
            continue
        checadas += 1
        r = checar_url(url)
        if r["ok"]:
            continue
        quebradas.append({"id_fonte": fonte["id_fonte"], "nome_empresa": fonte["nome_empresa"],
                          "url": url, "status": r["status"],
                          "diagnostico": r["diagnostico"],
                          "bloqueio": _e_efemera(r["status"])})
    return {"checadas": checadas, "quebradas": quebradas, "ok": not quebradas}


def probe_sec(cik: str) -> dict[str, Any]:
    url = BASE.format(cik=cik.zfill(10))
    status, payload = _get_json(url, headers={"User-Agent": config.USER_AGENT,
                                              "Accept": "application/json"})
    taxonomias = sorted((payload or {}).get("facts", {}).keys()) if payload else []
    return {"fonte": "SEC EDGAR", "url_json": url, "status": status,
            "detalhe": f"XBRL companyfacts · taxonomias={','.join(taxonomias) or '-'}",
            "json_publico": status == "OK"}


def probe_investidor10(sigla: str) -> dict[str, Any]:
    url = I10_STOCK_URL.format(sigla=sigla.lower())
    try:
        resp = requests.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=12)
        body = getattr(resp, "text", "") if resp.status_code == 200 else ""
    except requests.RequestException as exc:
        return {"fonte": "Investidor10", "url_json": url, "status": f"ERRO_REDE:{type(exc).__name__}",
                "detalhe": "sem acesso", "json_publico": False}
    tem_jsonld = '"@type":"QuestionAnswer"' in body or "application/ld+json" in body
    tem_next = "__NEXT_DATA__" in body or '"props"' in body
    status = "OK" if (tem_jsonld or tem_next) else "SEM_JSON"
    return {"fonte": "Investidor10", "url_json": url, "status": status,
            "detalhe": f"JSON-LD FAQ={tem_jsonld} · __NEXT_DATA__={tem_next}",
            "json_publico": status == "OK"}


def escanear(ciks: dict[str, str] | None = None, siglas_i10: dict[str, str] | None = None,
             repo: FonteRepository | None = None, timeout: int = 12) -> list[dict[str, Any]]:
    """Varre as fontes e persiste `api_json` (idempotente). Retorna o relatorio."""
    repo = repo or FonteRepository()
    repo.complementar_campos()
    ciks = {e: m["cik"] for e, m in config.COMPANIES.items()} if ciks is None else ciks
    siglas_i10 = ({e: m["codigo"] for e, m in config.COMPANIES.items()}
                  if siglas_i10 is None else siglas_i10)
    relatorio: list[dict[str, Any]] = []
    for empresa, cik in ciks.items():
        r = probe_sec(cik)
        r["nome_empresa"] = empresa
        relatorio.append(r)
    for empresa, sigla in siglas_i10.items():
        r = probe_investidor10(sigla)
        r["nome_empresa"] = empresa
        relatorio.append(r)
    for r in relatorio:
        marca = r["url_json"] if r["json_publico"] else f"SEM ({r['status']})"
        for fonte in repo.listar():
            if fonte["nome_empresa"] != r["nome_empresa"]:
                continue
            if (fonte.get("api_json") or "") != marca:
                repo.atualizar(fonte["id_fonte"], api_json=marca)
    return relatorio


def resumo(relatorio: list[dict[str, Any]]) -> str:
    com_api = [r for r in relatorio if r["json_publico"]]
    return (f"{len(com_api)}/{len(relatorio)} fontes com servico JSON publico: "
            + ", ".join(f"{r['nome_empresa']}={r['fonte']}" for r in com_api))
