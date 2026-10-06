"""Tarefa de parse picklável para o pool de processos do ETL.

`concurrent.futures.ProcessPoolExecutor` precisa serializar a função e o retorno.
Um parser escolhido por `escolher_parser` é um objeto de função (pode não ser
picklável), então a tarefa é resolvida **dentro** do processo filho, pelo caminho
do arquivo — que é string e é o que trafega.
"""
from __future__ import annotations

import time
from pathlib import Path


class _ErroParse(Exception):
    """Transporte de exceção entre processos (picklável ao contrário de Exception)."""

    def __init__(self, tipo: str, mensagem: str) -> None:
        super().__init__(f"{tipo}: {mensagem}")
        self.tipo = tipo
        self.mensagem = mensagem


def _ms(inicio: float) -> float:
    """Duração em ms com 1 casa decimal (sub-milissegundo não é zero, é precisão)."""
    return round((time.perf_counter() - inicio) * 1000, 1)


def parse_arquivo(caminho_str: str) -> tuple[Exception | None, float, list, dict]:
    """(erro, duracao_ms, extracoes, metrica) para um arquivo. Nunca levanta exceção.

    A duração vai com 1 casa decimal: um CSV pequeno leva menos de 1 ms e
    truncar para 0 fazia a métrica do painel mentir ("0 ms" em vez de "0,4 ms").

    `metrica` traz as páginas lidas e as tabelas detectadas do PDF (M8.12), o que
    dá ao painel o throughput em páginas/seg. Para CSV/XLSX ela é zerada — não
    tem página — e o painel distingue "não medido" de "mediu zero".
    """
    from workers.etl import escolher_parser

    caminho = Path(caminho_str)
    inicio = time.perf_counter()
    try:
        parser = escolher_parser(caminho)
        if parser is None:
            return (None, _ms(inicio), [], {})
        # IMPORTANTE: o parse precisa rodar ANTES de medir o tempo. Num
        # `return (None, tempo(), parser(x))` o Python avalia os argumentos da
        # esquerda para a direita e mediria quase zero — foi o que zerou a coluna
        # duracao_ms no painel (67,8 ms viravam 0).
        extrações = parser(caminho)
        return (None, _ms(inicio), extrações, _metrica_de(caminho))
    except _ErroParse as exc:                     # pragma: no cover
        return (exc, _ms(inicio), [], {})
    except Exception as exc:                      # noqa: BLE001
        return (_ErroParse(type(exc).__name__, str(exc)), _ms(inicio), [], {})


def _metrica_de(caminho: Path) -> dict[str, int]:
    """Métrica de leitura do arquivo, se houver (hoje só PDF tem o conceito)."""
    if caminho.suffix.lower() != ".pdf":
        return {}
    try:
        from workers.parse_pdf import ultima_metrica
        return ultima_metrica()
    except Exception:                             # noqa: BLE001
        return {}
