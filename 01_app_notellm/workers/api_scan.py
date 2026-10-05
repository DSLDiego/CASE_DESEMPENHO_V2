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
