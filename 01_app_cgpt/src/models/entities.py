"""Entidades de dominio (Clean Code: nomes revelam intencao)."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Company:
    company_id: str
    name: str
    country: str = ""
    currency: str = "USD"
    in_poc: bool = True


@dataclass(frozen=True)
class Period:
    period_id: str
    year: int
    quarter: int
    report_type: str = "QUARTER"
    is_ytd: bool = False


@dataclass(frozen=True)
class Indicator:
    indicator_id: str
    name: str
    category: str
    unit: str = "USD_M"


@dataclass
class SourceDocument:
    source_id: str = ""
    company_id: str = ""
    document: str = ""
    url: str = ""
    url_final: str = ""
    local_path: str = ""
    sha256: str = ""
    size_bytes: int = 0
    content_type: str = ""
    etag: str = ""
    last_modified: str = ""
    version: int = 1
    is_official: bool = False
    authority: str = "UNKNOWN"
    is_demo: bool = False
    content: bytes = b""


@dataclass
class CanonicalDocument:
    document_id: str
    company_id: str
    period_id: str
    text: str = ""
    tables: list = field(default_factory=list)
    pages: int = 1
    profile: str = "TEXT"
    source_path: str = ""


@dataclass
class Extraction:
    company_id: str
    period_id: str
    indicator_id: str
    value: float | None
    currency: str = "USD"
    unit: str = "USD_M"
    confidence: float = 0.6
    evidence: str = ""
    page: int | None = None
    sheet: str | None = None
    method: str = "HEURISTIC"


@dataclass
class QualityIssue:
    rule: str
    severity: str
    message: str
    company_id: str = ""
    period_id: str = ""
    indicator_id: str = ""
    value: float | None = None
    previous_value: float | None = None
