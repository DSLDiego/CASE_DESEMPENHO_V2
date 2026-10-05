"""Preenche web/html_template.html com os graficos Plotly + tabelas.

Uso: python scripts/web_dashboard.py [--out docs/dashboard_web.html]
Layout: sidebar 25% + ChartArea 75% (tabs dentro), accordions, temas light/dark.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.repositories.sqlite_repo import SQLiteRepository
from src.services.app_services import DashboardService
from src.services.source_panel import build_api_panel, build_documents_panel
from src.services.source_registry import SourceRegistry

BASE = Path(__file__).resolve().parents[1]
COMPANIES = ["PETROBRAS", "EQUINOR", "SHELL", "TOTALENERGIES"]
FIN_INDICATORS = ["REVENUE", "EBITDA_ADJ", "NET_INCOME", "NET_INCOME_ADJ", "OCF"]
ALL_INDICATORS = FIN_INDICATORS + ["EMPLOYEES"]
COLORS = {"PETROBRAS": "#009739", "EQUINOR": "#D20019",
          "SHELL": "#DD1C2A", "TOTALENERGIES": "#003DA5"}
CFG = {"responsive": True, "displayModeBar": True}


def build_dashboard(repo: SQLiteRepository | None = None) -> str:
    repo = repo or SQLiteRepository()
    svc = DashboardService(repo)
    periods = svc.periods()
    cur = "2T2026" if "2T2026" in periods else (periods[-1] if periods else "2T2026")

    # 1) Benchmark com botoes por periodo
    bfig = go.Figure()
    pal = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    for per in periods:
        table = svc.executive_view(per)["table"]
        for i, ind in enumerate(FIN_INDICATORS):
            bfig.add_bar(name=ind if per == periods[0] else None,
                         x=COMPANIES, y=[table.get(c, {}).get(ind) for c in COMPANIES],
                         visible=(per == cur), legendgroup=ind, marker_color=pal[i],
                         showlegend=(per == periods[0]))
    buttons = []
    for k, per in enumerate(periods):
        vis = [False] * (len(periods) * len(FIN_INDICATORS))
        for i in range(len(FIN_INDICATORS)):
            vis[k * len(FIN_INDICATORS) + i] = True
        buttons.append(dict(label=per, method="update",
                            args=[{"visible": vis}, {"title": f"Benchmark — {per} (USD M)"}]))
    bfig.update_layout(barmode="group", title=f"Benchmark — {cur} (USD milhões)", height=360,
                       margin=dict(l=60, r=10, t=60, b=50),
                       xaxis_title="Empresa", yaxis_title="USD milhões",
                       legend=dict(orientation="v", x=1.02, y=1, title="Indicador"),
                       xaxis_showgrid=False, yaxis_showgrid=True, yaxis_gridcolor="#ddd",
                       updatemenus=[dict(type="buttons", direction="right", x=0, y=1.15, buttons=buttons)])
    fig_bench = bfig.to_html(full_html=False, include_plotlyjs=True,
                             div_id="benchmark", config=CFG)

    # 2) Evolucao 2x3
    efig = make_subplots(rows=2, cols=3, subplot_titles=ALL_INDICATORS)
    for i, ind in enumerate(ALL_INDICATORS):
        r, c = divmod(i, 3)
        hist = svc.history(ind)
        for comp in COMPANIES:
            pts = hist.get(comp, [])
            efig.add_scatter(x=[p["period_id"] for p in pts], y=[p["value"] for p in pts],
                             mode="lines+markers", name=comp, legendgroup=comp,
                             showlegend=(i == 0), marker_color=COLORS[comp],
                             row=r + 1, col=c + 1)
    efig.update_layout(title="Evolução por indicador (por trimestre)", height=600,
                       margin=dict(l=60, r=10, t=60, b=50),
                       legend=dict(orientation="v", x=1.0, y=1, title="Empresa"))
    efig.update_xaxes(title_text="Trimestre", showgrid=True, gridcolor="#e5e5e5")
    efig.update_yaxes(title_text="USD milhões", showgrid=True, gridcolor="#ddd")
    fig_evol = efig.to_html(full_html=False, include_plotlyjs=False,
                            div_id="evolucao", config=CFG)

    # 3) Produtividade
    prod = svc.productivity(cur)
    pfig = go.Figure()
    pfig.add_bar(y=list(prod.keys()), x=list(prod.values()), orientation="h",
                 marker_color="#2ca02c")
    pfig.update_layout(title=f"Produtividade — {cur} (USD por empregado)", height=360,
                       margin=dict(l=60, r=10, t=60, b=50),
                       xaxis_title="USD por empregado", yaxis_title="",
                       showlegend=False, xaxis_showgrid=True, xaxis_gridcolor="#ddd")
    fig_prod = pfig.to_html(full_html=False, include_plotlyjs=False,
                            div_id="prod", config=CFG)

    # ---- KPIs executivos: Petrobras vs trimestre anterior + media dos pares ----
    prev = periods[periods.index(cur) - 1] if len(periods) > 1 else None
    now_t = svc.executive_view(cur)["table"]
    prv_t = svc.executive_view(prev)["table"] if prev else {}
    peers = [c for c in COMPANIES if c != "PETROBRAS"]
    kpi_defs = [("Receita", "REVENUE", "USD M"), ("EBITDA ajustado", "EBITDA_ADJ", "USD M"),
                ("Lucro líquido", "NET_INCOME", "USD M"), ("Caixa operacional", "OCF", "USD M"),
                ("Efetivo", "EMPLOYEES", "pessoas")]
    cards = []
    for label, ind, unit in kpi_defs:
        v = now_t.get("PETROBRAS", {}).get(ind)
        q = prv_t.get("PETROBRAS", {}).get(ind)
        dq = "" if v in (None, 0) or q in (None, 0) else f"{(v - q) / abs(q):+.1%} T/T"
        peer = [x for x in (now_t.get(c, {}).get(ind) for c in peers) if x is not None]
        avg = sum(peer) / len(peer) if peer else None
        vs = ""
        if v is not None and avg:
            vs = "acima dos pares ▲" if v > avg else "abaixo dos pares ▼"
        val = "—" if v is None else (f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.1f}")
        cards.append(f"<div class='kpi'><div class='kpi-l'>{label}</div>"
                     f"<div class='kpi-v'>{val} <small>{unit}</small></div>"
                     f"<div class='kpi-d'>{dq} · {vs}</div></div>")
    kpi_cards = "".join(cards)
    # ---- ranking do trimestre (por EBITDA ajustado) ----
    rank = sorted(((c, now_t.get(c, {}).get("EBITDA_ADJ")) for c in COMPANIES),
                  key=lambda x: -((x[1] or 0)))
    rank_rows = "".join(f"<tr><td>{i}º</td><td>{c}</td><td>{v:,.0f}</td></tr>"
                        for i, (c, v) in enumerate(rank, 1) if v is not None)
    fig_prod = pfig.to_html(full_html=False, include_plotlyjs=False,
                            div_id="prod", config=CFG)

    rows = repo.query("SELECT company_id, period_id, indicator_id, value, unit, confidence "
                      "FROM metric_current ORDER BY 2,1,3")
    data_rows = "".join(
        f"<tr><td>{r['company_id']}</td><td>{r['period_id']}</td><td>{r['indicator_id']}</td>"
        f"<td>{r['value']}</td><td>{r['unit']}</td><td>{r['confidence']}</td></tr>" for r in rows)
    qrows = repo.quality_issues(100)
    qual_rows = "".join(
        f"<tr><td>{q['rule']}</td><td>{q['severity']}</td><td>{q['message']}</td></tr>" for q in qrows) \
        or '<tr><td colspan="3">Nenhum alerta</td></tr>'
    docs = build_documents_panel(repo, SourceRegistry())
    docs_rows = "".join(
        f"<tr><td>{d['site']}</td><td>{d['documento']}</td><td>{d['extensao']}</td>"
        f"<td>{d['pasta']}</td><td>{d['data_download']}</td></tr>" for d in docs) \
        or '<tr><td colspan="5">Sem documentos</td></tr>'
    apis = build_api_panel(SourceRegistry())
    api_rows = "".join(
        f"<tr><td>{a['site']}</td><td>{a['fonte']}</td><td>{a['api_url']}</td>"
        f"<td>{a['status']}</td><td>{a['verificada_em']}</td><td>{a['amostra']}</td></tr>" for a in apis)

    tpl = (BASE / "web" / "html_template.html").read_text(encoding="utf-8")
    return (tpl
            .replace("{{TITLE}}", f"Benchmarking Financeiro — {cur}")
            .replace("{{NARRATIVE}}", f"<b>Análise executiva ({cur}):</b> {svc.executive_view(cur)['narrative']}")
            .replace("{{KPI_CARDS}}", kpi_cards)
            .replace("{{RANK_ROWS}}", rank_rows)
            .replace("{{FIG_BENCH}}", fig_bench)
            .replace("{{FIG_EVOL}}", fig_evol)
            .replace("{{FIG_PROD}}", fig_prod)
            .replace("{{DATA_ROWS}}", data_rows)
            .replace("{{QUALITY_ROWS}}", qual_rows)
            .replace("{{DOCS_ROWS}}", docs_rows)
            .replace("{{API_ROWS}}", api_rows)
            .replace("{{PERIODS_OPTIONS}}", "".join(f"<option>{p}</option>" for p in periods))
            .replace("{{COMPANIES_OPTIONS}}", "".join(f"<option>{c}</option>" for c in COMPANIES))
            .replace("{{INDICATORS_OPTIONS}}", "".join(f"<option>{i}</option>" for i in ALL_INDICATORS)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/dashboard_web.html")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_dashboard(), encoding="utf-8")
    print(f"dashboard web -> {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
