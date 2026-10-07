"""Worker SEC EDGAR: coleta XBRL padronizado via CIK (fonte secundaria p/ cross-check).

Endpoints:
  https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json
Exige User-Agent valido; respeita rate-limit e timeout.
Cobre US-GAAP (10-Q/10-K) e IFRS (20-F/6-K). Periodo preferencial via `frame`
(CY####Q#); fallback via fy/fp.
"""
from __future__ import annotations

import re
import time
from typing import Any

import requests

import config
from workers.parse_tab import RawExtraction

BASE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

XBRL_MAP = [
    ("us-gaap", "Revenues", "RECEITA_LIQUIDA"),
    ("us-gaap", "SalesRevenueNet", "RECEITA_LIQUIDA"),
    ("us-gaap", "GrossProfit", "LUCRO_BRUTO"),
    ("us-gaap", "NetIncomeLoss", "LUCRO_LIQUIDO"),
    ("us-gaap", "NetCashProvidedByUsedInOperatingActivities", "FCO"),
    ("ifrs-full", "Revenue", "RECEITA_LIQUIDA"),
    ("ifrs-full", "GrossProfit", "LUCRO_BRUTO"),
    ("ifrs-full", "ProfitLoss", "LUCRO_LIQUIDO"),
    ("ifrs-full", "CashFlowsFromUsedInOperatingActivities", "FCO"),
]

FRAME_Q = re.compile(r"^CY(20\d{2})Q([1-4])$")

_LAST_CALL = 0.0


def _throttle() -> None:
    global _LAST_CALL
    espera = 0.25 - (time.monotonic() - _LAST_CALL)
    if espera > 0:
        time.sleep(espera)
    _LAST_CALL = time.monotonic()


def cik_da_empresa(empresa: str) -> str | None:
    """CIK em vigor: banco (o que o usuário gravou) primeiro, config como fallback."""
    from models.repositories import CikRepository
    return CikRepository().cik_de(empresa)


def fetch_companyfacts(cik: str, timeout: int = 20) -> dict[str, Any] | None:
    _throttle()
    url = BASE.format(cik=cik.zfill(10))
    resp = requests.get(url, headers={"User-Agent": config.USER_AGENT,
                                      "Accept": "application/json",
                                      "Host": "data.sec.gov"}, timeout=timeout)
    if resp.status_code == 200:
        config.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        destino = config.DOWNLOADS_DIR / f"SEC_{cik.zfill(10)}.json"
        destino.write_bytes(resp.content)
        return resp.json()
    raise RuntimeError(f"SEC EDGAR HTTP {resp.status_code} para CIK {cik}")


def extract_facts(payload: dict[str, Any], empresa: str,
                  periodos: set[str] | None = None) -> list[RawExtraction]:
    seen: dict[tuple[str, str], RawExtraction] = {}
    for taxonomy, conceito, canon in XBRL_MAP:
        node = payload.get("facts", {}).get(taxonomy, {}).get(conceito)
        if not node:
            continue
        units = node.get("units", {})
        unit = "USD" if "USD" in units else next(iter(units), None)
        if not unit:
            continue
        for item in units[unit]:
            if item.get("form") not in ("10-Q", "10-K", "20-F", "6-K",
                                             "10-Q/A", "10-K/A", "20-F/A", "6-K/A"):
                continue
            per, conf = None, 0.90
            frame = item.get("frame") or ""
            m = FRAME_Q.match(frame)
            if m:
                per, conf = f"{m.group(1)}Q{m.group(2)}", 0.92
            else:
                fy, fp = item.get("fy"), (item.get("fp") or "")
                if not fy or not fp or fp == "FY":
                    continue  # anual (20-F/10-K): fora do escopo trimestral da PoC
                per = f"{fy}Q{fp[1]}" if fp.startswith("Q") else None
            if not per or (periodos and per not in periodos):
                continue
            try:
                val_bi = round(float(item["val"]) / 1e9, 4)
            except (TypeError, ValueError):
                continue
            key = (canon, per)
            ext = RawExtraction(canon, per, val_bi, "USD bi", conf,
                                f"SEC:{taxonomy}:{conceito}", "USD", {"form": item.get("form")})
            if key not in seen or (item.get("filed") or "") >= (seen[key].extras.get("filed") or ""):
                ext.extras["filed"] = item.get("filed")
                seen[key] = ext
    return list(seen.values())


def collect_empresa(cik: str, empresa: str,
                    periodos: set[str] | None = None) -> list[RawExtraction]:
    payload = fetch_companyfacts(cik)
    if not payload:
        return []
    return extract_facts(payload, empresa, periodos)
