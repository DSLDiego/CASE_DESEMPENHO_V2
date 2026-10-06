"""View Servidor: arquivos estaticos do painel + API JSON do CRUD de fontes.

O painel e' estatico (sem framework), mas o CRUD de fontes precisa de persistencia.
Por isso o servidor expoe REST minimo em /api/fontes (GET/POST/PUT/DELETE), usado
pela aba "Fontes (CRUD)" e pelo CLI `python app_main.py fontes ...`.
"""
from __future__ import annotations

import json
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from controllers import ForecastController, MailController, SourceController


def _cobertura_projecao() -> list[dict]:
    """Rubrica -> quantas séries foram projetadas.

    Revela rubricas que têm fato e nenhuma projeção. Antes isso era invisível: a
    lista fixa `RUBRICAS_PROJETAveis` simplesmente deixava FCL, DIVIDA_BRUTA e
    DESPESA_OPERACIONAL de fora, sem aviso na tela.
    """
    from models.database import DatabaseManager
    from models.glossario import obter
    with DatabaseManager().connect() as conn:
        com_fato = {r["rubrica_padronizada"]: r["n"] for r in conn.execute(
            "SELECT rubrica_padronizada, COUNT(*) n FROM tb_fato_financeiro GROUP BY 1")}
        projetadas = {r["rubrica_padronizada"]: r["n"] for r in conn.execute(
            "SELECT rubrica_padronizada, COUNT(DISTINCT nome_empresa) n "
            "FROM tb_projecao GROUP BY 1")}
    linhas = []
    for rubrica, fatos in sorted(com_fato.items(), key=lambda x: -x[1]):
        g = obter(rubrica)
        linhas.append({"rubrica": rubrica, "nome": g["nome"], "unidade": g["unidade"],
                       "categoria": g["categoria"], "fatos": fatos,
                       "series_projetadas": projetadas.get(rubrica, 0),
                       "coberta": bool(projetadas.get(rubrica)),
                       "formula": g["formula"]})
    return linhas


class DashboardHandler(SimpleHTTPRequestHandler):
    """Serve o HTML do painel, o CRUD JSON de fontes, o painel do ETL, as
    projecoes (M3) e a gestao da auditoria (M2)."""

    api_prefix = "/api/fontes"
    mail_prefix = "/api/email"
    etl_prefix = "/api/etl"
    proj_prefix = "/api/projecao"
    aud_prefix = "/api/auditoria"
    qual_prefix = "/api/qualidade"
    desc_prefix = "/api/descoberta"
    glo_prefix = "/api/glossario"

    def log_message(self, fmt: str, *args) -> None:  # silencia log de arquivo
        pass

    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _corpo(self) -> dict:
        tamanho = int(self.headers.get("Content-Length") or 0)
        if not tamanho:
            return {}
        try:
            return json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_GET(self) -> None:  # noqa: N802 (nome imposed por BaseHTTPRequestHandler)
        rota = self.path.split("?")[0]
        if rota == self.api_prefix:
            ctrl = SourceController()
            ctrl.complementar_campos()
            self._json(200, {"fontes": ctrl.catalogo()})
            return
        if rota == self.etl_prefix:  # painel de gestão do ETL
            self._json(200, SourceController().painel_etl())
            return
        if rota == self.proj_prefix:  # projeções (M3)
            q = parse_qs(urlparse(self.path).query)
            ctrl = ForecastController()
            if (q.get("gerar") or ["0"])[0] in ("1", "true"):
                ctrl.projetar(int((q.get("horizonte") or ["3"])[0]))
            empresa = (q.get("empresa") or ["PETROBRAS"])[0]
            rubrica = (q.get("rubrica") or ["RECEITA_LIQUIDA"])[0]
            painel = ctrl.painel(empresa, rubrica)
            if (q.get("cobertura") or ["0"])[0] in ("1", "true"):
                painel["cobertura"] = _cobertura_projecao()
            self._json(200, painel)
            return
        if rota == self.aud_prefix:  # auditoria (M2)
            ctrl = SourceController()
            q = parse_qs(urlparse(self.path).query)
            de = (q.get("de") or [None])[0]
            ate = (q.get("ate") or [None])[0]
            payload = {"resumo": ctrl.resumo_auditoria(),
                       "alertas": ctrl.qualidade()["alertas"][:200],
                       "revisao": ctrl.qualidade()["revisao"][:200]}
            if de or ate:      # decisoes do periodo (M2.10) — sem filtro, tudo
                payload["periodo"] = ctrl.resumo_auditoria_periodo(de, ate)
            if (q.get("pdf") or ["0"])[0] in ("1", "true"):
                try:
                    payload["relatorio"] = ctrl.relatorio_auditoria(de, ate)
                except Exception as exc:  # noqa: BLE001
                    self._json(500, {"erro": f"{type(exc).__name__}: {exc}"})
                    return
            self._json(200, payload)
            return
        if rota == self.qual_prefix:  # qualidade e rastreabilidade (M7)
            from workers.quality_score import painel_qualidade
            p = painel_qualidade()
            if (parse_qs(urlparse(self.path).query).get("rodar") or ["0"])[0] in ("1", "true"):
                from workers.quality_score import run_quality_score
                p["execucao"] = run_quality_score()
                p = painel_qualidade()
            self._json(200, p)
            return
        if rota == self.glo_prefix:  # glossario de indicadores
            from models import glossario
            q = parse_qs(urlparse(self.path).query)
            termo = (q.get("q") or [""])[0]
            dados = glossario.resumo()
            if termo:
                achados = glossario.buscar(termo)
                dados = {"total": len(achados), "com_formula": sum(
                    1 for g in achados if g.get("formula")),
                    "categorias": glossario.por_categoria(), "indicadores": achados,
                    "filtro": termo}
            self._json(200, dados)
            return
        if rota == self.desc_prefix:  # descoberta do que foi anunciado (M9)
            from controllers import PipelineController
            q = parse_qs(urlparse(self.path).query)
            def _flag(nome, padrao):
                return (q.get(nome) or [padrao])[0] in ("1", "true")
            dados = PipelineController().descoberta(
                periodo=(q.get("periodo") or [None])[0],
                incluir_sec=_flag("sec", "1"), incluir_ri=_flag("ri", "1"),
                registrar=_flag("registrar", "1"), baixar=_flag("baixar", "0"))
            self._json(200, dados)
            return
        if rota == self.mail_prefix:  # preview: o que sera anexado
            q = parse_qs(urlparse(self.path).query)
            rubrica = (q.get("rubrica") or ["RECEITA_LIQUIDA"])[0]
            periodo = (q.get("periodo") or ["2026Q2"])[0]
            self._json(200, {"rubrica": rubrica, "periodo": periodo,
                             "dados": MailController().preview(rubrica, periodo)})
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        rota = self.path.split("?")[0]
        dados = self._corpo()
        if rota == self.aud_prefix:  # triagem de auditoria (M2)
            try:
                r = SourceController().decidir(int(dados.get("id")), dados.get("decisao", ""),
                                              dados.get("comentario"))
            except (TypeError, ValueError) as exc:
                self._json(400, {"erro": str(exc)})
                return
            self._json(200, r)
            return
        if rota == self.proj_prefix:  # gera projecoes sob demanda
            try:
                self._json(200, ForecastController().projetar(int(dados.get("horizonte", 3))))
            except ValueError as exc:
                self._json(400, {"erro": str(exc)})
                return
        if rota == self.mail_prefix:  # gera (.eml) ou envia via SMTP
            try:
                resultado = MailController().enviar(
                    dados.get("para", ""), dados.get("rubrica") or "RECEITA_LIQUIDA",
                    dados.get("periodo") or "2026Q2",
                    enviar_real=bool(dados.get("enviar")),
                    anexos=dados.get("anexos", True) is not False)
            except ValueError as exc:
                self._json(400, {"erro": str(exc)})
                return
            except Exception as exc:  # SMTP sem credenciais, disco cheio, ...
                self._json(500, {"erro": f"{type(exc).__name__}: {exc}"})
                return
            self._json(200, resultado)
            return
        if rota != self.api_prefix:
            self._json(404, {"erro": "recurso nao encontrado"})
            return
        obrig = ("nome_empresa", "url_fonte", "tipo_arquivo")
        faltando = [c for c in obrig if not dados.get(c)]
        if faltando:
            self._json(400, {"erro": f"campos obrigatorios: {', '.join(faltando)}"})
            return
        ctrl = SourceController()
        novo_id = ctrl.registrar_manual(
            empresa=dados["nome_empresa"], url=dados["url_fonte"], tipo=dados["tipo_arquivo"],
            caminho=dados.get("caminho_local") or None,
            nome_documento=dados.get("nome_documento") or None,
            api_json=dados.get("api_json") or None)
        self._json(201, {"id_fonte": novo_id, "fonte": ctrl.obter(novo_id)})

    def do_PUT(self) -> None:  # noqa: N802
        if self.path.split("?")[0] != self.api_prefix:
            self._json(404, {"erro": "recurso nao encontrado"})
            return
        dados = self._corpo()
        id_fonte = dados.pop("id_fonte", None)
        if not id_fonte:
            self._json(400, {"erro": "id_fonte obrigatorio"})
            return
        ok = SourceController().atualizar(int(id_fonte), **dados)
        self._json(200 if ok else 404, {"atualizado": ok,
                                        "fonte": SourceController().obter(int(id_fonte))})

    def do_DELETE(self) -> None:  # noqa: N802
        if self.path.split("?")[0] != self.api_prefix:
            self._json(404, {"erro": "recurso nao encontrado"})
            return
        id_fonte = self._corpo().get("id_fonte") or self.path.split("=")[-1]
        if not str(id_fonte).isdigit():
            self._json(400, {"erro": "id_fonte numerico obrigatorio"})
            return
        ok = SourceController().excluir(int(id_fonte))
        self._json(200 if ok else 404, {"excluido": ok})


def serve(diretorio: Path, porta: int = 8080, abrir: bool = True) -> None:
    import functools
    handler = functools.partial(DashboardHandler, directory=str(diretorio))
    if abrir:
        threading.Timer(1.0, lambda: webbrowser.open(
            f"http://localhost:{porta}/")).start()
    with ThreadingHTTPServer(("127.0.0.1", porta), handler) as httpd:
        httpd.serve_forever()
