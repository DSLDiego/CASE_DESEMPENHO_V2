"""Envio de graficos/quadros por e-mail (SMTP via env; dry-run gera .eml).

Anexos: CSV (dados), HTML autocontido com o grafico Plotly interativo e PNG
quando o Kaleido estiver instalado (fallback: so CSV+HTML, sem dependencia nova).

Uso:
  python app_main.py email --para dest@exemplo.com --rubrica RECEITA_LIQUIDA --periodo 2026Q2
Env (somente p/ envio real): SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_DE.
"""
from __future__ import annotations

import csv
import io
import json
import os
import smtplib
from email.message import EmailMessage
from email.utils import formatdate

import config
from config import DATA_DIR
from models.database import DatabaseManager
from models.repositories import FatoRepository

CORES = dict(config.PALETA)  # mesma paleta do painel (fonte unica de verdade)


def _rotulo(rubrica: str) -> str:
    """Nome amigavel do indicador (EBITDA_AJUSTADO -> 'EBITDA ajustado')."""
    try:
        from config import INDICATORS
        for i in INDICATORS:
            if i["codigo"] == rubrica:
                return i["nome"]
    except Exception:
        pass
    return rubrica.replace("_", " ").title()


def _html_grafico(rubrica: str, periodo: str, linhas: list[dict],
                  proj: list[dict] | None = None) -> str:
    """HTML autocontido: tabela + grafico de barras Plotly (CDN).

    Com `proj`, acrescenta a faixa de IC95 de cada empresa como barra de erro:
    quem lê o gráfico fora do sistema não tem como saber que o número tem
    intervalo — e é o intervalo que diz se ele serve para decidir (M3.15).
    """
    from html import escape
    dados = [[r["nome_empresa"], round(r["valor"], 2)] for r in linhas]
    rotulos = [d[0] for d in dados]
    valores = [d[1] for d in dados]
    cores = [CORES.get(e, "#4a90d9") for e in rotulos]
    linhas_html = "".join(
        f"<tr><td>{escape(rotulos[i])}</td><td align='right'>{valores[i]:,.2f}</td></tr>"
        for i in range(len(rotulos)))
    traces_extra = ""
    bloco_proj = ""
    legenda = "false"
    if proj:
        dados_proj = [[p["nome_empresa"], round(p["valor"], 2),
                       round(p["intervalo_inf"], 2), round(p["intervalo_sup"], 2),
                       p["periodo_projetado"]] for p in sorted(proj, key=lambda x: x["nome_empresa"])]
        # O IC95 vira barra de erro (error_y): mostra que o número tem faixa, e não
        # um valor solto. `customdata` carrega o IC para o tooltip — sem ele o
        # hover mostraria só o ponto e esconderia justamente o intervalo.
        traces_extra = (",{type:'scatter',mode:'markers',name:'Projetado (IC 95%)',"
                      "x:proj_ic.map(function(p){return p[0];}),"
                      "y:proj_ic.map(function(p){return p[1];}),"
                      "error_y:{type:'data',symmetric:false,"
                      "array:proj_ic.map(function(p){return p[3]-p[1];}),"
                      "arrayminus:proj_ic.map(function(p){return p[1]-p[2];}),"
                      "color:'#D55E00',thickness:1.5,width:4},"
                      "customdata:proj_ic.map(function(p){return p[2]+' a '+p[3];}),"
                      "marker:{color:'#D55E00',size:7,symbol:'diamond'},"
                      "hovertemplate:'%{x}: %{y:,.2f}<br>IC 95%: %{customdata}<extra>projeção</extra>'}")
        linhas_proj = "".join(
            f"<tr><td>{escape(p[0])}</td><td align='right'>{p[1]:,.2f}</td>"
            f"<td align='right'>{p[2]:,.2f} … {p[3]:,.2f}</td><td>{escape(str(p[4]))}</td></tr>"
            for p in dados_proj)
        bloco_proj = (f"<h2>Projeção {escape(str(dados_proj[0][4]))} (IC 95%)</h2>"
                      "<table><tr><th>Empresa</th><th>Projetado</th>"
                      "<th>IC 95%</th><th>Período</th></tr>"
                      f"{linhas_proj}</table>"
                      "<p><small>Projeção não é fato publicado — método escolhido "
                      "por backtesting, intervalo pela dispersão dos erros.</small></p>")
        legenda = "true"
    ic = ("var proj_ic=" + json.dumps(
        [[p["nome_empresa"], round(p["valor"], 2), round(p["intervalo_inf"], 2),
          round(p["intervalo_sup"], 2), p["periodo_projetado"]]
         for p in sorted(proj, key=lambda x: x["nome_empresa"])]) + ";") if proj else ""
    return f"""<!DOCTYPE html><html lang="pt-BR"><meta charset="utf-8">
<title>PetroAnalytics {escape(_rotulo(rubrica))} {escape(periodo)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>body{{font-family:Segoe UI,Arial,sans-serif;font-size:13px;color:#0f172a;margin:16px}}
h1{{font-size:16px}}h2{{font-size:14px;margin-top:18px}}
table{{border-collapse:collapse;margin-top:12px}}
td,th{{border:1px solid #e2e8f0;padding:4px 8px}}</style>
<h1>PetroAnalytics — {escape(_rotulo(rubrica))} em {escape(periodo)} (USD bi)</h1>
<div id="g" style="width:640px;height:340px"></div>
<table><tr><th>Empresa</th><th>USD bi</th></tr>{linhas_html}</table>
{bloco_proj}
<p><small>Fonte: base comparativa PetroAnalytics (RI + SEC EDGAR). CSV em anexo.</small></p>
<script>
var d={dados!r}, r={rotulos!r}, c={cores!r}; {ic}
Plotly.newPlot('g',[{{type:'bar',x:r,y:d.map(function(v){{return v[1];}}),
  text:d.map(function(v){{return v[1].toFixed(2);}}),textposition:'outside',
  marker:{{color:c}},cliponaxis:true,
  hovertemplate:'%{{x}}: %{{y:,.2f}} USD bi<extra>real</extra>'}}]{traces_extra},
 {{title:{(_rotulo(rubrica) + ' ' + periodo)!r},margin:{{t:50,b:60,l:55,r:20}},
   yaxis:{{rangemode:'tozero',automargin:true}},xaxis:{{automargin:true,tickangle:-20}},
   template:'plotly',uniformtext:{{minsize:9}},showlegend:{legenda}}},
  {{responsive:true}});
</script></html>"""


def _png_grafico(rubrica: str, periodo: str, linhas: list[dict]) -> bytes | None:
    """PNG estatico via Kaleido (opcional)."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None
    fig = go.Figure(go.Bar(x=[r["nome_empresa"] for r in linhas],
                           y=[r["valor"] for r in linhas],
                           marker_color=[CORES.get(r["nome_empresa"], "#4a90d9") for r in linhas],
                           text=[f"{r['valor']:.2f}" for r in linhas], textposition="outside"))
    fig.update_layout(title=f"{_rotulo(rubrica)} {periodo} (USD bi)", template="plotly",
                      margin=dict(t=50, b=60, l=55, r=20))
    try:
        return fig.to_image(format="png", width=900, height=460, scale=2)
    except Exception:
        return None  # Kaleido ausente: segue com HTML+CSV


def _projecao_intervalo(rubrica: str, periodo: str,
                        db: DatabaseManager | None = None) -> list[dict]:
    """IC95 da projeção de cada empresa para o trimestre seguinte ao `periodo` (M3.15).

    Sem intervalo no e-mail, o leitor do número projetado não sabe o quanto ele
    pode variar — e é o intervalo que diz se o número serve para decidir.
    """
    from models.repositories import ProjectionRepository
    from workers.forecast import proximos
    alvo = proximos([periodo], 1)[0]
    return [p for p in ProjectionRepository(db or DatabaseManager()).listar(rubrica=rubrica)
            if p["periodo_projetado"] == alvo]


def _bloco_projection(linhas_proj: list[dict]) -> list[str]:
    """Bloco textual do IC95, uma linha por empresa, em ordem de período projetado."""
    if not linhas_proj:
        return []
    bloco = ["", "Projeção (IC 95%) — método e confiança:"]
    for p in sorted(linhas_proj, key=lambda x: x["nome_empresa"]):
        bloco.append(f"  {p['nome_empresa']}: {p['valor']:,.2f} "
                     f"[{p['intervalo_inf']:,.2f} … {p['intervalo_sup']:,.2f}] "
                     f"· {p['periodo_projetado']} · {p['metodo']} · "
                     f"confiança {p['confianca']:.2f}")
    bloco.append("  Projeção não é fato publicado: vive em tb_projecao e serve "
                 "para cenário, não para relatório.")
    return bloco


def montar_email(para: str, rubrica: str, periodo: str,
                 db: DatabaseManager | None = None,
                 anexar_grafico: bool = True,
                 com_projection: bool = True) -> EmailMessage:
    db = db or DatabaseManager()
    fatos = FatoRepository(db)
    linhas = [r for r in fatos.matriz(periodo) if r["rubrica_padronizada"] == rubrica]
    linhas.sort(key=lambda r: r["valor"], reverse=True)
    proj = _projecao_intervalo(rubrica, periodo, db) if com_projection else []
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["empresa", "periodo", "rubrica", "valor_usd_bi", "fonte"])
    for r in linhas:
        writer.writerow([r["nome_empresa"], r["periodo"], rubrica,
                         f"{r['valor']:.4f}", r.get("url_fonte") or ""])
    corpo = [f"PetroAnalytics PoC — {_rotulo(rubrica)} em {periodo} (USD bi):", ""]
    corpo += [f"  {r['nome_empresa']}: {r['valor']:,.2f}" for r in linhas]
    corpo += ["", f"Fonte: base comparativa ({len(linhas)} empresas). Ver painel e catálogo."]
    corpo += _bloco_projection(proj)
    if anexar_grafico and linhas:
        corpo += ["", "Em anexo: benchmark.html (gráfico interativo), PNG e CSV."]
    if proj:
        writer.writerow([])
        writer.writerow(["empresa", "periodo_projetado", "metodo", "valor_projetado",
                         "intervalo_inf", "intervalo_sup", "confianca"])
        for p in sorted(proj, key=lambda x: x["nome_empresa"]):
            writer.writerow([p["nome_empresa"], p["periodo_projetado"], p["metodo"],
                             f"{p['valor']:.4f}", f"{p['intervalo_inf']:.4f}",
                             f"{p['intervalo_sup']:.4f}", f"{p['confianca']:.2f}"])
    msg = EmailMessage()
    msg["Subject"] = f"[PetroAnalytics] {_rotulo(rubrica)} {periodo}"
    msg["From"] = os.environ.get("SMTP_DE", "petroanalytics@exemplo.com")
    msg["To"] = para
    msg["Date"] = formatdate(localtime=True)
    msg.set_content("\n".join(corpo))
    if anexar_grafico and linhas:
        msg.add_attachment(_html_grafico(rubrica, periodo, linhas, proj).encode("utf-8"),
                           maintype="text", subtype="html", filename=f"{rubrica}_{periodo}.html")
        png = _png_grafico(rubrica, periodo, linhas)
        if png:
            msg.add_attachment(png, maintype="image", subtype="png",
                               filename=f"{rubrica}_{periodo}.png")
    msg.add_attachment(buf.getvalue().encode("utf-8-sig"), maintype="text", subtype="csv",
                       filename=f"{rubrica}_{periodo}.csv")
    return msg



def listar_alerta_p1(db: DatabaseManager | None = None) -> list[dict]:
    """M7.25: itens P1 abertos da fila de qualidade (alertas que precisam agir)."""
    from workers.quality_score import fila_analise
    return [i for i in fila_analise(db or DatabaseManager()) if i["prioridade"] == "P1"]


def montar_email_alerta(para: str, db: DatabaseManager | None = None) -> EmailMessage | None:
    """Compõe o e-mail de alerta de P1. Retorna None quando não há P1 (sem spam)."""
    p1 = listar_alerta_p1(db)
    if not p1:
        return None
    corpo = [f"PetroAnalytics — {len(p1)} alerta(s) P1 na fila de qualidade:", ""]
    for i in p1[:25]:
        corpo.append(f"  [{i['codigo']}] {i.get('empresa','')} {i.get('periodo','')} — {i['motivo']}")
    corpo += ["", "Triagem: python app_main.py auditoria fila --prioridade P1"]
    msg = EmailMessage()
    msg["Subject"] = f"[PetroAnalytics] ALERTAS P1 — {len(p1)} itens na fila"
    msg["From"] = os.environ.get("SMTP_DE", "petroanalytics@exemplo.com")
    msg["To"] = para
    msg["Date"] = formatdate(localtime=True)
    msg.set_content("\n".join(corpo))
    return msg


def alertar_p1(para: str, db: DatabaseManager | None = None, dry_run: bool = True) -> str | None:
    msg = montar_email_alerta(para, db)
    if msg is None:
        return None
    return enviar(msg, dry_run=dry_run)


def enviar(msg: EmailMessage, dry_run: bool = True) -> str:
    """dry_run=True: salva .eml em data/outbox (sem rede). Retorna o caminho ou 'ENVIADO'."""
    if dry_run:
        outbox = DATA_DIR / "outbox"
        outbox.mkdir(parents=True, exist_ok=True)
        destino = outbox / f"{msg['Subject'].replace(' ', '_')}.eml"
        destino.write_bytes(msg.as_bytes())
        return str(destino)
    host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        smtp.send_message(msg)
    return "ENVIADO"
