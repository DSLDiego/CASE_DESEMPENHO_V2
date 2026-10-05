"""Gera docs/plan_200_tasks.md com 200 microtarefas (checklist da v0)."""
from pathlib import Path
groups = [
    ("Fundacao e dominio", 12), ("Discovery e qualificacao", 16), ("Download robusto", 18),
    ("Parsers 9 formatos", 27), ("Canonical + PeriodResolver", 12), ("Extractors + evidencia", 18),
    ("Normalizacao financeira", 12), ("Qualidade e reconciliacao", 18), ("Persistencia SQLite", 12),
    ("Batch e paralelismo", 20), ("Schedulers", 12), ("Hardware e metrics", 8),
    ("Painel MVC (9 abas)", 18), ("Docs e entregaveis", 7),
]
titles = {
    "Fundacao e dominio": ["Criar {n}: modelo Company/Period/Indicator", "Criar {n}: SourceDocument imutavel", "Criar {n}: CanonicalDocument", "Criar {n}: Extraction+confidence", "Criar {n}: QualityIssue", "Criar {n}: schema.sql + WAL", "Criar {n}: seed empresas", "Criar {n}: seed indicadores", "Criar {n}: seed periodos", "Criar {n}: view metric_current", "Criar {n}: file_manifest", "Criar {n}: etl_run/etl_item/quarantine"],
    "Painel MVC (9 abas)": ["Criar {n}: aba Executiva", "Criar {n}: aba Benchmark", "Criar {n}: aba Evolucao+grafico", "Criar {n}: aba Produtividade", "Criar {n}: aba Dados import/export", "Criar {n}: aba Qualidade", "Criar {n}: aba Fontes", "Criar {n}: aba ETL/batch", "Criar {n}: aba Hardware", "Criar {n}: DashboardController", "Criar {n}: ETLJobManager+cancel", "Criar {n}: narrativa executiva", "Criar {n}: filtros periodo/empresa/indicador", "Criar {n}: export CSV", "Criar {n}: CLI fallback", "Criar {n}: smoke GUI headless", "Criar {n}: roteiro 15min", "Criar {n}: teste de navegacao"],
}
n = 0
lines = ["# Plano 200 microtarefas — v0", ""]
for g, total in groups:
    lines.append(f"## {g} ({total})")
    for i in range(1, total + 1):
        n += 1
        base = titles.get(g, [f"Executar {{n}}: passo {i} de {g}"])
        t = base[(i - 1) % len(base)].format(n=n)
        lines.append(f"- [ ] T{n:03d} {t} — aceite: teste/evidence correspondente verde")
    lines.append("")
p = Path(__file__).resolve().parents[1] / "docs" / "plan_200_tasks.md"
p.write_text("\n".join(lines), encoding="utf-8")
print(f"{n} tarefas -> {p}")
