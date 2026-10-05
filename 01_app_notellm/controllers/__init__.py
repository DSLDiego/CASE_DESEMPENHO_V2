"""Controllers: orquestracao de negocio (dependem de abstracoes Model/Workers)."""
from __future__ import annotations

from models.database import DatabaseManager
from models.repositories import FatoRepository, FonteRepository, QualityRepository
from workers.etl import run_etl
from workers.quality import run_audit
from workers.scanner import scan_container


class PipelineController:
    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()

    def coleta(self) -> dict:
        return scan_container(FonteRepository(self.db))

    def etl_completo(self, alvos: set[str] | None = None) -> dict:
        return run_etl(self.db, apenas_periodos=alvos)

    def auditoria(self) -> dict:
        return run_audit(self.db)


class MailController:
    """Envio do benchmark por e-mail com o grafico anexado (HTML + PNG + CSV)."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()

    def preview(self, rubrica: str, periodo: str) -> list[dict]:
        """Dados que serao anexados (para a UI mostrar o que vai no e-mail)."""
        fatos = FatoRepository(self.db)
        linhas = [r for r in fatos.matriz(periodo) if r["rubrica_padronizada"] == rubrica]
        linhas.sort(key=lambda r: r["valor"], reverse=True)
        return [{"empresa": r["nome_empresa"], "valor": round(r["valor"], 2),
                 "fonte": r.get("url_fonte") or ""} for r in linhas]

    def enviar(self, para: str, rubrica: str = "RECEITA_LIQUIDA", periodo: str = "2026Q2",
               enviar_real: bool = False, anexos: bool = True) -> dict:
        """dry-run (enviar_real=False) gera o .eml em data/outbox e devolve o caminho."""
        from workers.mailer import enviar as _enviar, montar_email
        if not (para or "").strip() or "@" not in (para or ""):
            raise ValueError("destinatario invalido (informe um e-mail)")
        msg = montar_email(para.strip(), rubrica, periodo, self.db, anexos)
        caminho = _enviar(msg, dry_run=not enviar_real)
        return {"resultado": caminho, "assunto": msg["Subject"], "para": msg["To"],
                "anexos": [p.get_filename() for p in msg.iter_attachments()],
                "enviado": bool(enviar_real)}


class AnalyticsController:
    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()
        self.fatos = FatoRepository(self.db)

    def ranking(self, periodo: str, rubrica: str) -> list[dict]:
        linhas = [r for r in self.fatos.matriz(periodo) if r["rubrica_padronizada"] == rubrica]
        return sorted(linhas, key=lambda r: r["valor"], reverse=True)

    def insight_executivo(self, periodo: str) -> str:
        partes = []
        for rub in ("RECEITA_LIQUIDA", "EBITDA_AJUSTADO", "LUCRO_LIQUIDO"):
            rank = self.ranking(periodo, rub)
            if not rank:
                continue
            top = rank[0]
            vals = [r["valor"] for r in rank]
            media = sum(vals) / len(vals)
            partes.append(f"{rub}: lider {top['nome_empresa']} ({top['valor']:.2f} USD bi; media pares {media:.2f}).")
        petro = [r for r in self.fatos.matriz(periodo) if r["nome_empresa"] == "PETROBRAS"]
        if petro:
            rec = next((r["valor"] for r in petro if r["rubrica_padronizada"] == "RECEITA_LIQUIDA"), None)
            ebitda = next((r["valor"] for r in petro if r["rubrica_padronizada"] == "EBITDA_AJUSTADO"), None)
            if rec and ebitda:
                partes.append(f"Margem EBITDA Petrobras: {ebitda / rec:.1%}.")
        return " ".join(partes) or "Sem dados para o periodo."


class SourceController:
    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()
        self.repo = FonteRepository(self.db)

    def catalogo(self):
        return self.repo.listar()

    def registrar_manual(self, empresa: str, url: str, tipo: str, caminho: str | None = None,
                          nome_documento: str | None = None, api_json: str | None = None) -> int:
        from config import COMPANIES
        cik = COMPANIES.get((empresa or "").upper(), {}).get("cik")
        return self.repo.registrar(empresa, url, tipo, caminho, cik, "MANUAL",
                                   nome_documento, api_json, "MANUAL")

    def obter(self, id_fonte: int):
        return self.repo.obter(id_fonte)

    def atualizar(self, id_fonte: int, **campos):
        return self.repo.atualizar(id_fonte, **campos)

    def excluir(self, id_fonte: int, desvincular: bool = True):
        return self.repo.excluir(id_fonte, desvincular)

    def complementar_campos(self) -> int:
        return self.repo.complementar_campos()

    def com_api_json(self):
        return self.repo.com_api_json()

    def resumo_etl(self) -> dict:
        """KPIs do painel de gestão do ETL (processado/erro/sem dados/duração)."""
        return self.repo.resumo_etl()

    def execucoes_etl(self, limite: int = 30):
        return self.repo.execucoes(limite)

    def painel_etl(self, limite: int = 500) -> dict:
        """Pacote completo consumido pelo painel web (`/api/etl`) e pela GUI.

        Ordena por prioridade de intervencao (ERRO -> SEM_DADOS -> NAO_PROCESSADO ->
        PROCESSADO -> NAO_BAIXADO) e, dentro de cada grupo, pelo tempo de processo:
        o que precisa de atencao aparece primeiro, nao o download mais recente.
        """
        prioridade = {"ERRO": 0, "SEM_DADOS": 1, "NAO_PROCESSADO": 2, "SEM_PARSER": 3,
                      "PROCESSADO": 4, "PENDENTE": 5}
        fontes = sorted(self.repo.listar(),
                        key=lambda f: (prioridade.get(f["status_processamento"], 6),
                                       -(f["duracao_ms"] or 0),
                                       f["data_download"] or ""))[:limite]
        return {"resumo": self.repo.resumo_etl(), "execucoes": self.repo.execucoes(30),
                "fontes": fontes}

    def escanear_api_json(self):
        from workers.api_scan import escanear as _escanear, resumo as _resumo
        relatorio = _escanear(repo=self.repo)
        return {"relatorio": relatorio, "resumo": _resumo(relatorio)}

    def integridade(self):
        return self.repo.verificar_integridade()

    def qualidade(self):
        quality = QualityRepository(self.db)
        return {"alertas": quality.listar_alertas(), "revisao": quality.listar_revisao()}
