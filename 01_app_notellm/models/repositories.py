"""Model: repositorios (SRP: um repo por agregado; DIP: controllers dependem daqui)."""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import config
from models.database import DatabaseManager

CHUNK = 65536

# Campos que o CRUD de fontes aceita criar/alterar (whitelist: evita SQL injection
# por nome de coluna e mantem o Model como unico dono do schema).
CAMPOS_FONTE = ("nome_empresa", "cik", "url_fonte", "tipo_arquivo", "caminho_local",
                "hash_arquivo", "data_download", "status_processamento",
                "nome_documento", "extensao", "pasta_sistema", "api_json", "origem")


def extensao_de(tipo: str, caminho: str | None = None) -> str:
    """Extensao normalizada (.pdf, .xlsm, ...) a partir do tipo ou do caminho."""
    if caminho:
        suf = Path(caminho).suffix.lower()
        if suf:
            return suf
    return "." + (tipo or "").strip().lower().lstrip(".")


def pasta_de(caminho: str | None) -> str:
    return str(Path(caminho).parent) if caminho else ""


def _metrica_pdf(pdf: Any, ultimo: Any) -> dict[str, Any]:
    """Throughput de leitura dos PDFs (M8.12): páginas/seg e tabelas detectadas.

    O numerador é `paginas_lidas` (o que o parse percorreu), nunca o total do
    arquivo: um DF de 37 páginas lido até a 12ª rendia 12, não 37. E a divisão é
    pelo tempo de parse — pelo tempo total da fonte o número mediria o disco, não
    o leitor de PDF. Documento sem duração (0 ms) fica fora da média em vez de
    distorcê-la para infinito.
    """
    n = (pdf["n"] if pdf else 0) or 0
    paginas = (pdf["pag"] if pdf else 0) or 0
    lidas = (pdf["lidas"] if pdf else 0) or 0
    ms = (pdf["ms"] if pdf else 0) or 0
    tabelas = (pdf["tab"] if pdf else 0) or 0
    lent = None
    if ultimo is not None:
        dur = ultimo["duracao_ms"] or 0
        lent = {"documento": ultimo["nome_documento"], "extensao": ultimo["extensao"],
                "paginas": ultimo["n_paginas"],
                "paginas_lidas": ultimo["n_paginas_lidas"],
                "tabelas": ultimo["n_tabelas"], "duracao_ms": ultimo["duracao_ms"],
                "paginas_por_seg": (round(1000.0 * (ultimo["n_paginas_lidas"] or 0) / dur, 2)
                                    if dur else 0.0)}
    return {"documentos": n, "paginas": paginas, "paginas_lidas": lidas,
            "tabelas": tabelas, "duracao_ms": ms,
            "paginas_por_seg": round(1000.0 * lidas / ms, 2) if ms > 0 else 0.0,
            "tabelas_por_doc": round(tabelas / n, 2) if n else 0.0,
            "cobertura_paginas": round(100.0 * lidas / paginas, 1) if paginas else 0.0,
            "mais_lento": lent}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


class FonteRepository:
    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()

    def registrar(self, nome_empresa: str, url: str, tipo: str,
                  caminho: str | None = None, cik: str | None = None,
                  status: str = "PENDENTE", nome_documento: str | None = None,
                  api_json: str | None = None, origem: str | None = None) -> int:
        from workers.ri_collector import canonical_url
        try:
            url = canonical_url(url)
        except Exception:
            pass
        digest = sha256_file(Path(caminho)) if caminho and Path(caminho).is_file() else None
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        doc = nome_documento or (Path(caminho).name if caminho else None)
        with self.db.connect() as conn:
            if digest is None:  # fonte web sem arquivo local: dedup por empresa+url
                row = conn.execute(
                    "SELECT id_fonte FROM tb_fonte_dados WHERE nome_empresa = ? AND url_fonte = ?",
                    (nome_empresa, url)).fetchone()
                if row:
                    return int(row["id_fonte"])
            try:
                cur = conn.execute(
                    """INSERT INTO tb_fonte_dados
                       (nome_empresa, cik, url_fonte, tipo_arquivo, caminho_local,
                        hash_arquivo, data_download, status_processamento,
                        nome_documento, extensao, pasta_sistema, api_json, origem)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (nome_empresa, cik, url, tipo.upper(), caminho, digest, now, status,
                     doc, extensao_de(tipo, caminho), pasta_de(caminho), api_json,
                     origem or "CONTAINER"),
                )
                conn.commit()
                new_id = int(cur.lastrowid or -1)
            except sqlite3.IntegrityError:
                row = conn.execute(
                    "SELECT id_fonte FROM tb_fonte_dados WHERE hash_arquivo = ?", (digest,)
                ).fetchone()
                new_id = int(row["id_fonte"]) if row else -1
        self.exportar()
        return new_id

    def obter(self, id_fonte: int) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM tb_fonte_dados WHERE id_fonte = ?",
                               (id_fonte,)).fetchone()
        return dict(row) if row else None

    def atualizar(self, id_fonte: int, **campos: Any) -> bool:
        """Update do CRUD: so aceita colunas da whitelist; deriva extensao/pasta."""
        sets, vals = [], []
        for chave, valor in campos.items():
            if chave not in CAMPOS_FONTE or valor is None:
                continue
            sets.append(f"{chave} = ?")
            vals.append(valor)
        atual = self.obter(id_fonte)
        if atual is None:
            return False
        if "tipo_arquivo" in campos or "caminho_local" in campos:
            tipo = campos.get("tipo_arquivo") or atual["tipo_arquivo"]
            caminho = campos.get("caminho_local") or atual["caminho_local"]
            sets += ["extensao = ?", "pasta_sistema = ?"]
            vals += [extensao_de(tipo, caminho), pasta_de(caminho)]
        if "caminho_local" in campos and campos["caminho_local"]:
            arq = Path(campos["caminho_local"])
            if arq.is_file():
                sets.append("hash_arquivo = ?")
                vals.append(sha256_file(arq))
        if not sets:
            return False
        vals.append(id_fonte)
        with self.db.connect() as conn:
            cur = conn.execute(f"UPDATE tb_fonte_dados SET {', '.join(sets)} WHERE id_fonte = ?", vals)
            conn.commit()
            ok = cur.rowcount > 0
        if ok:
            self.exportar()
        return ok

    def excluir(self, id_fonte: int, desvincular: bool = True) -> bool:
        """Delete do CRUD. Por padrao preserva os fatos e zera a FK (auditoria)."""
        with self.db.connect() as conn:
            if desvincular:
                conn.execute("UPDATE tb_fato_financeiro SET id_fonte = NULL WHERE id_fonte = ?",
                             (id_fonte,))
                conn.execute("UPDATE tb_fato_operacional SET id_fonte = NULL WHERE id_fonte = ?",
                             (id_fonte,))
            cur = conn.execute("DELETE FROM tb_fonte_dados WHERE id_fonte = ?", (id_fonte,))
            conn.commit()
            ok = cur.rowcount > 0
        if ok:
            self.exportar()
        return ok

    def registrar_processamento(self, id_fonte: int, status: str, duracao_ms: int | None = None,
                                 erro: str | None = None, n_extracoes: int | None = None,
                                 n_paginas: int | None = None,
                                 n_paginas_lidas: int | None = None,
                                 n_tabelas: int | None = None) -> None:
        """Grava o desfecho do ETL na fonte: status, duração, erro, nº de extrações
        e a métrica de leitura do PDF (páginas/tabelas, M8.12)."""
        campos, vals = ["status_processamento = ?", "data_processamento = datetime('now')"], [status]
        if duracao_ms is not None:
            campos.append("duracao_ms = ?")
            vals.append(int(duracao_ms))
        if n_extracoes is not None:
            campos.append("n_extracoes = ?")
            vals.append(int(n_extracoes))
        if n_paginas is not None:
            campos.append("n_paginas = ?")
            vals.append(int(n_paginas))
        if n_paginas_lidas is not None:
            campos.append("n_paginas_lidas = ?")
            vals.append(int(n_paginas_lidas))
        if n_tabelas is not None:
            campos.append("n_tabelas = ?")
            vals.append(int(n_tabelas))
        campos.append("erro = ?")
        vals.append((erro or None))
        vals.append(id_fonte)
        with self.db.connect() as conn:
            conn.execute(f"UPDATE tb_fonte_dados SET {', '.join(campos)} WHERE id_fonte = ?", vals)
            conn.commit()

    def resumo_etl(self) -> dict[str, Any]:
        """Agregações do painel de gestão do ETL (processado / erro / sem dados / duração)."""
        with self.db.connect() as conn:
            linhas = [dict(r) for r in conn.execute(
                "SELECT status_processamento, COUNT(*) n, SUM(COALESCE(n_extracoes,0)) ext,"
                " SUM(COALESCE(duracao_ms,0)) ms FROM tb_fonte_dados"
                " GROUP BY status_processamento").fetchall()]
            ultima = conn.execute(
                "SELECT * FROM tb_etl_execucao ORDER BY id_execucao DESC LIMIT 1").fetchone()
            total_exec = conn.execute("SELECT COUNT(*) c FROM tb_etl_execucao").fetchone()["c"]
            tudo = conn.execute(
                "SELECT COUNT(*) n, SUM(COALESCE(n_extracoes,0)) ext,"
                " SUM(COALESCE(duracao_ms,0)) ms, AVG(COALESCE(duracao_ms,0)) media,"
                " SUM(CASE WHEN data_processamento IS NOT NULL THEN 1 ELSE 0 END) batidas"
                " FROM tb_fonte_dados").fetchone()
            # M8.12: throughput de leitura dos PDFs. n_paginas NULL = nunca medido
            # (CSV/XLSX), entao a media e por documento de PDF, nunca pela base toda.
            pdf = conn.execute(
                "SELECT COUNT(*) n, SUM(COALESCE(n_paginas,0)) pag,"
                " SUM(COALESCE(n_paginas_lidas,0)) lidas,"
                " SUM(COALESCE(n_tabelas,0)) tab, SUM(COALESCE(duracao_ms,0)) ms"
                " FROM tb_fonte_dados WHERE n_paginas IS NOT NULL").fetchone()
            ultimo_pdf = conn.execute(
                "SELECT nome_documento, extensao, n_paginas, n_paginas_lidas, n_tabelas,"
                " duracao_ms FROM tb_fonte_dados WHERE n_paginas IS NOT NULL"
                " ORDER BY COALESCE(duracao_ms,0) DESC LIMIT 1").fetchone()
        por_status = {r["status_processamento"]: r for r in linhas}

        def _n(status: str) -> int:
            return (por_status.get(status) or {}).get("n", 0)

        resumo: dict[str, Any] = {
            "total": tudo["n"] or 0,
            "processadas": _n("PROCESSADO"),
            "catalogadas": _n("CATALOGADO") + _n("DESCOBERTO"),
            "com_erro": _n("ERRO"),
            "sem_dados": _n("SEM_DADOS"),
            "nao_processadas": _n("NAO_PROCESSADO"),
            "nao_baixados": _n("NAO_BAIXADO"),
            "sem_parser": _n("SEM_PARSER"),
            "pendentes": _n("PENDENTE"),
            "duracao_total_ms": tudo["ms"] or 0,
            "duracao_media_ms": round(tudo["media"] or 0, 1),
            "extracoes_total": tudo["ext"] or 0,
            "ja_processadas_alguma_vez": tudo["batidas"] or 0,
            "total_execucoes": total_exec,
            "por_status": {r["status_processamento"]: {"n": r["n"], "extracoes": r["ext"] or 0,
                                                       "duracao_ms": r["ms"] or 0}
                           for r in linhas},
            "ultima_execucao": None,
            "ultimas_cargas": None,
            "ultimas_paginas": None,
            "ultimas_tabelas": None,
            "pdf": _metrica_pdf(pdf, ultimo_pdf),
        }
        if ultima:
            resumo["ultima_execucao"] = ultima["inicio_em"]
            resumo["ultimas_cargas"] = ultima["cargas"]
            resumo["ultimas_paginas"] = ultima["paginas_lidas"]
            resumo["ultimas_tabelas"] = ultima["tabelas_detectadas"]
        return resumo

    def execucoes(self, limite: int = 30) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM tb_etl_execucao ORDER BY id_execucao DESC LIMIT ?",
                (limite,)).fetchall()]

    def abrir_execucao(self) -> int:
        with self.db.connect() as conn:
            cur = conn.execute("INSERT INTO tb_etl_execucao (inicio_em, status) "
                               "VALUES (datetime('now'), 'EM_ANDAMENTO')")
            conn.commit()
            return int(cur.lastrowid or -1)

    def fechar_execucao(self, id_execucao: int, arquivos: int = 0, extracoes: int = 0,
                        cargas: int = 0, pulados: int = 0, revisao: int = 0, erros: int = 0,
                        detalhe: str | None = None, paginas: int = 0, tabelas: int = 0) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """UPDATE tb_etl_execucao SET fim_em = datetime('now'),
                   duracao_ms = CAST((julianday('now') - julianday(inicio_em)) * 86400000 AS INTEGER),
                   arquivos_processados = ?, extracoes = ?, cargas = ?, pulados_pdf = ?,
                   revisao = ?, erros = ?, status = ?, detalhe = ?,
                   paginas_lidas = ?, tabelas_detectadas = ?
                   WHERE id_execucao = ?""",
                (arquivos, extracoes, cargas, pulados, revisao, erros,
                 "ERRO" if erros and not cargas else "CONCLUIDA", detalhe,
                 int(paginas or 0), int(tabelas or 0), id_execucao))
            conn.commit()

    def complementar_campos(self) -> int:
        """Backfill de extensao/pasta_sistema/nome_documento em bancos antigos."""
        with self.db.connect() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT id_fonte, url_fonte, tipo_arquivo, caminho_local, nome_documento"
                " FROM tb_fonte_dados"
                " WHERE extensao IS NULL OR extensao = '' OR nome_documento IS NULL").fetchall()]
            for r in rows:
                caminho = r["caminho_local"]
                doc = Path(caminho).name if caminho else Path(urlparse(r["url_fonte"] or "").path).name
                conn.execute(
                    "UPDATE tb_fonte_dados SET extensao = COALESCE(NULLIF(?, ''), extensao),"
                    " pasta_sistema = COALESCE(NULLIF(?, ''), pasta_sistema),"
                    " nome_documento = COALESCE(NULLIF(?, ''), nome_documento) WHERE id_fonte = ?",
                    (extensao_de(r["tipo_arquivo"], caminho), pasta_de(caminho),
                     doc, r["id_fonte"]))
            conn.commit()
        if rows:
            self.exportar()
        return len(rows)

    def existe_hash(self, digest: str) -> bool:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM tb_fonte_dados WHERE hash_arquivo = ?", (digest,)
            ).fetchone()
        return row is not None

    def listar(self) -> list[dict[str, Any]]:
        # desempate por id: sem ele a ordem entre linhas com o mesmo
        # data_download (quase todas) fica a critério do SQLite e muda entre
        # consultas — na tela de aprovação em lote a linha marcada saltava.
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM tb_fonte_dados"
                                " ORDER BY data_download DESC, id_fonte DESC").fetchall()
        return [dict(r) for r in rows]

    def atualizar_status(self, id_fonte: int, status: str) -> None:
        with self.db.connect() as conn:
            conn.execute("UPDATE tb_fonte_dados SET status_processamento = ? WHERE id_fonte = ?",
                         (status, id_fonte))
            conn.commit()
        self.exportar()

    def verificar_integridade(self) -> list[dict[str, Any]]:
        faltantes = []
        for row in self.listar():
            caminho = row.get("caminho_local") or ""
            if caminho and not Path(caminho).exists():
                faltantes.append(row)
        return faltantes

    def com_api_json(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM tb_fonte_dados WHERE api_json IS NOT NULL AND api_json <> ''"
                " ORDER BY nome_empresa").fetchall()]

    def exportar(self) -> None:
        fontes = self.listar()
        config.CATALOG_JSON.parent.mkdir(parents=True, exist_ok=True)
        with open(config.CATALOG_JSON, "w", encoding="utf-8") as fh:
            json.dump(fontes, fh, indent=2, ensure_ascii=False)
        if fontes:
            with open(config.CATALOG_CSV, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(fontes[0].keys()))
                writer.writeheader()
                writer.writerows(fontes)


class DeParaRepository:
    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()
        self._cache: dict[tuple[str, str], tuple[str, float]] = {}

    def upsert(self, empresa: str, origem: str, canonico: str,
               demonstrativo: str = "DRE", fator: float = 1.0) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO tb_depara_rubrica
                   (nome_empresa, rubrica_origem, rubrica_padronizada, demonstrativo, fator_multiplicador)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (nome_empresa, rubrica_origem) DO UPDATE SET
                     rubrica_padronizada = excluded.rubrica_padronizada,
                     demonstrativo = excluded.demonstrativo,
                     fator_multiplicador = excluded.fator_multiplicador""",
                (empresa, origem, canonico, demonstrativo, fator),
            )
            conn.commit()
        self._cache[(empresa, origem)] = (canonico, fator)

    def resolver(self, empresa: str, origem: str) -> tuple[str | None, float]:
        if (empresa, origem) in self._cache:
            return self._cache[(empresa, origem)]
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT rubrica_padronizada, fator_multiplicador FROM tb_depara_rubrica"
                " WHERE nome_empresa IN (?, '*') AND rubrica_origem = ?"
                " ORDER BY CASE nome_empresa WHEN '*' THEN 1 ELSE 0 END LIMIT 1",
                (empresa, origem),
            ).fetchone()
        if row:
            self._cache[(empresa, origem)] = (row["rubrica_padronizada"], row["fator_multiplicador"])
            return row["rubrica_padronizada"], row["fator_multiplicador"]
        return None, 1.0


class FatoRepository:
    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()

    @staticmethod
    def split_periodo(periodo: str) -> tuple[int, int]:
        periodo = periodo.strip().upper()
        if periodo.endswith(("Q1", "Q2", "Q3", "Q4")):
            return int(periodo[:4]), int(periodo[-1])
        if periodo.endswith(("T1", "T2", "T3", "T4")):
            return int(periodo[:4]), int(periodo[-1])
        if "S1" in periodo or "S2" in periodo:
            return int(periodo[:4]), 0
        return int(periodo[:4]), 0

    def upsert_financeiro(self, empresa: str, periodo: str, rubrica: str, valor: float,
                          moeda: str = "USD", id_fonte: int | None = None,
                          confianca: float = 1.0) -> None:
        ano, tri = self.split_periodo(periodo)
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO tb_fato_financeiro
                   (id_fonte, nome_empresa, moeda, ano, trimestre, periodo,
                    rubrica_padronizada, valor, confianca)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (nome_empresa, rubrica_padronizada, periodo) DO UPDATE SET
                     valor = excluded.valor, moeda = excluded.moeda,
                     id_fonte = excluded.id_fonte, confianca = excluded.confianca,
                     data_atualizacao = datetime('now')""",
                (id_fonte, empresa, moeda, ano, tri, periodo, rubrica, valor, confianca),
            )
            conn.commit()

    def upsert_operacional(self, empresa: str, periodo: str, indicador: str,
                           valor: float, unidade: str = "",
                           id_fonte: int | None = None) -> None:
        ano, tri = self.split_periodo(periodo)
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO tb_fato_operacional
                   (id_fonte, nome_empresa, ano, trimestre, periodo, indicador, unidade_medida, valor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (nome_empresa, indicador, periodo) DO UPDATE SET
                     valor = excluded.valor, unidade_medida = excluded.unidade_medida,
                     id_fonte = excluded.id_fonte""",
                (id_fonte, empresa, ano, tri, periodo, indicador, unidade, valor),
            )
            conn.commit()

    def obter(self, empresa: str, periodo: str, rubrica: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM tb_fato_financeiro WHERE nome_empresa = ? AND periodo = ?"
                " AND rubrica_padronizada = ?", (empresa, periodo, rubrica)).fetchone()
        return dict(row) if row else None

    def matriz(self, periodo: str | None = None) -> list[dict[str, Any]]:
        query = ("SELECT f.nome_empresa, f.periodo, f.rubrica_padronizada, f.valor, f.moeda,"
                 " f.confianca, s.url_fonte, s.tipo_arquivo"
                 " FROM tb_fato_financeiro f LEFT JOIN tb_fonte_dados s ON s.id_fonte = f.id_fonte")
        params: tuple = ()
        if periodo:
            query += " WHERE f.periodo = ?"
            params = (periodo,)
        query += " ORDER BY f.periodo, f.nome_empresa, f.rubrica_padronizada"
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def evolucao(self, empresa: str, rubrica: str) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT periodo, valor FROM tb_fato_financeiro"
                " WHERE nome_empresa = ? AND rubrica_padronizada = ? ORDER BY periodo",
                (empresa, rubrica)).fetchall()]

    def contar(self) -> dict[str, int]:
        with self.db.connect() as conn:
            n_fin = conn.execute("SELECT COUNT(*) c FROM tb_fato_financeiro").fetchone()["c"]
            n_op = conn.execute("SELECT COUNT(*) c FROM tb_fato_operacional").fetchone()["c"]
            n_font = conn.execute("SELECT COUNT(*) c FROM tb_fonte_dados").fetchone()["c"]
        return {"fatos": n_fin, "operacionais": n_op, "fontes": n_font}


class ProjectionRepository:
    """Projecoes estatisticas (workers/forecast.py) — gravadas a parte dos fatos."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()

    def salvar(self, empresa: str, rubrica: str, periodo_base: str, horizonte: int,
               resultado: dict[str, Any]) -> int:
        import json as _json
        n = 0
        with self.db.connect() as conn:
            for h, (periodo, valor) in enumerate(zip(resultado["futuros"],
                                                     resultado["valores"]), start=1):
                conn.execute(
                    """INSERT INTO tb_projecao (nome_empresa, rubrica_padronizada, periodo_base,
                       periodo_projetado, horizonte, valor, intervalo_inf, intervalo_sup, metodo,
                       confianca, mae, mape, serie_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT (nome_empresa, rubrica_padronizada, periodo_projetado)
                       DO UPDATE SET valor = excluded.valor, intervalo_inf = excluded.intervalo_inf,
                         intervalo_sup = excluded.intervalo_sup, metodo = excluded.metodo,
                         confianca = excluded.confianca, mae = excluded.mae, mape = excluded.mape,
                         serie_json = excluded.serie_json, gerado_em = datetime('now')""",
                    (empresa, rubrica, periodo_base, periodo, h, valor,
                     resultado["inf"][h - 1], resultado["sup"][h - 1], resultado["metodo"],
                     resultado["confianca"], resultado["mae"], resultado["mape"],
                     _json.dumps({"periodos": resultado.get("periodos", []),
                                  "reais": resultado.get("reais", [])})))
                n += 1
            conn.commit()
        return n

    def listar(self, empresa: str | None = None, rubrica: str | None = None,
               min_confianca: float = 0.0) -> list[dict[str, Any]]:
        q = "SELECT * FROM tb_projecao WHERE confianca >= ?"
        params: list[Any] = [min_confianca]
        if empresa:
            q += " AND nome_empresa = ?"
            params.append(empresa)
        if rubrica:
            q += " AND rubrica_padronizada = ?"
            params.append(rubrica)
        q += " ORDER BY nome_empresa, rubrica_padronizada, periodo_projetado"
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(q, params).fetchall()]

    def serie_com_projezcao(self, empresa: str, rubrica: str,
                            horizonte: int | None = None) -> dict[str, Any]:
        """Reais + projetados + banda de IC, para o grafico de cenarios.

        `horizonte` corta a projeção nos primeiros h trimestres. Sem isso o
        gráfico mostrava linhas de rodadas anteriores com horizontes misturados
        (o UPSERT é por período, então 2026Q3 pode ter vindo de um h=1 e
        2027Q1 de um h=3) — e o filtro de horizonte do painel não fazia nada.
        `intervalo_inf/sup` são nullable no schema: vêm como None e o gráfico
        desenha gap em vez de quebrar.
        """
        sql = ("SELECT * FROM tb_projecao WHERE nome_empresa = ? AND rubrica_padronizada = ?"
               " ORDER BY periodo_projetado")
        params: list[Any] = [empresa, rubrica]
        if horizonte:
            sql += " LIMIT ?"
            params.append(int(horizonte))
        with self.db.connect() as conn:
            reais = [dict(r) for r in conn.execute(
                "SELECT periodo, valor FROM tb_fato_financeiro WHERE nome_empresa = ?"
                " AND rubrica_padronizada = ? ORDER BY periodo", (empresa, rubrica)).fetchall()]
            proy = [dict(r) for r in conn.execute(sql, params).fetchall()]
        return {"empresa": empresa, "rubrica": rubrica,
                "periodos_reais": [r["periodo"] for r in reais],
                "valores_reais": [r["valor"] for r in reais],
                "periodos_projetados": [p["periodo_projetado"] for p in proy],
                "valores_projetados": [p["valor"] for p in proy],
                "horizontes": [p["horizonte"] for p in proy],
                "inf": [p["intervalo_inf"] for p in proy],
                "sup": [p["intervalo_sup"] for p in proy],
                "metodo": proy[0]["metodo"] if proy else None,
                "confianca": proy[0]["confianca"] if proy else None}


class QualityRepository:
    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or DatabaseManager()

    def alertar(self, tabela: str, reg_id: int, tipo: str, desc: str, sev: str = "MEDIUM") -> None:
        with self.db.connect() as conn:
            existe = conn.execute(
                "SELECT 1 FROM tb_quality_alerts WHERE tabela_ref = ? AND registro_id = ?"
                " AND tipo_alerta = ? AND descricao = ?",
                (tabela, reg_id, tipo, desc)).fetchone()
            if existe:
                return  # idempotente: reruns nao duplicam evidencias
            conn.execute(
                "INSERT INTO tb_quality_alerts (tabela_ref, registro_id, tipo_alerta, descricao, severidade)"
                " VALUES (?, ?, ?, ?, ?)", (tabela, reg_id, tipo, desc, sev))
            conn.commit()

    def para_revisao(self, empresa: str, periodo: str, rubrica: str,
                     valor: float | None, motivo: str, confianca: float = 0.0) -> None:
        with self.db.connect() as conn:
            existe = conn.execute(
                "SELECT 1 FROM tb_review_queue WHERE nome_empresa = ? AND periodo = ?"
                " AND rubrica = ? AND motivo = ? AND status = 'ABERTO'",
                (empresa, periodo, rubrica, motivo)).fetchone()
            if existe:
                return
            conn.execute(
                "INSERT INTO tb_review_queue (nome_empresa, periodo, rubrica, valor, motivo, confianca)"
                " VALUES (?, ?, ?, ?, ?, ?)", (empresa, periodo, rubrica, valor, motivo, confianca))
            conn.commit()

    def listar_alertas(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM tb_quality_alerts ORDER BY criado_em DESC LIMIT 200").fetchall()]

    # ---------------- gestao e controle da auditoria (M2) ----------------
    def reabrir(self, tabela_ref: str, registro_id: int,
               comentario: str | None = None, por: str = "usuario") -> bool:
        """Desfaz a triagem: o item volta para a fila (M2.9).

        A decisao anterior nao e apagada — vira outra linha em tb_auditoria_decisao
        com o comentario de reabertura, entao a trilha continua completa.
        """
        with self.db.connect() as conn:
            if tabela_ref == "tb_review_queue":
                existe = conn.execute(
                    "SELECT status FROM tb_review_queue WHERE id_review = ?",
                    (int(registro_id),)).fetchone()
                if not existe:
                    return False
                # ABERTO/PENDENTE ja estao na fila; decidido e RESOLVIDO/REJEITADO/IGNORADO
                if existe["status"] in ("ABERTO", "PENDENTE"):
                    return False
                conn.execute("UPDATE tb_review_queue SET status = 'ABERTO' "
                             "WHERE id_review = ?", (int(registro_id),))
            conn.execute(
                "INSERT INTO tb_auditoria_decisao (tabela_ref, registro_id, decisao,"
                " comentario, decidido_por) VALUES (?, ?, 'REABERTO', ?, ?)",
                (tabela_ref, int(registro_id),
                 comentario or "item reaberto para nova analise", por))
            conn.commit()
        return True

    def decidir(self, tabela_ref: str, registro_id: int, decisao: str,
                comentario: str | None = None, por: str = "usuario") -> bool:
        """Registra a triagem e reflete a decisao na fila de revisao (idempotente)."""
        if decisao not in ("ACEITO", "REJEITADO", "IGNORADO"):
            raise ValueError(f"decisao invalida: {decisao}")
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO tb_auditoria_decisao (tabela_ref, registro_id, decisao,"
                " comentario, decidido_por) VALUES (?, ?, ?, ?, ?)",
                (tabela_ref, int(registro_id), decisao, comentario, por))
            if tabela_ref == "tb_review_queue":
                novo = {"ACEITO": "RESOLVIDO", "REJEITADO": "REJEITADO",
                        "IGNORADO": "IGNORADO"}[decisao]
                conn.execute("UPDATE tb_review_queue SET status = ? WHERE id_review = ?",
                             (novo, int(registro_id)))
            conn.commit()
        return True

    def decisoes(self, limite: int = 200) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM tb_auditoria_decisao ORDER BY id_decisao DESC LIMIT ?",
                (limite,)).fetchall()]

    def resumo_auditoria(self) -> dict[str, Any]:
        """KPIs da auditoria: severidade, tipos, aging da fila e triagem."""
        with self.db.connect() as conn:
            alertas = [dict(r) for r in conn.execute(
                "SELECT * FROM tb_quality_alerts").fetchall()]
            fila = [dict(r) for r in conn.execute(
                "SELECT * FROM tb_review_queue").fetchall()]
            decisoes = [dict(r) for r in conn.execute(
                "SELECT decisao, COUNT(*) n FROM tb_auditoria_decisao"
                " GROUP BY decisao").fetchall()]
        por_sev: dict[str, int] = {}
        por_tipo: dict[str, int] = {}
        for a in alertas:
            por_sev[a["severidade"]] = por_sev.get(a["severidade"], 0) + 1
            por_tipo[a["tipo_alerta"]] = por_tipo.get(a["tipo_alerta"], 0) + 1
        aging = {"0-7d": 0, "8-30d": 0, ">30d": 0}
        from datetime import datetime as _dt
        hoje = _dt.now()
        for r in fila:
            if r.get("status") != "ABERTO" or not r.get("criado_em"):
                continue
            try:
                dias = (hoje - _dt.fromisoformat(r["criado_em"])).days
            except ValueError:
                continue
            aging["0-7d" if dias <= 7 else "8-30d" if dias <= 30 else ">30d"] += 1
        por_status: dict[str, int] = {}
        for r in fila:
            por_status[r["status"]] = por_status.get(r["status"], 0) + 1
        triagem = {d["decisao"]: d["n"] for d in decisoes}
        # Taxa de resolucao = decisoes que FECHARAM um item sobre o total de decisoes.
        # O denominador era len(decisoes), que e o numero de TIPOS distintos
        # (GROUP BY decisao): com ACEITO=2 e REABERTO=2 dava 2/2 = 100% enquanto
        # 875 itens seguiam abertos. Agora usa a soma das contagens.
        fecham = ("ACEITO", "REJEITADO", "IGNORADO")
        total_decisoes = sum(triagem.values())
        resolvidas = sum(v for k, v in triagem.items() if k in fecham)
        return {"total_alertas": len(alertas), "por_severidade": por_sev,
                "por_tipo": dict(sorted(por_tipo.items(), key=lambda kv: -kv[1])),
                "fila_total": len(fila), "fila_por_status": por_status,
                "fila_aberta": por_status.get("ABERTO", 0), "aging": aging,
                "triagem": triagem, "total_decisoes": total_decisoes,
                "itens_resolvidos": resolvidas,
                "taxa_resolucao": round(100.0 * resolvidas / total_decisoes, 1)
                if total_decisoes else 0.0}

    def listar_revisao(self, apenas_abertos: bool = True) -> list[dict[str, Any]]:
        q = "SELECT * FROM tb_review_queue"
        if apenas_abertos:
            q += " WHERE status = 'ABERTO'"
        q += " ORDER BY criado_em DESC LIMIT 200"
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(q).fetchall()]
