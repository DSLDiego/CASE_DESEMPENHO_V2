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

from controllers import MailController, SourceController


class DashboardHandler(SimpleHTTPRequestHandler):
    """Serve o HTML do painel, o CRUD JSON de fontes e o envio de e-mail (mesma porta)."""

    api_prefix = "/api/fontes"
    mail_prefix = "/api/email"
    etl_prefix = "/api/etl"

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
