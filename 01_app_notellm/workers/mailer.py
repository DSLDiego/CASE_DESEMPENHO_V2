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
import os
import smtplib
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path

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


def _html_grafico(rubrica: str, periodo: str, linhas: list[dict]) -> str:
    """HTML autocontido: tabela + grafico de barras Plotly (CDN)."""
    from html import escape
    dados = [[r["nome_empresa"], round(r["valor"], 2)] for r in linhas]
    rotulos = [d[0] for d in dados]
    valores = [d[1] for d in dados]
    cores = [CORES.get(e, "#4a90d9") for e in rotulos]
    linhas_html = "".join(
        f"<tr><td>{escape(rotulos[i])}</td><td align='right'>{valores[i]:,.2f}</td></tr>"
        for i in range(len(rotulos)))
    return f"""<!DOCTYPE html><html lang="pt-BR"><meta charset="utf-8">
<title>PetroAnalytics {escape(_rotulo(rubrica))} {escape(periodo)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>body{{font-family:Segoe UI,Arial,sans-serif;font-size:13px;color:#0f172a;margin:16px}}
h1{{font-size:16px}}table{{border-collapse:collapse;margin-top:12px}}
td,th{{border:1px solid #e2e8f0;padding:4px 8px}}</style>
<h1>PetroAnalytics — {escape(_rotulo(rubrica))} em {escape(periodo)} (USD bi)</h1>
<div id="g" style="width:640px;height:340px"></div>
<table><tr><th>Empresa</th><th>USD bi</th></tr>{linhas_html}</table>
<p><small>Fonte: base comparativa PetroAnalytics (RI + SEC EDGAR). CSV em anexo.</small></p>
<script>
var d={dados!r}, r={rotulos!r}, c={cores!r};
Plotly.newPlot('g',[{{type:'bar',x:r,y:d.map(function(v){{return v[1];}}),
  text:d.map(function(v){{return v[1].toFixed(2);}}),textposition:'outside',
  marker:{{color:c}},cliponaxis:true,
  hovertemplate:'%{{x}}: %{{y:,.2f}} USD bi<extra></extra>'}}],
 {{title:{(_rotulo(rubrica) + ' ' + periodo)!r},margin:{{t:50,b:60,l:55,r:20}},
   yaxis:{{rangemode:'tozero',automargin:true}},xaxis:{{automargin:true,tickangle:-20}},
   template:'plotly',uniformtext:{{minsize:9}},showlegend:false}},{{responsive:true}});
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


def montar_email(para: str, rubrica: str, periodo: str,
                 db: DatabaseManager | None = None,
                 anexar_grafico: bool = True) -> EmailMessage:
    fatos = FatoRepository(db or DatabaseManager())
    linhas = [r for r in fatos.matriz(periodo) if r["rubrica_padronizada"] == rubrica]
    linhas.sort(key=lambda r: r["valor"], reverse=True)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["empresa", "periodo", "rubrica", "valor_usd_bi", "fonte"])
    for r in linhas:
        writer.writerow([r["nome_empresa"], r["periodo"], rubrica,
                         f"{r['valor']:.4f}", r.get("url_fonte") or ""])
    corpo = [f"PetroAnalytics PoC — {_rotulo(rubrica)} em {periodo} (USD bi):", ""]
    corpo += [f"  {r['nome_empresa']}: {r['valor']:,.2f}" for r in linhas]
    corpo += ["", f"Fonte: base comparativa ({len(linhas)} empresas). Ver painel e catálogo."]
    if anexar_grafico and linhas:
        corpo += ["", "Em anexo: benchmark.html (gráfico interativo), PNG e CSV."]
    msg = EmailMessage()
    msg["Subject"] = f"[PetroAnalytics] {_rotulo(rubrica)} {periodo}"
    msg["From"] = os.environ.get("SMTP_DE", "petroanalytics@exemplo.com")
    msg["To"] = para
    msg["Date"] = formatdate(localtime=True)
    msg.set_content("\n".join(corpo))
    if anexar_grafico and linhas:
        msg.add_attachment(_html_grafico(rubrica, periodo, linhas).encode("utf-8"),
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
