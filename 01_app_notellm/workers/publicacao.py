"""M9.14 — alerta automático de publicação trimestral.

"3T26 publicado": quando um trimestre novo aparece na base (fatos novos do
Container ou da SEC), o e-mail é o lugar certo para a equipe receber o
resumo — não um push no painel, que ninguém olha até segunda.

Para o e-mail poder ser gerado sem intervenção manual, ele precisa de:
1. última publicação (max periodo na base) com contagem de fatos novos;
2. comparação desse trimestre com o anterior para cada rubrica-âncora.
"""
from __future__ import annotations

import csv
import io
from email.message import EmailMessage
from email.utils import formatdate
from typing import Any

from models.database import DatabaseManager

RUBRICAS_PUBLICACAO = ("RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO",
                       "FCO", "DIVIDA_LIQUIDA", "CAPEX")


def ultimo_periodo_com_dados(db: DatabaseManager | None = None) -> dict[str, Any] | None:
    db = db or DatabaseManager()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT MAX(periodo) AS ult, COUNT(*) AS fatos,"
            " COUNT(DISTINCT nome_empresa) AS empresas FROM tb_fato_financeiro").fetchone()
        row2 = conn.execute(
            "SELECT COUNT(*) AS fatos FROM tb_fato_financeiro WHERE periodo = ?",
            (row["ult"],)).fetchone()
    if not row or not row["ult"]:
        return None
    return {"periodo": row["ult"], "fatos_no_periodo": row2["fatos"],
            "empresas": row["empresas"]}


def _trimestre_anterior(periodo: str) -> str | None:
    ano, t = int(periodo[:4]), int(periodo[-1])
    return f"{ano - (t == 1)}Q{t - 1 if t > 1 else 4}"


def comparativo(db: DatabaseManager, periodo: str) -> list[dict[str, Any]]:
    """Rubrica-âncora: valor publicado agora x trimestre anterior (sim/não)."""
    prev = _trimestre_anterior(periodo)
    linhas = []
    with db.connect() as conn:
        for rub in RUBRICAS_PUBLICACAO:
            atual = conn.execute(
                "SELECT AVG(valor) v, COUNT(*) n FROM tb_fato_financeiro"
                " WHERE rubrica_padronizada = ? AND periodo = ?", (rub, periodo)).fetchone()
            ant = (conn.execute(
                "SELECT AVG(valor) v, COUNT(*) n FROM tb_fato_financeiro"
                " WHERE rubrica_padronizada = ? AND periodo = ?", (rub, prev)).fetchone()
                if prev else None)
            if atual["n"] == 0:
                continue
            meio = atual["v"]
            meio_a = ant["v"] if ant and ant["n"] else None
            var = ((meio / meio_a) - 1) * 100 if meio_a else None
            linhas.append({"rubrica": rub, "periodo": periodo, "media": round(meio, 2),
                           "n": atual["n"], "periodo_anterior": prev,
                           "media_anterior": round(meio_a, 2) if meio_a else None,
                           "variacao": round(var, 1) if var is not None else None})
    return linhas


def montar_email_publicacao(para: str, db: DatabaseManager | None = None,
                            periodo: str | None = None) -> EmailMessage | None:
    db = db or DatabaseManager()
    info = ultimo_periodo_com_dados(db)
    if info is None:
        return None
    periodo = periodo or info["periodo"]
    comp = comparativo(db, periodo)
    if not comp:
        return None
    msg = EmailMessage()
    msg["From"] = "PetroAnalytics <poc@petroanalytics.local>"
    msg["To"] = para
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = f"[PetroAnalytics] {periodo} publicado — {info['fatos_no_periodo']} fatos"
    linhas = []
    for c in comp:
        seta = ""
        if c["variacao"] is not None:
            seta = f" ({'+' if c['variacao'] >= 0 else ''}{c['variacao']}% vs {c['periodo_anterior']})"
        linhas.append(f"  {c['rubrica']:<22} {c['media']:>10} US$ bi · {c['n']} empresas{seta}")
    corpo = (
        f"Publicado: {periodo} — {info['fatos_no_periodo']} fatos novos de "
        f"{info['empresas']} empresas.\n\n"
        "    Indicador                 Média das empresas\n"
        + "\n".join(linhas)
        + "\n\nProjeção não é fato publicado: os números do relatório são extraídos de "
        "documentos da própria empresa (RI) ou da cópia regulatória no SEC. "
        "Ver painel em `python app_main.py web`.\n")
    msg.set_content(corpo, charset="utf-8")

    html = ["<h2>Publicação detectada</h2>",
            f"<p><b>{periodo}</b> — {info['fatos_no_periodo']} fatos novos de "
            f"{info['empresas']} empresas.</p>",
            "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse'>",
            "<tr><th>Indicador</th><th>Média (US$ bi)</th><th>Empresas</th>"
            "<th>Vs trimestre anterior</th></tr>"]
    for c in comp:
        seta = (f"{c['variacao']:+}% vs {c['periodo_anterior']}"
                if c["variacao"] is not None else "—")
        html.append(f"<tr><td>{c['rubrica']}</td><td align='right'>{c['media']:,.2f}</td>"
                    f"<td align='right'>{c['n']}</td><td>{seta}</td></tr>")
    html.append("</table><p><small>Projeção não é fato publicado.</small></p>")
    msg.add_alternative("<html><body>" + "".join(html) + "</body></html>",
                        subtype="html", charset="utf-8")

    buf = io.StringIO()
    fw = csv.writer(buf, delimiter=";")
    fw.writerow(["rubrica", "periodo", "media_usd_bi", "empresas", "variacao_qt_anterior_pct"])
    for c in comp:
        fw.writerow([c["rubrica"], c["periodo"], c["media"], c["n"], c["variacao"]])
    msg.add_attachment(buf.getvalue().encode("utf-8-sig"), maintype="text",
                       subtype="csv", filename=f"publicacao_{periodo}.csv")
    return msg


def enviar(para: str, dry_run: bool = True, db: DatabaseManager | None = None,
           periodo: str | None = None):
    from workers.mailer import enviar as _enviar
    msg = montar_email_publicacao(para, db, periodo)
    if msg is None:
        return None
    return _enviar(msg, dry_run=dry_run)
