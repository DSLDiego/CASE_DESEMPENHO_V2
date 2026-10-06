"""Benchmark PyMuPDF vs pdf-inspector no acervo real.

Pergunta: seria mais rapido usar pdf-inspector como motor primario e PyMuPDF
como fallback? Mede tempo E qualidade (texto e numeros) no acervo real.
"""
import re
import sys
import time

sys.path.insert(0, r"C:\Users\diego\Downloads\CASE_DESEMPENHO\01_app_notellm")
from config import CONTAINER_DIR  # noqa: E402

LIMITE = int(sys.argv[1]) if len(sys.argv) > 1 else 40
NUMERO = re.compile(r"\d[\d.,]{2,}")


def coletar(limite):
    return sorted(p for p in CONTAINER_DIR.rglob("*.pdf") if p.is_file())[:limite]


def via_pymupdf(caminhos):
    import pymupdf
    chars = nums = paginas = tabelas = 0
    inicio = time.perf_counter()
    ok = falha = 0
    for p in caminhos:
        try:
            with pymupdf.open(p) as doc:
                paginas += len(doc)
                for pg in doc:
                    t = pg.get_text("text")
                    chars += len(t)
                    nums += len(NUMERO.findall(t))
                    tabelas += len(pg.find_tables().tables)
            ok += 1
        except Exception:
            falha += 1
    dt = time.perf_counter() - inicio
    return dt, chars, nums, paginas, tabelas, ok, falha


def via_inspector(caminhos):
    import pdf_inspector as pi
    chars = nums = paginas = tabelas = 0
    inicio = time.perf_counter()
    ok = falha = 0
    for p in caminhos:
        try:
            r = pi.extract_pages_markdown(str(p))
            paginas += len(r.pages)
            tabelas += len(r.pages_with_tables)
            for item in r.pages:
                chars += len(item.markdown)
                nums += len(NUMERO.findall(item.markdown))
            ok += 1
        except Exception:
            falha += 1
    dt = time.perf_counter() - inicio
    return dt, chars, nums, paginas, tabelas, ok, falha


def main():
    caminhos = coletar(LIMITE)
    mb = sum(p.stat().st_size for p in caminhos) / 1024 / 1024
    print(f"acervo: {len(caminhos)} PDFs · {mb:.1f} MB\n")
    res = []
    for nome, fn in (("PyMuPDF (atual)", via_pymupdf),
                     ("pdf-inspector", via_inspector)):
        dt, chars, nums, pag, tab, ok, falha = fn(caminhos)
        res.append((nome, dt, chars, nums, pag, tab, ok))
        print(f"{nome:18} {dt:7.2f} s | {pag:>5} pag | {chars:>9} chars"
              f" | {nums:>7} numeros | {tab:>4} tabelas | ok={ok} falha={falha}")

    (_, t1, c1, m1, p1, b1, _) = res[0]
    (_, t2, c2, m2, p2, b2, _) = res[1]
    print()
    print(f"tempo:     {t1:6.2f}s vs {t2:6.2f}s  -> pdf-inspector "
          f"{t1 / t2:.2f}x {'MAIS RAPIDO' if t2 < t1 else 'MAIS LENTO'}")
    print(f"paginas:   {p1} vs {p2}")
    print(f"texto:     {c2 / c1 * 100:5.1f}% do PyMuPDF")
    print(f"numeros:   {m2 / m1 * 100:5.1f}% do PyMuPDF   <- insumo do parser")
    print(f"tabelas:   {b2} vs {b1}")
    print(f"kchar/s:   PyMuPDF {c1 / t1 / 1000:.1f} | inspector {c2 / t2 / 1000:.1f}")


if __name__ == "__main__":
    main()