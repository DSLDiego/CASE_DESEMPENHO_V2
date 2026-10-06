"""Controllers: orquestracao de negocio (dependem de abstracoes Model/Workers)."""
from __future__ import annotations

from pathlib import Path

from models.database import DatabaseManager
from models.repositories import FatoRepository, FonteRepository, QualityRepository
from workers.etl import run_etl
from workers.quality import run_audit
from workers.scanner import scan_container


class ForecastController:
    """Projecao estatistica de series trimestrais (M3) — cenarios, nunca 'fato'."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()

    def projetar(self, horizonte: int = 3) -> dict:
        from workers.forecast_run import run_forecast
        return run_forecast(self.db, horizonte=horizonte)

    def projecoes(self, min_confianca: float = 0.0) -> list[dict]:
        from models.repositories import ProjectionRepository
        return ProjectionRepository(self.db).listar(min_confianca=min_confianca)

    def painel(self, empresa: str = "PETROBRAS", rubrica: str = "RECEITA_LIQUIDA") -> dict:
        """Pacote da aba Projecoes: KPIs + serie real/projetada + tabela completa."""
        from models.repositories import ProjectionRepository
        repo = ProjectionRepository(self.db)
        lista = repo.listar()
        cenarios = {}
        with self.db.connect() as conn:
            chaves = [dict(r) for r in conn.execute(
                "SELECT DISTINCT nome_empresa, rubrica_padronizada FROM tb_projecao"
                " ORDER BY nome_empresa, rubrica_padronizada").fetchall()]
        for c in chaves:
            cid = f"{c['nome_empresa']}|{c['rubrica_padronizada']}"
            cenarios[cid] = repo.serie_com_projezcao(c["nome_empresa"], c["rubrica_padronizada"])
        metodos: dict[str, int] = {}
        for p in lista:
            metodos[p["metodo"]] = metodos.get(p["metodo"], 0) + 1
        conf = [p["confianca"] for p in lista if p.get("confianca") is not None]
        horizontes = sorted({p["horizonte"] for p in lista})
        return {"total": len(lista),
                "series": len({(p["nome_empresa"], p["rubrica_padronizada"]) for p in lista}),
                "empresas": len({p["nome_empresa"] for p in lista}),
                "metodos": metodos,
                "confianca_media": round(sum(conf) / len(conf), 2) if conf else 0.0,
                "baixa_confianca": sum(1 for c in conf if c < 0.5),
                "periodos_projetados": sorted({p["periodo_projetado"] for p in lista}),
                "horizontes": horizontes,
                "projecoes": lista, "cenarios": cenarios,
                "padrao": {"empresa": empresa, "rubrica": rubrica}}


class PipelineController:
    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()

    def coleta(self) -> dict:
        return scan_container(FonteRepository(self.db))

    def etl_completo(self, alvos: set[str] | None = None, jobs: int | None = None) -> dict:
        return run_etl(self.db, apenas_periodos=alvos, jobs=jobs)

    def etl_incremental(self, alvos: set[str] | None = None,
                       jobs: int | None = None) -> dict:
        """Refaz o ETL so dos arquivos novos que entraram no Container."""
        return run_etl(self.db, apenas_periodos=alvos, only_new=True, jobs=jobs)

    def descoberta(self, periodo: str | None = None, incluir_sec: bool = True,
                   incluir_ri: bool = True, registrar: bool = True,
                   baixar: bool = False, empresas: list[str] | None = None) -> dict:
        """Descobre o que foi anunciado (SEC/RI) e ainda nao esta no acervo."""
        from workers.discovery import baixar_achados, descobrir
        dados = descobrir(periodo, incluir_sec, incluir_ri, registrar, empresas)
        if baixar:
            # inclui os anexos do arquivamento: e neles que fica a demonstracao
            achados = [a for r in dados["empresas"]
                       for a in (r["sec"].get("novos", []) + r["ri"].get("novos", []))]
            achados += [ax for r in dados["empresas"]
                        for ax in r["sec"].get("anexos_registrados", [])]
            dados["downloads"] = baixar_achados(achados)
        return dados

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

    def resumo_auditoria(self) -> dict:
        """KPIs de gestao da auditoria (severidade, aging, triagem)."""
        return QualityRepository(self.db).resumo_auditoria()

    def relatorio_auditoria(self, de: str | None = None, ate: str | None = None,
                            destino: str | None = None) -> dict:
        """Relatorio de auditoria em PDF com as decisoes do periodo (M2.10)."""
        from workers.relatorio_auditoria import gerar_relatorio
        caminho = gerar_relatorio(Path(destino) if destino else None, de=de, ate=ate,
                                  db=self.db)
        return {"arquivo": caminho, "de": de, "ate": ate}

    def historico_qualidade(self, empresa: str | None = None) -> dict:
        """Scorecard historico: DQS ao longo do tempo (M7.23)."""
        from workers.quality_score import historico_scorecard
        return historico_scorecard(self.db, empresa)

    def resumo_auditoria_periodo(self, de: str | None = None,
                                ate: str | None = None) -> dict:
        """Decisoes do periodo (preview da API e do PDF de M2.10)."""
        from workers.relatorio_auditoria import decisoes_periodo
        decisoes = decisoes_periodo(self.db, de, ate)
        por_decisao: dict[str, int] = {}
        for d in decisoes:
            por_decisao[d["decisao"]] = por_decisao.get(d["decisao"], 0) + 1
        return {"total": len(decisoes), "por_decisao": por_decisao, "decisoes": decisoes}

    def decidir(self, registro_id: int, decisao: str, comentario: str | None = None) -> dict:
        QualityRepository(self.db).decidir("tb_review_queue", registro_id, decisao, comentario)
        return {"id_review": registro_id, "decisao": decisao,
                "resumo": self.resumo_auditoria()}

    def reabrir(self, registro_id: int, comentario: str | None = None) -> dict:
        """Desfaz a triagem: o item volta para PENDENTE (M2.9)."""
        ok = QualityRepository(self.db).reabrir("tb_review_queue", registro_id, comentario)
        return {"id_review": registro_id, "reaberto": ok,
                "resumo": self.resumo_auditoria()}

    def painel_fontes(self, limite: int = 500) -> dict:
        """Gestao e Controle de Fontes (M1): CRUD + cobertura + integridade + lacunas."""
        from config import COMPANIES
        fontes = self.repo.listar()
        por_empresa: dict[str, dict[str, int]] = {}
        for f in fontes:
            d = por_empresa.setdefault(f["nome_empresa"], {})
            d[f["status_processamento"]] = d.get(f["status_processamento"], 0) + 1
        # cobertura: periodos (YYYYQn) efetivamente cobertos por fonte por empresa
        cobertura: dict[str, list[str]] = {}
        for f in fontes:
            pasta = f.get("pasta_sistema") or ""
            for parte in reversed(pasta.replace("\\", "/").split("/")):
                # padrao do Container: 2026_1T  (ano _ trimestre T) => 2026Q1
                if (len(parte) == 7 and parte[:4].isdigit() and parte[4] == "_"
                        and parte[5].isdigit() and parte[6] in ("T", "t")):
                    per = f"{parte[:4]}Q{parte[5]}"
                    lst = cobertura.setdefault(f["nome_empresa"], [])
                    if per not in lst:
                        lst.append(per)
                    break
        for lst in cobertura.values():
            lst.sort()
        todos_periodos = sorted({p for lst in cobertura.values() for p in lst})
        lacunas = []
        for empresa in sorted(COMPANIES):
            for per in todos_periodos:
                if per not in cobertura.get(empresa, []):
                    lacunas.append({"empresa": empresa, "periodo": per})
        return {"resumo": self.repo.resumo_etl(),
                "integridade": {"arquivos_ausentes": len(self.repo.verificar_integridade()),
                                "sem_url": sum(1 for f in fontes if not (f.get("url_fonte") or "")),
                                "sem_data": sum(1 for f in fontes if not (f.get("data_download") or ""))},
                "por_empresa": por_empresa,
                "cobertura": cobertura,
                "periodos": todos_periodos,
                "lacunas": lacunas,
                "com_api_json": len(self.repo.com_api_json()),
                "fontes": fontes[:limite]}
