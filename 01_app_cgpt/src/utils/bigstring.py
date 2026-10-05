"""Utilidades BigString: hash em stream, leitura por linhas, join eficiente."""
from __future__ import annotations
import hashlib
from pathlib import Path


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> tuple[str, int]:
    h = hashlib.sha256()
    total = 0
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
            total += len(block)
    return h.hexdigest(), total


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iter_lines(path: str | Path, encoding: str = "utf-8", errors: str = "ignore"):
    with open(path, "r", encoding=encoding, errors=errors) as f:
        for line in f:
            yield line


def join_parts(parts) -> str:
    return "".join(parts)
