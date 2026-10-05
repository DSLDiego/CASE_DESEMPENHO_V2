"""View Web: painel estatico com Plotly + filtros client-side (JS, sem servidor).

Layout: Sidebar 25% (accordions, scroll, colapso) + WorkArea 75% (tabs, grid NxM,
temas). Dataset completo embutido em JSON: checkboxes filtram empresas nas series
temporais; seletor de trimestre filtra barras, matriz e leitura executiva.
"""
from __future__ import annotations

import json as _json
import re as _re
from pathlib import Path

import plotly.graph_objects as go
from plotly.offline import plot as plot_div

import config
from config import INDICATORS
from controllers import AnalyticsController, SourceController

CATEGORICAS = list(config.PALETA)
CORES = dict(config.PALETA)
ESTILO = config.ESTILO_SERIE
CORES_DESATIVADAS = ["#9AA5B1", "#B8C0C8", "#7C8794", "#C3CBD3", "#96A0AA", "#D5DBE1", "#8892A0"]
_QOK = _re.compile(r"^\d{4}Q[1-4]$")
TS_RUBS = ["RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO", "FCO", "DIVIDA_LIQUIDA", "CAPEX"]
BAR_RUBS = ["RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO", "DIVIDA_LIQUIDA",
            "CAPEX", "DIVIDA_BRUTA", "LUCRO_BRUTO", "FCL"]
ORDEM_MATRIZ = ["RECEITA_LIQUIDA", "LUCRO_BRUTO", "DESPESA_OPERACIONAL", "EBITDA_AJUSTADO",
                "LUCRO_LIQUIDO", "FCO", "FCL", "CAPEX", "DIVIDA_BRUTA", "DIVIDA_LIQUIDA"]

# Config global do Plotly: sem modebar (o toolbar flutuante cobria o titulo do
# grafico e vazava sobre a celula vizinha), responsivo e com duplo clique = reset.
PLOT_CONFIG = {"displayModeBar": False, "responsive": True, "scrollZoom": False,
               "doubleClick": "reset", "displaylogo": False, "showTips": False}


def _plot_div_id(div: str) -> tuple[str, str | None]:
    """Extrai o uuid que o proprio Plotly gerou (div e newPlot usam o mesmo)."""
    m = _re.search(r'<div id="([^"]+)" class="plotly-graph-div"', div)
    return div, (m.group(1) if m else None)


def _fig_bar(empresas: list[str], valores: list[float], titulo: str, unidade: str) -> tuple[str, str | None]:
    cores = [CORES.get(e, CORES_DESATIVADAS[i % len(CORES_DESATIVADAS)])
             for i, e in enumerate(empresas)]
    fig = go.Figure(go.Bar(x=empresas, y=valores, marker_color=cores,
                           marker_line=dict(width=1.5, color="#ffffff"),
                           text=[f"{v:.2f}" for v in valores],
                           textposition="outside", cliponaxis=True,
                           hovertemplate="%{x}: %{y:,.2f} " + unidade + "<extra></extra>"))
    media = (sum(valores) / len(valores)) if valores else None
    if media is not None:
        fig.add_hline(y=media, line_dash="dash", line_color="gray")
    # headroom: os rotulos "outside" das barras precisam caber dentro da celula
    topo = max(valores) * 1.18 if valores else 1
    fig.update_layout(title=titulo, yaxis_title=unidade, height=340, margin=dict(t=52, b=58, l=52, r=20),
                      xaxis=dict(automargin=True, tickangle=-20, tickfont=dict(size=10)),
                      yaxis=dict(automargin=True, rangemode="tozero", range=[0, topo], tickfont=dict(size=10)),
                      uniformtext=dict(minsize=9, mode="show"), hovermode="closest",
                      hoverlabel=dict(namelength=-1), bargap=0.32,
                      template="plotly", font=dict(size=11))
    return _plot_div_id(plot_div(fig, output_type="div", include_plotlyjs=False, config=PLOT_CONFIG))


def _fig_serie(rubrica: str, titulo: str, quarters: list[str],
               series: dict[str, dict[str, dict[str, float]]]) -> tuple[str, list[str], str | None]:
    """Um trace por empresa ao longo dos trimestres.

    Cor + trace + marcador por empresa (Okabe-Ito em config.PALETA): antes todas as
    series eram azuis parecidos e o Plotly mantia o mesmo trace/marker, deixando o
    grafico de linha ilegivel.
    """
    fig = go.Figure()
    ordem = []
    for emp in [e for e in CATEGORICAS if e in series.get(rubrica, {})]:
        vals = series[rubrica][emp]
        est = ESTILO.get(emp, {})
        cor = CORES.get(emp, "#4a90d9")
        fig.add_trace(go.Scatter(
            x=quarters, y=[vals.get(p) for p in quarters],
            mode="lines+markers", name=emp, connectgaps=True,
            line=dict(color=cor, width=est.get("width", 2),
                      dash=est.get("dash", "solid"),
                      shape="spline" if emp == "PETROBRAS" else "linear",
                      simplify=False),
            marker=dict(color=cor, size=7 if emp == "PETROBRAS" else 5,
                        symbol=est.get("symbol", "circle"),
                        line=dict(width=1, color="#ffffff")),
            hovertemplate=emp + ": %{y:,.2f} USD bi<extra></extra>"))
        ordem.append(emp)
    fig.update_layout(title=titulo, yaxis_title="USD bi", height=340,
                      margin=dict(t=46, b=58, l=52, r=16), template="plotly",
                      xaxis=dict(automargin=True, tickfont=dict(size=10)),
                      yaxis=dict(automargin=True, tickfont=dict(size=10)),
                      font=dict(size=11), hovermode="x",
                      hoverlabel=dict(namelength=-1), spikedistance=-1,
                      legend=dict(orientation="h", x=0.02, y=0.98, xanchor="left", yanchor="top",
                                  bgcolor="rgba(0,0,0,0)", font=dict(size=9)))
    div, pid = _plot_div_id(plot_div(fig, output_type="div", include_plotlyjs=False, config=PLOT_CONFIG))
    return div, ordem, pid


def build_dashboard(periodo: str = "2026Q2", destino=None) -> str:
    destino = Path(destino) if destino else config.WEB_HTML
    analytics = AnalyticsController()
    sources = SourceController()
    matriz = analytics.fatos.matriz(periodo)
    por_rub: dict[str, dict[str, float]] = {}
    for row in matriz:
        por_rub.setdefault(row["rubrica_padronizada"], {})[row["nome_empresa"]] = row["valor"]

    def bar(rubrica: str, titulo: str) -> str:
        dados = por_rub.get(rubrica, {})
        emps = [e for e in CATEGORICAS if e in dados] or sorted(dados)
        if not emps:  # estado vazio explicito (nada de grafico em branco)
            return ("<div class='empty'>sem dados para este indicador no período"
                    "<br><span class='note'>rode <b>python app_main.py etl --extra " + periodo +
                    "</b> ou <b>sec --periodos " + periodo + "</b></span></div>")
        div, pid = _fig_bar(emps, [dados[e] for e in emps], titulo, "USD bi")
        if pid:
            BAR_IDS[rubrica] = pid
        return div
    BAR_IDS: dict[str, str] = {}

    with analytics.fatos.db.connect() as _conn:
        _all = _conn.execute(
            "SELECT nome_empresa, periodo, rubrica_padronizada, valor FROM tb_fato_financeiro").fetchall()
    quarters_all = sorted({r["periodo"] for r in _all if _QOK.match(r["periodo"] or "")})
    if periodo not in quarters_all:
        quarters_all = sorted(set(quarters_all) | {periodo})
    from workers.quality import taxa_para_usd
    TAXAS = {}
    for _q in quarters_all:
        try:
            TAXAS[_q] = round(float(taxa_para_usd(_q)), 4)
        except Exception:
            TAXAS[_q] = 5.20
    SERIES: dict[str, dict[str, dict[str, float]]] = {}
    for r in _all:
        if not _QOK.match(r["periodo"] or ""):
            continue
        SERIES.setdefault(r["rubrica_padronizada"], {}).setdefault(r["nome_empresa"], {})[r["periodo"]] = r["valor"]

    def _matriz(per: str) -> str:
        import html as _html
        m: dict[str, dict[str, float]] = {}
        src: dict[tuple[str, str], str] = {}
        for row in analytics.fatos.matriz(per):
            m.setdefault(row["rubrica_padronizada"], {})[row["nome_empresa"]] = row["valor"]
            origem = row.get("url_fonte") or ""
            tipo = f" [{row.get('tipo_arquivo')}]" if row.get("tipo_arquivo") else ""
            src[(row["rubrica_padronizada"], row["nome_empresa"])] = (
                _html.escape(f"Fonte: {origem}{tipo}") if origem else "Fonte: SEC/RI (ver catálogo)")
        cols = [e for e in CATEGORICAS if any(e in m.get(r, {}) for r in ORDEM_MATRIZ)]
        head = "".join(f"<th>{e}</th>" for e in cols)
        rows = ""
        for rub in ORDEM_MATRIZ:
            cells = "".join(
                f"<td title=\"{src.get((rub, e), '')}\">{m.get(rub, {}).get(e):,.2f}</td>"
                if e in m.get(rub, {}) else "<td class='note'>—</td>" for e in cols)
            rows += f"<tr><th>{rub}</th>{cells}</tr>"
        return (f"<table><tr><th>Indicador (USD bi) \\ Empresa</th>{head}</tr>{rows}</table>"
                f"<div class='note'>Matriz comparativa {per} · passe o mouse na célula p/ ver a fonte · — = sem dado</div>")

    matriz_tab = _matriz(periodo)
    _kpi = []
    for _tit, _rub, _fmt in (("Receita líder", "RECEITA_LIQUIDA", " USD bi"),
                             ("EBITDA líder", "EBITDA_AJUSTADO", " USD bi"),
                             ("Lucro líder", "LUCRO_LIQUIDO", " USD bi")):
        _rank = sorted(por_rub.get(_rub, {}).items(), key=lambda kv: kv[1], reverse=True)
        if _rank:
            _kpi.append(f"<div class='kpi'><div class='kpi-t'>{_tit}</div>"
                        f"<div class='kpi-v' data-kpi='{_rub}' data-per='{periodo}'>{_rank[0][1]:,.2f}{_fmt}</div>"
                        f"<div class='kpi-s'>{_rank[0][0]} · {periodo}</div></div>")
    _marg = ""
    _rec = por_rub.get("RECEITA_LIQUIDA", {}).get("PETROBRAS")
    _ebi = por_rub.get("EBITDA_AJUSTADO", {}).get("PETROBRAS")
    if _rec:
        _marg = (f"<div class='kpi'><div class='kpi-t'>Margem EBITDA Petrobras</div>"
                 f"<div class='kpi-v' data-kpi='MARGEM' data-per='{periodo}'>{(_ebi / _rec * 100 if _ebi else 0):,.1f}%</div>"
                 f"<div class='kpi-s'>{periodo}</div></div>")
    kpi_bar = f"<div class='kpis' id='kpis'>{''.join(_kpi)}{_marg}</div>"
    _mkt: dict[str, dict[str, str]] = {}
    with analytics.fatos.db.connect() as _c2:
        for _r in _c2.execute(
                "SELECT nome_empresa, periodo, indicador, valor, unidade_medida FROM tb_fato_operacional"
                " WHERE indicador IN ('COTACAO','P_L','DIVIDEND_YIELD')").fetchall():
            _mkt.setdefault(_r["nome_empresa"], {})[_r["indicador"]] = (
                f"{_r['valor']:,.2f} {_r['unidade_medida']}".strip())
    from workers.ri_collector import I10_SITES as _I10
    _mkt_rows = "".join(
        f"<tr><td>{e}</td><td>{_mkt.get(e, {}).get('COTACAO', '—')}</td>"
        f"<td>{_mkt.get(e, {}).get('P_L', '—')}</td>"
        f"<td>{_mkt.get(e, {}).get('DIVIDEND_YIELD', '—')}</td>"
        f"<td><a href='{_I10[e]}'>Investidor10</a></td></tr>" for e in CATEGORICAS)
    mercado_tab = (f"<table><tr><th>Empresa</th><th>Cotação</th><th>P/L</th><th>DY</th>"
                   f"<th>Fonte</th></tr>{_mkt_rows}</table>"
                   f"<div class='note'>Snapshot Investidor10 (`coleta --site I10 --mercado`) — sem dados? rode a coleta.</div>")
    _der: dict[str, dict[str, str]] = {}
    with analytics.fatos.db.connect() as _c3:
        for _r in _c3.execute(
                "SELECT nome_empresa, periodo, indicador, valor FROM tb_fato_operacional"
                " WHERE indicador IN ('MARGEM_EBITDA','MARGEM_LIQUIDA','DIVIDA_LIQUIDA_EBITDA')"
                " AND periodo = ?", (periodo,)).fetchall():
            uni = "%" if "MARGEM" in _r["indicador"] else "x"
            _der.setdefault(_r["nome_empresa"], {})[_r["indicador"]] = f"{_r['valor']:,.2f}{uni}"
    _der_rows = "".join(
        f"<tr><td>{e}</td><td>{_der.get(e, {}).get('MARGEM_EBITDA', '—')}</td>"
        f"<td>{_der.get(e, {}).get('MARGEM_LIQUIDA', '—')}</td>"
        f"<td>{_der.get(e, {}).get('DIVIDA_LIQUIDA_EBITDA', '—')}</td></tr>" for e in CATEGORICAS)
    rentab_tab = (f"<table><tr><th>Empresa</th><th>Margem EBITDA</th><th>Margem líquida</th>"
                  f"<th>Dívida líq./EBITDA</th></tr>{_der_rows}</table>"
                  f"<div class='note'>Derivados calculados (`derivados`) a partir dos fatos {periodo}.</div>")
    ts_cells, traces, ts_ids = [], {}, {}
    nome_ind = {i["codigo"]: i["nome"] for i in INDICATORS}
    for _rub in [r for r in TS_RUBS if r in SERIES]:
        _div, _ordem, _pid = _fig_serie(_rub, "", quarters_all, SERIES)
        traces[_rub] = _ordem
        if _pid:
            ts_ids[_rub] = _pid
        _titulo = f"{nome_ind.get(_rub, _rub)} — série temporal"
        ts_cells.append(f"<div class='cell'><h4>{_titulo}</h4>{_div}</div>")
    ts_grid = "".join(ts_cells)

    def gridbar(gid: str) -> str:
        cols = "".join(
            f"<button onclick=\"gridCols('{gid}',{n},this)\"{' class=\"on\"' if n == 2 else ''}>{n}</button>"
            for n in (1, 2, 3, 4))
        sizes = "".join(
            f"<button onclick=\"gridH('{gid}',{h},this)\"{' class=\"on\"' if lbl == 'P' else ''}>{lbl}</button>"
            for h, lbl in ((400, "P"), (560, "M"), (760, "G")))
        return (f"<div class='gridbar'><span class='note'>Grade {gid}:</span> colunas {cols}"
                f"<span class='note'>altura</span> {sizes}"
                f"<button onclick=\"fitAll('{gid}')\" title='Redimensionar todos os graficos'>⤢ ajustar</button>"
                f"<span class='note'>duplo clique no gráfico = tela cheia</span></div>")

    insight = analytics.insight_executivo(periodo)
    fontes = sources.catalogo()
    with analytics.fatos.db.connect() as _conn:
        _ef = [_conn.execute(
            "SELECT nome_empresa, periodo, valor FROM tb_fato_operacional"
            " WHERE indicador = 'EFETIVO_TOTAL' ORDER BY nome_empresa, periodo").fetchall()]
        efetivo_rows = [dict(r) or {} for r in _ef[0]]
    _ult = {}
    for r in efetivo_rows:
        _ult[r["nome_empresa"]] = (r["periodo"], r["valor"])
    _emps = [e for e in CATEGORICAS if e in _ult] or sorted(_ult)
    efetivo_bar, _ = _fig_bar(_emps, [_ult[e][1] for e in _emps],
                           "Efetivo total — âncora anual (pessoas)", "pessoas")
    efetivo_tab = "".join(
        f"<tr><td>{e}</td><td>{_ult[e][0]}</td><td>{_ult[e][1]:,.0f}</td></tr>" for e in _emps)
    linhas = "".join(
        f"<tr><td>{f['id_fonte']}</td><td>{f['nome_empresa']}</td>"
        f"<td>{(f.get('nome_documento') or '')[:44]}</td>"
        f"<td>{f.get('extensao') or f['tipo_arquivo']}</td>"
        f"<td class='url'>{(f.get('pasta_sistema') or '')[:34]}</td>"
        f"<td class='url'>{('JSON: ' + (f['api_json'] or '')[:26]) if f.get('api_json') else '—'}</td>"
        f"<td class='url'>{(f['url_fonte'] or '')[:44]}</td><td>{f['data_download'] or ''}</td>"
        f"<td><span class='status {f['status_processamento']}'>{f['status_processamento']}</span></td>"
        f"<td><button class='sm' onclick=\"fEditar({f['id_fonte']})\">editar</button>"
        f"<button class='sm' onclick=\"fExcluir({f['id_fonte']})\">excluir</button></td></tr>"
        for f in fontes[:300])
    com_api = sum(1 for f in fontes if (f.get("api_json") or "").startswith("http"))
    pasta_raiz = config.DOWNLOADS_DIR.name
    qualidade = sources.qualidade()
    alertas = "".join(
        f"<tr><td>{a['tipo_alerta']}</td><td>{a['descricao'][:110]}</td><td>{a['severidade']}</td></tr>"
        for a in qualidade["alertas"][:100])
    revisao = "".join(
        f"<tr><td>{r['nome_empresa']}</td><td>{r['periodo']}</td><td>{r['rubrica']}</td>"
        f"<td>{r['motivo'][:100]}</td><td>{r['status']}</td></tr>"
        for r in qualidade["revisao"][:100])

    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PetroAnalytics PoC — Benchmark {periodo}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root{{--bg:#12151c;--panel:#1a1e28;--card:#222733;--txt:#e2e8f0;--mut:#94a3b8;--line:#2d3748;--acc:#00a86b}}
[data-theme=light]{{--bg:#f4f6f8;--panel:#fff;--card:#fff;--txt:#0f172a;--mut:#64748b;--line:#e2e8f0;--acc:#007a4d}}
*{{box-sizing:border-box}}body{{margin:0;font-family:'Segoe UI',Arial,sans-serif;background:var(--bg);color:var(--txt);display:flex;height:100vh;overflow:hidden;font-size:12px}}
#sidebar{{width:25%;min-width:230px;background:var(--panel);border-right:1px solid var(--line);display:flex;flex-direction:column;transition:width .25s}}body.menu-off #sidebar{{display:none}}
.side-head{{display:flex;align-items:center;justify-content:space-between;padding:12px 12px 4px}}.side-head h3{{margin:0}}
#collapse{{border:none;border-radius:50%;width:26px;height:26px;background:var(--acc);color:#fff;cursor:pointer;font-size:11px;flex:none}}
#expand{{display:none;position:fixed;left:8px;top:10px;z-index:50;border:none;border-radius:6px;padding:6px 10px;background:var(--acc);color:#fff;cursor:pointer;font-size:12px}}body.menu-off #expand{{display:block}}
.side-in{{padding:12px;overflow-y:auto;overflow-x:auto;height:100%}}details{{border:1px solid var(--line);border-radius:6px;margin-bottom:8px;background:var(--card)}}
summary{{cursor:pointer;padding:8px;font-weight:600;font-size:11px}}summary::-webkit-details-marker{{color:var(--acc)}}
.acc{{padding:8px;border-top:1px solid var(--line)}}.acc label{{display:block;margin:3px 0;font-size:11px}}
#work{{flex:1;display:flex;flex-direction:column;min-width:0}}.tabs{{display:flex;background:var(--panel);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20;flex:none;overflow-x:auto;scrollbar-width:thin}}
.tab{{padding:9px 16px;cursor:pointer;border:none;background:none;color:var(--txt);font-size:11px;font-weight:700;white-space:nowrap}}.tab.on{{border-bottom:3px solid var(--acc);color:var(--acc)}}
.page{{display:none;padding:12px;overflow:auto;flex:1}}.page.on{{display:block}}
body{{scrollbar-gutter:stable}}
.grid{{display:grid;grid-template-columns:repeat(var(--cols,2),minmax(0,1fr));gap:12px;align-items:start}}.grid>*{{min-width:0}}
.cell{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px;min-height:var(--cellh,400px);display:flex;flex-direction:column;overflow:hidden;position:relative;contain:layout paint;isolation:isolate}}
.cell .plotly-graph-div,.cell .js-plotly-plot,.cell .plot-container{{max-width:100%;overflow:hidden}}
.cell .hoverlayer,.cell .modebar,.cell .annotation,.cell .legend,.cell .infolayer{{overflow:hidden}}
.cell h4{{margin:2px 0 6px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.cell .plotly-graph-div{{flex:1;width:100%!important;min-height:0}}
/* width:100%!important e' obrigatorio: o Plotly grava a largura INLINE no div ao
   renderizar (555px em grade de 2 colunas) e com isso o resize trava — ao passar
   para 4 colunas o grafico continuava largo e era cortado dentro da celula. */
.cell h4{{margin:2px 0 6px;font-size:12px}}.note{{color:var(--mut);font-size:11px}}
.badge{{font-size:10px;font-weight:600;color:var(--mut);border:1px solid var(--line);
  border-radius:9px;padding:0 6px;margin-left:4px;white-space:nowrap}}
.fs{{position:fixed;inset:0;background:rgba(2,6,12,.88);z-index:100;display:none;padding:18px}}
.fs.on{{display:flex;align-items:center;justify-content:center}}
.fs-inner{{background:var(--panel);border:1px solid var(--line);border-radius:8px;width:100%;height:100%;display:flex;flex-direction:column;padding:10px}}
.fs-head{{display:flex;justify-content:space-between;align-items:center;font-size:12px;margin-bottom:6px}}
#fs-plot{{flex:1;min-height:0}}
.empty{{display:flex;align-items:center;justify-content:center;flex:1;color:var(--mut);font-size:12px;text-align:center;padding:20px}}
.gridbar{{display:flex;gap:6px;align-items:center;margin:8px 0;font-size:11px;flex-wrap:wrap}}.gridbar button{{font-size:11px;padding:3px 10px;cursor:pointer}}.gridbar button.on{{background:var(--acc);color:#fff;border:none;border-radius:3px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}th,td{{border:1px solid var(--line);padding:5px 7px;text-align:left}}th{{background:var(--card)}}
.pager{{display:flex;gap:8px;align-items:center;margin:8px 0;font-size:11px}}.pager button,.pager select{{font-size:11px;padding:3px 8px}}
.twrap{{overflow-x:auto;max-width:100%}}.twrap table{{min-width:640px}}
.crud{{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:8px 0;font-size:11px}}
.crud input,.crud select{{font-size:11px;padding:3px 6px;border:1px solid var(--line);border-radius:4px;background:var(--card);color:var(--txt)}}
.status{{padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700}}.PROCESSADO{{background:#046c4e;color:#fff}}.CATALOGADO,.DESCOBERTO{{background:#374151;color:#fff}}.SEM_DADOS{{background:#92400e;color:#fff}}.ERRO{{background:#7f1d1d;color:#fff}}.NAO_PROCESSADO,.NAO_BAIXADO,.SEM_PARSER{{background:#4b5563;color:#fff}}.PENDENTE{{background:#6b7280;color:#fff}}
.err{{color:#dc2626;font-size:10px;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
select,button.sm{{font-size:11px;padding:4px 8px;margin:2px}}.insight{{background:var(--card);border-left:4px solid var(--acc);padding:10px;border-radius:4px;margin-bottom:10px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:10px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:6px;padding:8px 10px}}
.kpi-t{{font-size:10px;color:var(--mut);text-transform:uppercase}}.kpi-v{{font-size:20px;font-weight:800}}.kpi-s{{font-size:11px}}
@media(max-width:900px){{#sidebar{{min-width:190px}}.grid{{--cols:1}}}}
</style></head>
<body data-theme="light">
<button id="expand" onclick="toggleMenu()" title="Mostrar menu">▶ Menu</button>
<div id="sidebar"><div class="side-head"><h3>PetroAnalytics PoC</h3><button id="collapse" onclick="toggleMenu()" title="Ocultar menu">◀</button></div><div class="side-in">
<div class="note">Benchmark Petrobras vs pares · {periodo}</div><hr>
<details open><summary>1 · Período &amp; moeda</summary><div class="acc">
<label>Trimestre (filtra barras, matriz e leitura):</label>
<select id="qsel" onchange="applyQuarter(this.value)">
{"".join(f"<option value='{q}'{' selected' if q == periodo else ''}>{q}</option>" for q in quarters_all)}
</select>
<label>Moeda dos valores (USD bi ↔ BRL bi, PTAX de fechamento):</label>
<label><input type="radio" name="moeda" value="USD" checked onchange="setMoeda('USD')"> USD</label>
<label><input type="radio" name="moeda" value="BRL" onchange="setMoeda('BRL')"> BRL (PTAX)</label>
<label class="note">Efetivo segue em pessoas · leitura executiva em USD</label>
<label class="note">PTAX do trimestre selecionado: <b id="ptax">R$ {TAXAS.get(periodo, 5.2):.2f}</b></label></div></details>
<details open><summary>2 · Empresas &amp; indicadores</summary><div class="acc">
<label class="note">Empresas (filtram séries temporais):</label>
{"".join(f"<label><input type='checkbox' class='empchk' value='{e}' checked onchange='applyCompanies()'> {e}</label>" for e in CATEGORICAS)}
<hr>{"".join(f"<label>· {i['codigo']} <span class='note'>({i['unidade']})</span></label>" for i in INDICATORS)}
</div></details>
<details><summary>3 · Tema</summary><div class="acc">
<button class="sm" onclick="setTheme('light')">Claro</button>
<button class="sm" onclick="setTheme('dark')">Escuro</button></div></details>
<details><summary>4 · Qualidade</summary><div class="acc">
<label>Alertas: <b>{len(qualidade['alertas'])}</b> · Revisão: <b>{len(qualidade['revisao'])}</b></label>
<label class="note">Ver aba Auditoria. Fontes: {len(fontes)} arquivos.</label></div></details>
</div></div>
<div id="work">
<div class="tabs">
<button class="tab on" onclick="tab(0)">Visão executiva</button>
<button class="tab" onclick="tab(1)">Comparação</button>
<button class="tab" onclick="tab(2)">Expandidos</button>
<button class="tab" onclick="tab(3)">Evolução histórica</button>
<button class="tab" onclick="tab(4)">Efetivo (âncora anual)</button>
<button class="tab" onclick="tab(5)">Fontes (CRUD)</button>
<button class="tab" onclick="tab(6)">Gestão ETL</button>
<button class="tab" onclick="tab(7)">Auditoria</button>
</div>
<div class="page on"><div class="insight"><b>Leitura executiva <span class="qper">{periodo}</span>:</b> <span id="insight-txt">{insight}</span></div>
<div><button class="sm" onclick="emailGrafico()" title="Gerar e-mail com o gráfico anexado">✉ Enviar por e-mail</button>
<span class="note">gera <b>.eml</b> com o gráfico (HTML+PNG+CSV) em <b>data/outbox</b>; use <b>app_main.py email --enviar</b> p/ SMTP real</span></div>
{kpi_bar}
{gridbar('exec')}
<div class="grid" id="grid-exec"><div class="cell"><h4>Receita líquida (USD bi) <span class="badge" id="badge-RECEITA_LIQUIDA"></span></h4>{bar('RECEITA_LIQUIDA','')}</div>
<div class="cell"><h4>EBITDA ajustado (USD bi) <span class="badge" id="badge-EBITDA_AJUSTADO"></span></h4>{bar('EBITDA_AJUSTADO','')}</div></div></div>
<div class="page">{gridbar('comp')}
<div class="grid" id="grid-comp"><div class="cell"><h4>Lucro líquido (USD bi) <span class="badge" id="badge-LUCRO_LIQUIDO"></span></h4>{bar('LUCRO_LIQUIDO','')}</div>
<div class="cell"><h4>Dívida líquida (USD bi) <span class="badge" id="badge-DIVIDA_LIQUIDA"></span></h4>{bar('DIVIDA_LIQUIDA','')}</div></div>
<h4 style="margin-top:10px">Matriz comparativa resultante (<span class="qper">{periodo}</span>, USD bi)</h4>
<div id="matriz-wrap" class="twrap">{matriz_tab}</div>
<h4 style="margin-top:10px">Mercado — snapshot Investidor10</h4>{mercado_tab}
<h4 style="margin-top:10px">Rentabilidade e alavancagem (<span class="qper">{periodo}</span>)</h4>{rentab_tab}</div>
<div class="page">{gridbar('exp')}
<div class="grid" id="grid-exp"><div class="cell"><h4>CAPEX / Investimentos (USD bi) <span class="badge" id="badge-CAPEX"></span></h4>{bar('CAPEX','')}</div>
<div class="cell"><h4>Dívida bruta (USD bi) <span class="badge" id="badge-DIVIDA_BRUTA"></span></h4>{bar('DIVIDA_BRUTA','')}</div>
<div class="cell"><h4>Lucro bruto (USD bi) <span class="badge" id="badge-LUCRO_BRUTO"></span></h4>{bar('LUCRO_BRUTO','')}</div>
<div class="cell"><h4>Fluxo de caixa livre (USD bi) <span class="badge" id="badge-FCL"></span></h4>{bar('FCL','')}</div></div></div>
<div class="page"><div class="note">Séries temporais multi-empresa — filtre empresas na barra lateral ou clique na legenda.</div>
{gridbar('evo')}
<div class="grid" id="grid-evo">{ts_grid}</div></div>
<div class="page"><div class="insight"><b>Efetivo total:</b> os RIs trimestrais não publicam
headcount por trimestre; exibimos âncoras anuais auditadas (31/dez, relatórios oficiais).
Série trimestral segue na fila de revisão.</div>
<div class="grid"><div class="cell"><h4>Efetivo por empresa (pessoas)</h4>{efetivo_bar}</div>
<div class="cell"><h4>Âncoras e períodos</h4>
<table><tr><th>Empresa</th><th>Período</th><th>Pessoas</th></tr>{efetivo_tab or '<tr><td colspan=3>Sem âncoras — rode: python app_main.py efetivo</td></tr>'}</table></div></div></div>
<div class="page"><h4>Catálogo de fontes ({len(fontes)}) · <b>{com_api}</b> com serviço JSON público</h4>
<div class="crud">
 <input type="hidden" id="f_id">
 <input id="f_emp" placeholder="empresa (ex.: PETROBRAS)" list="empreset">
 <datalist id="empreset">{"".join(f"<option value='{e}'>" for e in CATEGORICAS)}</datalist>
 <input id="f_doc" placeholder="nome do documento">
 <input id="f_url" placeholder="URL de origem" size="34">
 <select id="f_tipo"><option>PDF</option><option>XLSX</option><option>XLS</option><option>XLSM</option><option>CSV</option><option>TXT</option><option>DOCX</option><option>JSON</option><option>HTML</option></select>
 <input id="f_caminho" placeholder="pasta/arquivo em {pasta_raiz}/" size="30">
 <input id="f_api" placeholder="API JSON (opcional)" size="26">
 <select id="f_status"><option>PENDENTE</option><option>CATALOGADO</option><option>PROCESSADO</option><option>ERRO</option></select>
 <button class="sm" onclick="fSalvar()">💾 Salvar</button>
 <button class="sm" onclick="fNovo()">limpar</button>
 <input id="f_busca" placeholder="🔎 filtrar catálogo (empresa, doc, URL)" oninput="fonteFiltro()" size="34">
 <span class="note" id="f_msg">requer servidor: <b>python app_main.py web --serve</b></span>
</div>
<div class="twrap"><table class="paged" data-per="25"><tr><th>ID</th><th>Empresa</th><th>Documento</th><th>Ext</th><th>Pasta do sistema</th><th>API JSON</th><th>URL de origem</th><th>Download</th><th>Status</th><th>Ações</th></tr>{linhas}</table></div></div>
<div class="page" id="etl_body"><h4>Gestão e controle do ETL</h4>
<div class="note">O que foi processado, o que falhou (com a mensagem de erro), o que não teve
dado e quanto tempo cada fonte levou. Atualizado a cada execução do pipeline.</div>
<div class="kpis" id="etl_kpis" style="margin-top:8px"></div>
<div class="crud" style="margin-top:8px">
<select id="etl_status" onchange="etlFiltro()"><option value="">todos os status</option>
<option>PROCESSADO</option><option>SEM_DADOS</option><option>ERRO</option>
<option>NAO_PROCESSADO</option><option>NAO_BAIXADO</option><option>SEM_PARSER</option>
<option>PENDENTE</option></select>
<input id="etl_busca" placeholder="🔎 filtrar (empresa, documento, erro)" oninput="etlFiltro()" size="30">
<button class="sm" onclick="etlRecarregar()">⟳ recarregar</button></div>
<div class="twrap"><table class="paged" data-per="25">
<tr><th>ID</th><th>Empresa</th><th>Documento</th><th>Ext</th><th>Status</th><th>Extrações</th>
<th>Duração</th><th>Download</th><th>Processado em</th><th>Erro</th></tr>
<tbody id="etl_tbody"></tbody></table></div>
<h4 style="margin-top:10px">Histórico de execuções do pipeline</h4>
<div class="twrap"><table class="paged" data-per="25">
<tr><th>Início</th><th>Fim</th><th>Duração</th><th>Arquivos</th><th>Extrações</th><th>Cargas</th>
<th>PDFs pulados</th><th>Revisão</th><th>Erros</th><th>Detalhe</th></tr>
<tbody id="etl_hist"></tbody></table></div></div>
<div class="page"><h4>Alertas de qualidade ({len(qualidade['alertas'])})</h4>
<table class="paged" data-per="25"><tr><th>Tipo</th><th>Descrição</th><th>Severidade</th></tr>{alertas or '<tr><td colspan=3>Nenhum alerta.</td></tr>'}</table>
<h4>Fila de revisão ({len(qualidade['revisao'])})</h4>
<table class="paged" data-per="25"><tr><th>Empresa</th><th>Período</th><th>Rubrica</th><th>Motivo</th><th>Status</th></tr>{revisao or '<tr><td colspan=5>Fila vazia.</td></tr>'}</table></div>
</div>
<div class="fs" id="mail" onclick="if(event.target.id==='mail')mFechar()">
<div class="fs-inner" style="max-width:640px">
<div class="fs-head"><b>Enviar benchmark por e-mail</b>
<button class="sm" onclick="mFechar()">✕ fechar (Esc)</button></div>
<div class="note" id="mail_corpo" style="margin-bottom:6px"></div>
<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:11px">
<label>Para:</label><input id="mail_para" placeholder="destino@exemplo.com" size="26">
<label>Indicador:</label>
<select id="mail_rub">{"".join(f"<option value='{r['codigo']}'>{r['nome']}</option>" for r in INDICATORS if r["categoria"] == "Financeiro")}</select>
<button class="sm" id="mail_go" onclick="mEnviar()">✉ Gerar e-mail com o gráfico</button>
</div>
<div class="note" style="margin:6px 0">Anexos: <b>benchmark.html</b> (gráfico interativo), <b>.png</b> (imagem) e <b>.csv</b> (dados). Sem SMTP configurado o arquivo <b>.eml</b> é gerado em <b>data/outbox</b> — é só abrir e anexar/encaminhar.</div>
<div id="mail_prev" class="twrap"></div>
<div class="note" id="mail_msg" style="margin-top:6px"></div>
</div></div>
<div class="fs" id="fs" onclick="if(event.target.id==='fs')fSair()">
<div class="fs-inner"><div class="fs-head"><b id="fs-tit">Gráfico</b>
<span><button class="sm" onclick="fAjustar()">⤢ ajustar</button>
<button class="sm" onclick="fSair()">✕ fechar (Esc)</button></span></div>
<div id="fs-plot"></div></div></div>
<script>
const QALL = {_json.dumps(quarters_all)};
const SERIES = {_json.dumps(SERIES)};
const TAXAS = {_json.dumps(TAXAS)};
const INSIGHTS = {_json.dumps({q: AnalyticsController().insight_executivo(q) for q in quarters_all})};
const TRACES = {_json.dumps(traces)};
const CORES = {_json.dumps(CORES)};
const IDS = {_json.dumps({"bars": BAR_IDS, "ts": ts_ids})};
const BAR_TITLES = {_json.dumps({r["codigo"]: r["nome"] for r in INDICATORS if r["codigo"] in BAR_RUBS})};
const ORDEM = {_json.dumps(ORDEM_MATRIZ)};
const FONTES = {_json.dumps({str(f["id_fonte"]): {k: f.get(k) for k in (
    "nome_empresa", "nome_documento", "url_fonte", "tipo_arquivo", "caminho_local",
    "api_json", "status_processamento")} for f in fontes})};
const RUB_GRID = {{"RECEITA_LIQUIDA": "exec", "EBITDA_AJUSTADO": "exec", "LUCRO_LIQUIDO": "comp",
  "DIVIDA_LIQUIDA": "comp", "CAPEX": "exp", "DIVIDA_BRUTA": "exp", "LUCRO_BRUTO": "exp", "FCL": "exp"}};
const GRID_H = {{}};  // altura de plot por grade (preserva P/M/G ao trocar trimestre)
let MOEDA = 'USD';
function taxa(q){{return TAXAS[q] || 5.2;}}
function conv(v, q){{return MOEDA === 'BRL' ? v * taxa(q) : v;}}
function fmt(v){{return MOEDA === 'BRL'
  ? v.toLocaleString('pt-BR', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})
  : v.toFixed(2);}}
function uni(){{return MOEDA === 'BRL' ? 'BRL bi' : 'USD bi';}}
function tab(i){{
  [...document.querySelectorAll('.tab')].forEach((b,j)=>b.classList.toggle('on',j===i));
  [...document.querySelectorAll('.page')].forEach((p,j)=>{{
    p.classList.toggle('on',j===i);
    if(j===i) p.querySelectorAll('.plotly-graph-div').forEach(el=>{{try{{Plotly.Plots.resize(el);}}catch(e){{}}}});
  }});
  if(i===6) etlCarregar();   // aba "Gestao ETL" busca o status ao vivo
  autoFit(); urlSync();
}}
function toggleMenu(){{document.body.classList.toggle('menu-off');}}
function fAjustar(){{document.querySelectorAll('.plotly-graph-div').forEach(el=>{{
  try{{Plotly.Plots.resize(el);}}catch(e){{}}}});}}
function autoFit(){{
  // Cada grafico ocupa exatamente o espaço livre da sua celula.
  // Dois bugs corrigidos aqui:
  //  1) Plotly.Plots.resize() NAO encolhe o svg quando o layout tem altura fixa;
  //     por isso medimos a celula e passamos width/height explicitos no relayout
  //     (era isso que deixava o grafico largo e cortado ao passar p/ 4 colunas).
  //  2) Celulas de abas ocultas (clientWidth=0) nao podem ser redimensionadas.
  document.querySelectorAll('.cell').forEach(cell=>{{
    const el=cell.querySelector('.plotly-graph-div'); if(!el||!el.data) return;
    if(!cell.clientWidth) return;
    const h4=cell.querySelector('h4');
    const w=el.clientWidth||cell.clientWidth-18;
    const h=cell.clientHeight-(h4?h4.offsetHeight+6:0)-18;
    if(w>80&&h>150){{el.style.height=h+'px';
      try{{Plotly.relayout(el,{{width:w,height:h}});}}catch(e){{}}
      try{{Plotly.Plots.resize(el);}}catch(e){{}}
    }}
  }});
}}
let _roT=null;
function observarCelulas(){{
  if(typeof ResizeObserver==='undefined') return;
  const ro=new ResizeObserver(()=>{{clearTimeout(_roT);_roT=setTimeout(autoFit,60);}});
  document.querySelectorAll('.cell').forEach(c=>ro.observe(c));
}}
function fitAll(gid){{const g=document.getElementById('grid-'+gid);
  (g?g.querySelectorAll('.plotly-graph-div'):document.querySelectorAll('.plotly-graph-div'))
    .forEach(el=>{{try{{Plotly.Plots.resize(el);}}catch(e){{}}}});}}
let _fsEl=null,_fsParent=null,_fsNext=null;
function fAbrir(el){{
  const box=document.getElementById('fs'); if(!box||!el) return;
  _fsEl=el; _fsParent=el.parentElement; _fsNext=el.nextSibling;
  const tit=(_fsParent.querySelector('h4')||{{}}).textContent||'Gráfico';
  document.getElementById('fs-tit').textContent=tit;
  document.getElementById('fs-plot').appendChild(el);
  box.classList.add('on');
  try{{Plotly.Plots.resize(el);Plotly.relayout(el,{{height:Math.max(320,window.innerHeight-140)}});}}catch(e){{}}
}}
function fSair(){{
  if(document.getElementById('mail').classList.contains('on')){{mFechar();return;}}
  const box=document.getElementById('fs'); if(!box||!_fsEl) return;
  box.classList.remove('on');
  if(_fsNext&&_fsNext.parentElement===_fsParent) _fsParent.insertBefore(_fsEl,_fsNext);
  else _fsParent.appendChild(_fsEl);
  const el=_fsEl; _fsEl=null; _fsParent=null; _fsNext=null;
  try{{Plotly.Plots.resize(el);}}catch(e){{}}
  autoFit();
}}
function fFullscreenFirst(){{
  const cell=document.querySelector('.page.on .cell .plotly-graph-div');
  if(cell) fAbrir(cell); else fMsg('nenhum grafico na aba atual',false);
}}
function fonteFiltro(){{
  const q=(document.getElementById('f_busca')||{{}}).value.toLowerCase().trim();
  document.querySelectorAll('.page table.paged tbody tr, .page table.paged tr').forEach((tr,i)=>{{
    if(i===0) return;
    tr.style.display=(!q||tr.textContent.toLowerCase().includes(q))?'':'none';
  }});
}}
function emailGrafico(){{
  const txt=document.getElementById('insight-txt')?document.getElementById('insight-txt').textContent:'';
  if(txt) document.getElementById('mail_corpo').textContent=txt;
  mAbrir();
}}
/* ---------- envio do grafico por e-mail (API /api/email) ---------- */
let _mailRub='RECEITA_LIQUIDA',_mailDados=[];
function mMsg(t,ok){{const m=document.getElementById('mail_msg');
  if(m){{m.textContent=t;m.style.color=ok?'var(--acc)':'#dc2626';}}}}
function QPER(){{const s=document.getElementById('qsel');return s?s.value:QALL[QALL.length-1];}}
function mAbrir(){{
  const box=document.getElementById('mail'); if(!box) return;
  box.classList.add('on');
  _mailRub=document.getElementById('mail_rub').value;
  _mailDados=[]; mMsg('carregando preview...',true);
  fetch('/api/email?rubrica='+encodeURIComponent(_mailRub)+'&periodo='+encodeURIComponent(QPER()))
    .then(r=>r.json()).then(j=>{{
      _mailDados=j.dados||[];
      document.getElementById('mail_prev').innerHTML = _mailDados.length
        ? '<table><tr><th>Empresa</th><th>USD bi</th></tr>'+_mailDados.map(d=>
            '<tr><td>'+d.empresa+'</td><td align="right">'+d.valor.toLocaleString('pt-BR')+
            '</td></tr>').join('')+'</table>'
        : "<div class='note'>sem dados para esta rubrica/per&iacute;odo</div>";
      mMsg(_mailDados.length+' empresas · anexos: HTML + PNG + CSV',_mailDados.length>0);
    }}).catch(()=>mMsg('API indispon&iacute;vel — rode com --serve',false));
}}
function mFechar(){{const b=document.getElementById('mail');if(b)b.classList.remove('on');}}
function mEnviar(){{
  const para=document.getElementById('mail_para').value.trim();
  if(!para||para.indexOf('@')<0){{mMsg('informe um e-mail v&aacute;lido',false);return;}}
  const btn=document.getElementById('mail_go'); btn.disabled=true;
  mMsg('gerando .eml com o gr&aacute;fico...',true);
  fetch('/api/email',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{para:para,rubrica:_mailRub,periodo:QPER()}})}})
   .then(r=>r.json().then(j=>({{ok:r.ok,j}})))
   .then(({{ok,j}})=>{{
     btn.disabled=false;
     if(!ok){{mMsg(j.erro||'erro',false);return;}}
     mMsg('OK: '+(j.resultado||'')+' · anexos: '+(j.anexos||[]).join(', '),true);
     mFechar();
   }}).catch(()=>{{btn.disabled=false;mMsg('falha de rede',false);}});
}}
function fMsg(t,ok){{const m=document.getElementById('f_msg');if(m){{m.textContent=t;m.style.color=ok?'var(--acc)':'#dc2626';}}}}
async function fApi(method,body){{
  try{{const r=await fetch('/api/fontes',{{method:method,headers:{{'Content-Type':'application/json'}},
      body:body?JSON.stringify(body):undefined}});const j=await r.json();
    if(!r.ok){{fMsg(j.erro||'erro '+r.status,false);return null;}} return j;}}
  catch(e){{fMsg('API indisponivel — rode com --serve',false);return null;}}
}}
function fCampo(id){{return (document.getElementById(id).value||'').trim();}}
function fDados(){{return {{nome_empresa:fCampo('f_emp'),nome_documento:fCampo('f_doc'),
  url_fonte:fCampo('f_url'),tipo_arquivo:fCampo('f_tipo'),caminho_local:fCampo('f_caminho'),
  api_json:fCampo('f_api'),status_processamento:fCampo('f_status')}};}}
function fNovo(){{['f_id','f_emp','f_doc','f_url','f_caminho','f_api'].forEach(i=>document.getElementById(i).value='');
  fMsg('formulario limpo',true);}}
function fSalvar(){{
  const d=fDados(), id=fCampo('f_id');
  if(!d.nome_empresa||!d.url_fonte||!d.tipo_arquivo){{fMsg('empresa, URL e tipo sao obrigatorios',false);return;}}
  const acao = id ? fApi('PUT',Object.assign({{id_fonte:parseInt(id)}},d))
                  : fApi('POST',d);
  acao && setTimeout(()=>location.reload(),400);
  acao && fMsg(id?'atualizado':'criado',true);
}}
function fEditar(id){{
  const f=(FONTES[id]||{{}});
  document.getElementById('f_id').value=id;
  document.getElementById('f_emp').value=f.nome_empresa||'';
  document.getElementById('f_doc').value=f.nome_documento||'';
  document.getElementById('f_url').value=f.url_fonte||'';
  document.getElementById('f_tipo').value=f.tipo_arquivo||'PDF';
  document.getElementById('f_caminho').value=f.caminho_local||'';
  document.getElementById('f_api').value=(f.api_json||'').startsWith('http')?f.api_json:'';
  document.getElementById('f_status').value=f.status_processamento||'PENDENTE';
  fMsg('editando fonte #'+id,true);
}}
function fExcluir(id){{
  if(!confirm('Excluir a fonte #'+id+'? Os fatos vinculados permanecem (id_fonte = NULL).')) return;
  fApi('DELETE',{{id_fonte:id}}) && setTimeout(()=>location.reload(),400);
}}
function gridCols(id,n,btn){{const g=document.getElementById('grid-'+id);if(!g||!n)return;
  g.style.setProperty('--cols',n);
  if(btn){{[...btn.parentElement.querySelectorAll('button')].slice(0,4).forEach(b=>b.classList.remove('on'));
    btn.classList.add('on');}}
  g.querySelectorAll('.plotly-graph-div').forEach(el=>{{try{{Plotly.Plots.resize(el);}}catch(e){{}}}});
  autoFit(); urlSync();
}}
function gridH(id,h,btn){{const g=document.getElementById('grid-'+id);if(!g)return;
  g.style.setProperty('--cellh',h+'px'); GRID_H[id]=h-70;
  if(btn){{[...btn.parentElement.querySelectorAll('button')].slice(4).forEach(b=>b.classList.remove('on'));
    btn.classList.add('on');}}
  autoFit(); urlSync();
}}
function fitAll(gid){{const g=document.getElementById('grid-'+gid);
  (g?g.querySelectorAll('.plotly-graph-div'):document.querySelectorAll('.plotly-graph-div'))
    .forEach(el=>{{try{{Plotly.Plots.resize(el);}}catch(e){{}}}});autoFit();}}
let _rz=null;
window.addEventListener('resize',()=>{{clearTimeout(_rz);_rz=setTimeout(()=>{{
  document.querySelectorAll('.plotly-graph-div').forEach(el=>{{try{{Plotly.Plots.resize(el);}}catch(e){{}}}});
}},200);}});
function chartTheme(){{return document.body.getAttribute('data-theme')==='light'?'plotly':'plotly_dark';}}  // kept p/ compat
function setTheme(t){{
  document.body.setAttribute('data-theme',t);try{{localStorage.setItem('petro-theme',t);}}catch(e){{}}
  temaPlot();
  // barras sao re-renderizadas (barLayout ja monta o layout com as cores do tema)
  const sel=document.getElementById('qsel');
  try{{applyQuarter(sel?sel.value:QALL[QALL.length-1]);}}catch(e){{}}
  urlSync();
}}
function initTheme(){{let t=null;try{{t=localStorage.getItem('petro-theme');}}catch(e){{}}
  if(t==='light'||t==='dark'){{document.body.setAttribute('data-theme',t);
    document.querySelectorAll('.plotly-graph-div').forEach(el=>{{try{{Plotly.relayout(el,{{template:chartTheme()}});}}catch(e){{}}}});}}
}}
function paginate(tbl){{
  const rows=[...tbl.querySelectorAll('tr')].slice(1); if(rows.length<=10) return;
  let per=parseInt(tbl.dataset.per||'25',10), page=0;
  const bar=document.createElement('div'); bar.className='pager'; tbl.after(bar);
  function draw(){{
    const n=Math.max(1,Math.ceil(rows.length/per)); page=Math.min(Math.max(page,0),n-1);
    rows.forEach((r,i)=>r.style.display=(i>=page*per&&i<(page+1)*per)?'':'none');
    bar.innerHTML='';
    const mk=(t,fn,dis)=>{{const b=document.createElement('button');b.textContent=t;b.onclick=fn;b.disabled=!!dis;bar.appendChild(b);}};
    mk('◀',()=>{{page--;draw();}},page===0);
    const s=document.createElement('span');s.textContent=`Página ${{page+1}} de ${{n}} · ${{rows.length}} linhas`;bar.appendChild(s);
    mk('▶',()=>{{page++;draw();}},page>=n-1);
    const sel=document.createElement('select');[10,25,50,100].forEach(v=>{{const o=document.createElement('option');o.value=v;o.textContent=v+'/pág';if(v===per)o.selected=true;sel.appendChild(o);}});
    sel.onchange=()=>{{per=parseInt(sel.value,10);page=0;draw();}};bar.appendChild(sel);
  }}
  draw();
}}
document.addEventListener('DOMContentLoaded',()=>{{
  initTheme();
  document.querySelectorAll('table.paged').forEach(paginate);
  document.querySelectorAll('.cell').forEach(c=>c.addEventListener('dblclick',ev=>{{
    if(ev.target.closest('.plotly-graph-div')) fAbrir(ev.target.closest('.plotly-graph-div'));}}));
  autoFit();
  observarCelulas();
  const q0=document.getElementById('qsel')?document.getElementById('qsel').value:QALL[QALL.length-1];
  applyQuarter(q0);   // popula badges de media e alinha matriz/KPIs no load
  aplicarUrl();      // deep-link: ?tema=dark&tab=2&cols=4&q=2026Q2
}});
function aplicarUrl(){{
  const p=new URLSearchParams(location.search);
  if(p.get('tema')==='dark'||p.get('tema')==='light') setTheme(p.get('tema'));
  if(p.get('tab')) tab(parseInt(p.get('tab'),10)||0);
  const nc=parseInt(p.get('cols'),10);
  if(nc>=1&&nc<=4){{
    gridCols('exec',nc,null);   // deep-link nao tem botao: marca o certo manualmente
    const barra=document.querySelectorAll('.gridbar')[0];
    if(barra){{[...barra.querySelectorAll('button')].forEach(b=>{{
      if(b.textContent===String(nc)) b.classList.add('on'); else b.classList.remove('on');
    }});}}
  }}
  const q=p.get('q'), sel=document.getElementById('qsel');
  if(q&&sel&&QALL.includes(q)) sel.value=q;
}}
function urlSync(){{
  try{{const p=new URLSearchParams();
    p.set('tema',chartTheme()==='plotly'?'light':'dark');
    p.set('tab',String([...document.querySelectorAll('.tab')].findIndex(b=>b.classList.contains('on'))));
    const q=document.getElementById('qsel'); if(q) p.set('q',q.value);
    history.replaceState(null,'','?'+p.toString());}}catch(e){{}}
}}
window.addEventListener('resize',()=>{{clearTimeout(_rz);_rz=setTimeout(autoFit,220);}});
document.addEventListener('keydown',ev=>{{
  if(ev.key==='Escape') fSair();
  if(ev.target.tagName==='INPUT'||ev.target.tagName==='SELECT') return;
  if(ev.key>='1'&&ev.key<='8') tab(parseInt(ev.key,10)-1);
  if(ev.key==='f'||ev.key==='F') fFullscreenFirst();
  if(ev.key==='t'||ev.key==='T') setTheme(chartTheme()==='plotly'?'light':'dark');
}});
function plotColors(){{
  const d=document.body.getAttribute('data-theme')==='dark';
  return {{paper:d?'#12151c':'#ffffff', plot:d?'#12151c':'#ffffff', font:d?'#e2e8f0':'#0f172a',
          grid:d?'#2d3748':'#e2e8f0', axis:d?'#94a3b8':'#64748b', line:d?'#94a3b8':'#888888'}};
}}
function temaPlot(){{
  // troca de tema SEM depender de template: define cores explicitamente em todos
  // os graficos (relayout de 'template' nao era aplicado pelo Plotly)
  const c=plotColors();
  document.querySelectorAll('.plotly-graph-div').forEach(el=>{{try{{Plotly.relayout(el,{{
    'paper_bgcolor':c.paper,'plot_bgcolor':c.plot,'font.color':c.font,'title.font.color':c.font,
    'xaxis.gridcolor':c.grid,'yaxis.gridcolor':c.grid,'xaxis.zerolinecolor':c.grid,
    'yaxis.zerolinecolor':c.grid,'xaxis.tickfont.color':c.axis,'yaxis.tickfont.color':c.axis,
    'xaxis.title.font.color':c.axis,'yaxis.title.font.color':c.axis,
    'hoverlabel.bgcolor':c.paper,'hoverlabel.bordercolor':c.grid,'hoverlabel.font.color':c.font,
    'legend.font.color':c.font,'shapes[0].line.color':c.line
  }});}}catch(e){{}}}});
}}
function barLayout(t,h){{const c=plotColors();return {{
  title:{{text:t,font:{{color:c.font,size:13}}}},
  yaxis:{{title:c.unit||'USD bi',automargin:true,rangemode:'tozero',gridcolor:c.grid,
          zerolinecolor:c.grid,tickfont:{{size:10,color:c.axis}},titlefont:{{color:c.axis}}}},
  xaxis:{{automargin:true,tickangle:-20,gridcolor:c.grid,zerolinecolor:c.grid,
          tickfont:{{size:10,color:c.axis}}}},
  height:h||340,margin:{{t:56,b:58,l:56,r:20}},
  paper_bgcolor:c.paper,plot_bgcolor:c.plot,font:{{size:11,color:c.font}},
  hovermode:'closest',hoverlabel:{{bgcolor:c.paper,bordercolor:c.grid,font:{{color:c.font}}}},
  template:'none',bargap:0.32,showlegend:false
}};}}
function withMean(t,vals,rub){{const m=vals.reduce((a,b)=>a+b,0)/vals.length;
  const L=barLayout(t,GRID_H[RUB_GRID[rub]]||340);
  L.shapes=[{{type:'line',x0:0,x1:1,xref:'paper',y0:m,y1:m,line:{{dash:'dash',color:'gray'}}}}];
  const badge=document.getElementById('badge-'+rub);   // media no cabecalho: nunca e cortada
  if(badge) badge.textContent='média '+m.toFixed(1);
  return L;}}
function applyQuarter(q){{
  document.querySelectorAll('.qper').forEach(e=>e.textContent=q);
  document.getElementById('insight-txt').textContent=INSIGHTS[q]||'Sem dados para o período.';
  renderMatrix(q); renderKpis(q);
  for(const rub of Object.keys(BAR_TITLES)){{
    const d=SERIES[rub]||{{}}; const emps=Object.keys(d).filter(e=>d[e][q]!==undefined);
    const el=document.getElementById(IDS.bars[rub]);
    if(!emps.length||!el) continue;
    Plotly.react(el,[{{x:emps,y:emps.map(e=>conv(d[e][q],q)),type:'bar',
      marker:{{color:emps.map(e=>(CORES[e]||'#4a90d9')),line:{{color:'#fff',width:1.5}}}},
      text:emps.map(e=>fmt(conv(d[e][q],q))),textposition:'outside',cliponaxis:true,
      hovertemplate:'%{{x}}: %{{y:,.2f}} '+uni()+'<extra></extra>'}}],
      withMean(BAR_TITLES[rub]+' ('+uni()+')', emps.map(e=>conv(d[e][q],q)), rub));
  }}
}}
function renderMatrix(q){{
  const cols=Object.keys(CORES).filter(e=>ORDEM.some(r=>(SERIES[r]||{{}})[e]!==undefined&&(SERIES[r][e][q]!==undefined)));
  let h=`<table><tr><th>Indicador (${{uni()}}) \\ Empresa</th>`+cols.map(e=>`<th>${{e}}</th>`).join('')+'</tr>';
  for(const rub of ORDEM){{
    h+='<tr><th>'+rub+'</th>';
    for(const e of cols){{
      const v=((SERIES[rub]||{{}})[e]||{{}})[q];
      h+= v===undefined ? "<td class='note'>—</td>" : `<td>${{fmt(conv(v,q))}}</td>`;
    }}
    h+='</tr>';
  }}
  h+=`</table><div class='note'>Matriz comparativa ${{q}} · — = sem dado</div>`;
  document.getElementById('matriz-wrap').innerHTML=h;
}}
function renderKpis(q){{
  document.querySelectorAll('#kpis .kpi').forEach(card=>{{
    const el=card.querySelector('.kpi-v'), sub=card.querySelector('.kpi-s');
    const rub=el.dataset.kpi;
    if(rub==='MARGEM'){{
      const r=((SERIES.RECEITA_LIQUIDA||{{}}).PETROBRAS||{{}})[q];
      const e=((SERIES.EBITDA_AJUSTADO||{{}}).PETROBRAS||{{}})[q];
      if(r) el.textContent=((e||0)/r*100).toFixed(1)+'%';
      if(sub) sub.textContent=q;
      return;
    }}
    const d=SERIES[rub]||{{}};
    let top=null; for(const e of Object.keys(d)){{ if(d[e][q]!==undefined&&(top===null||d[e][q]>d[top][q])) top=e; }}
    if(top!==null){{ el.textContent=fmt(conv(d[top][q],q))+' '+(MOEDA==='BRL'?'BRL bi':'USD bi'); }}
    if(sub) sub.textContent=top+' · '+q;
  }});
}}
function setMoeda(m){{
  MOEDA=m;
  const q=document.getElementById('qsel')?document.getElementById('qsel').value:QALL[QALL.length-1];
  document.getElementById('ptax').textContent='R$ '+taxa(q).toFixed(2);
  applyQuarter(q);
  for(const rub of Object.keys(TRACES)){{
    const el=document.getElementById(IDS.ts[rub]); if(!el||!el.data) continue;
    TRACES[rub].forEach((emp,idx)=>{{
      const vals=(SERIES[rub][emp]||{{}});
      const ys=QALL.map(p=>{{const v=vals[p];return v===undefined?null:conv(v,p);}});
      Plotly.restyle(el,{{y:[ys]}},[idx]);
    }});
    Plotly.relayout(el,{{yaxis:{{title:{{text:uni()}}}}}});
  }}
  renderKpis(q);
}}
function applyCompanies(){{
  const on=[...document.querySelectorAll('.empchk')].filter(c=>c.checked).map(c=>c.value);
  for(const rub of Object.keys(TRACES)){{
    const el=document.getElementById(IDS.ts[rub]); if(!el||!el.data) continue;
    TRACES[rub].forEach((emp,idx)=>{{Plotly.restyle(el,{{visible:on.includes(emp)}},[idx]);}});
  }}
}}
/* ---------- gestao do ETL: status por fonte ---------- */
async function etlCarregar(){{
  const box=document.getElementById('etl_body');
  if(!box) return;
  try{{
    const r=await fetch('/api/etl'); const j=await r.json();
    const s=j.resumo;
    document.getElementById('etl_kpis').innerHTML=[
      ['Fontes',s.total,''],['Processadas',s.processadas,'ok'],['Com erro',s.com_erro,'bad'],
      ['Sem dados',s.sem_dados,'warn'],['Não processadas',s.nao_processadas,''],
      ['Não baixadas',s.nao_baixados,''],
      ['Duração total',s.duracao_total_ms!=null?(s.duracao_total_ms/1000).toFixed(1)+' s':'—',''],
      ['Duração média',s.duracao_media_ms!=null?(s.duracao_media_ms/1000).toFixed(2)+' s':'—',''],
      ['Extrações',s.extracoes_total,''],
      ['Última execução',s.ultima_execucao?s.ultima_execucao.slice(0,19).replace('T',' '):'—',''],
      ['Execuções',s.total_execucoes,''],['Cargas na última',s.ultimas_cargas!=null?s.ultimas_cargas:'—','']
    ].map(([t,v,k])=>`<div class='kpi'><div class='kpi-t'>${{t}}</div>
        <div class='kpi-v' style='font-size:15px;color:${{k==='bad'?'#dc2626':k==='ok'?'var(--acc)':k==='warn'?'#b45309':'inherit'}}'>${{v}}</div></div>`).join('');
    const linhas=(j.fontes||[]).map(f=>
      `<tr data-st="${{f.status_processamento}}"><td>${{f.id_fonte}}</td><td>${{f.nome_empresa}}</td>
       <td>${{(f.nome_documento||'').slice(0,40)}}</td><td>${{f.extensao||''}}</td>
       <td><span class='status ${{f.status_processamento}}'>${{f.status_processamento}}</span></td>
       <td>${{f.n_extracoes!=null?f.n_extracoes:''}}</td>
       <td>${{f.duracao_ms!=null?(f.duracao_ms/1000).toFixed(2)+'s':''}}</td>
       <td>${{(f.data_download||'').slice(0,19)}}</td>
       <td>${{(f.data_processamento||'').slice(0,19)}}</td>
       <td class='err'>${{(f.erro||'').slice(0,120)}}</td></tr>`).join('');
    document.getElementById('etl_tbody').innerHTML=linhas||"<tr><td colspan=10>nada</td></tr>";
    document.getElementById('etl_hist').innerHTML=(j.execucoes||[]).map(e=>
      `<tr><td>${{e.inicio_em}}</td><td>${{e.fim_em||''}}</td><td>${{e.duracao_ms!=null?(e.duracao_ms/1000).toFixed(2)+'s':''}}</td>
       <td>${{e.arquivos_processados}}</td><td>${{e.extracoes}}</td><td>${{e.cargas}}</td>
       <td>${{e.pulados_pdf}}</td><td>${{e.revisao}}</td><td>${{e.erros}}</td>
       <td>${{(e.detalhe||'').slice(0,80)}}</td></tr>`).join('');
    etlFiltro();
  }}catch(e){{box.innerHTML="<div class='note'>API indisponível — rode com --serve</div>";}}
}}
function etlFiltro(){{
  const st=document.getElementById('etl_status').value;
  const q=(document.getElementById('etl_busca').value||'').toLowerCase().trim();
  document.querySelectorAll('#etl_tbody tr').forEach(tr=>{{
    const okSt=!st||tr.dataset.st===st;
    const okQ=!q||tr.textContent.toLowerCase().includes(q);
    tr.style.display=(okSt&&okQ)?'':'none';
  }});
}}
function etlRecarregar(){{etlCarregar();}}
</script>
</body></html>"""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return str(destino)
