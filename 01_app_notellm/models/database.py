"""Camada Model: DDL do SQLite + DatabaseManager (singleton, thread-safe)."""
from __future__ import annotations

import sqlite3
import threading

import config

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tb_fonte_dados (
    id_fonte INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_empresa TEXT NOT NULL,
    cik TEXT,
    url_fonte TEXT NOT NULL,
    tipo_arquivo TEXT NOT NULL,
    caminho_local TEXT,
    hash_arquivo TEXT UNIQUE,
    data_download TEXT,
    status_processamento TEXT DEFAULT 'PENDENTE',
    nome_documento TEXT,
    extensao TEXT,
    pasta_sistema TEXT,
    api_json TEXT,
    origem TEXT DEFAULT 'MANUAL'
);

CREATE TABLE IF NOT EXISTS tb_depara_rubrica (
    id_depara INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_empresa TEXT NOT NULL,
    rubrica_origem TEXT NOT NULL,
    rubrica_padronizada TEXT NOT NULL,
    demonstrativo TEXT NOT NULL DEFAULT 'DRE',
    fator_multiplicador REAL DEFAULT 1.0,
    UNIQUE (nome_empresa, rubrica_origem)
);

CREATE TABLE IF NOT EXISTS tb_fato_financeiro (
    id_fato INTEGER PRIMARY KEY AUTOINCREMENT,
    id_fonte INTEGER,
    nome_empresa TEXT NOT NULL,
    moeda TEXT NOT NULL DEFAULT 'USD',
    ano INTEGER NOT NULL,
    trimestre INTEGER NOT NULL,
    periodo TEXT NOT NULL,
    rubrica_padronizada TEXT NOT NULL,
    valor REAL NOT NULL,
    confianca REAL DEFAULT 1.0,
    data_atualizacao TEXT DEFAULT (datetime('now')),
    UNIQUE (nome_empresa, rubrica_padronizada, periodo),
    FOREIGN KEY (id_fonte) REFERENCES tb_fonte_dados(id_fonte)
);

CREATE TABLE IF NOT EXISTS tb_fato_operacional (
    id_operacional INTEGER PRIMARY KEY AUTOINCREMENT,
    id_fonte INTEGER,
    nome_empresa TEXT NOT NULL,
    ano INTEGER NOT NULL,
    trimestre INTEGER NOT NULL,
    periodo TEXT NOT NULL,
    indicador TEXT NOT NULL,
    unidade_medida TEXT NOT NULL,
    valor REAL NOT NULL,
    UNIQUE (nome_empresa, indicador, periodo),
    FOREIGN KEY (id_fonte) REFERENCES tb_fonte_dados(id_fonte)
);

CREATE TABLE IF NOT EXISTS tb_quality_alerts (
    id_alerta INTEGER PRIMARY KEY AUTOINCREMENT,
    tabela_ref TEXT NOT NULL,
    registro_id INTEGER NOT NULL,
    tipo_alerta TEXT NOT NULL,
    descricao TEXT NOT NULL,
    severidade TEXT NOT NULL DEFAULT 'MEDIUM',
    criado_em TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tb_review_queue (
    id_review INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_empresa TEXT NOT NULL,
    periodo TEXT NOT NULL,
    rubrica TEXT NOT NULL,
    valor REAL,
    motivo TEXT NOT NULL,
    confianca REAL DEFAULT 0.0,
    status TEXT DEFAULT 'ABERTO',
    criado_em TEXT DEFAULT (datetime('now'))
);

-- Historico de execucoes do pipeline (painel de gestao do ETL).
CREATE TABLE IF NOT EXISTS tb_etl_execucao (
    id_execucao INTEGER PRIMARY KEY AUTOINCREMENT,
    inicio_em TEXT DEFAULT (datetime('now')),
    fim_em TEXT,
    duracao_ms INTEGER,
    arquivos_processados INTEGER DEFAULT 0,
    extracoes INTEGER DEFAULT 0,
    cargas INTEGER DEFAULT 0,
    pulados_pdf INTEGER DEFAULT 0,
    revisao INTEGER DEFAULT 0,
    erros INTEGER DEFAULT 0,
    status TEXT DEFAULT 'EM_ANDAMENTO',
    detalhe TEXT,
    paginas_lidas INTEGER DEFAULT 0,
    tabelas_detectadas INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_fato_emp_per
    ON tb_fato_financeiro (nome_empresa, periodo, rubrica_padronizada);
CREATE INDEX IF NOT EXISTS idx_oper_emp_per
    ON tb_fato_operacional (nome_empresa, periodo, indicador);
-- Projecoes estatisticas (NAO sobrescrevem fatos reais; vive separada).
CREATE TABLE IF NOT EXISTS tb_projecao (
    id_projecao INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_empresa TEXT NOT NULL,
    rubrica_padronizada TEXT NOT NULL,
    periodo_base TEXT NOT NULL,
    periodo_projetado TEXT NOT NULL,
    horizonte INTEGER NOT NULL,
    valor REAL NOT NULL,
    intervalo_inf REAL,
    intervalo_sup REAL,
    metodo TEXT NOT NULL,
    confianca REAL DEFAULT 0.0,
    mae REAL,
    mape REAL,
    serie_json TEXT,
    gerado_em TEXT DEFAULT (datetime('now')),
    UNIQUE (nome_empresa, rubrica_padronizada, periodo_projetado)
);

CREATE INDEX IF NOT EXISTS idx_projecao_chave ON tb_projecao (nome_empresa, rubrica_padronizada);

-- Premissas macro por trimestre (Brent, PTAX). Alimenta os cenários (M3.13/M10.8).
-- valor é em USD/bbl (Brent) ou BRL/USD (ptax), média trimestral.
CREATE TABLE IF NOT EXISTS tb_macro_fator (
    periodo TEXT NOT NULL,
    fator TEXT NOT NULL,
    valor REAL NOT NULL,
    PRIMARY KEY (periodo, fator)
);

-- Chaves CIK da SEC EDGAR por empresa (gestao de chaves). O config.COMPANIES
-- alimenta a primeira carga; o usuario pode inserir/atualizar sem editar codigo.
CREATE TABLE IF NOT EXISTS tb_cik_empresa (
    nome_empresa TEXT PRIMARY KEY,
    cik TEXT NOT NULL,
    ativo INTEGER DEFAULT 1,
    atualizado_em TEXT DEFAULT (datetime('now'))
);
-- Trilha de decisao da auditoria (quem aceitou/rejeitou/ignorou cada achado).
CREATE TABLE IF NOT EXISTS tb_auditoria_decisao (
    id_decisao INTEGER PRIMARY KEY AUTOINCREMENT,
    tabela_ref TEXT NOT NULL,
    registro_id INTEGER NOT NULL,
    decisao TEXT NOT NULL,
    comentario TEXT,
    decidido_em TEXT DEFAULT (datetime('now')),
    decidido_por TEXT DEFAULT 'usuario'
);

CREATE INDEX IF NOT EXISTS idx_decisao_ref ON tb_auditoria_decisao (tabela_ref, registro_id);

-- Scorecard de qualidade e confiabilidade (M7): 1 linha por empresa x periodo.
CREATE TABLE IF NOT EXISTS tb_qualidade_score (
    id_score INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_empresa TEXT NOT NULL,
    periodo TEXT NOT NULL,
    completude REAL,
    tempestividade REAL,
    plausibilidade REAL,
    consistencia REAL,
    rastreabilidade REAL,
    dqs REAL,
    classificacao TEXT,
    n_fatos INTEGER DEFAULT 0,
    n_esperadas INTEGER DEFAULT 0,
    detalhes_json TEXT,
    gerado_em TEXT DEFAULT (datetime('now')),
    UNIQUE (nome_empresa, periodo)
);

-- Serie historica do scorecard (M7.23): DQS ao longo do tempo.
-- tb_qualidade_score guarda o ULTIMO estado (UNIQUE empresa x periodo, sobrescrito
-- a cada recalculo); sem esta tabela a evolucao da qualidade some. Aqui cada ponto
-- e gravado quando o DQS muda de verdade — assim a serie mostra mudanca, nao execucao.
CREATE TABLE IF NOT EXISTS tb_qualidade_historico (
    id_hist INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_empresa TEXT NOT NULL,
    periodo TEXT NOT NULL,
    completude REAL,
    tempestividade REAL,
    plausibilidade REAL,
    consistencia REAL,
    rastreabilidade REAL,
    dqs REAL,
    classificacao TEXT,
    n_fatos INTEGER DEFAULT 0,
    gerado_em TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_qhist_chave ON tb_qualidade_historico (nome_empresa, periodo, gerado_em);

-- Registro das regras de alerta/limiar (permite calibrar e reduzir alarme).
-- Registro das regras de alerta/limiar (permite calibrar e reduzir alarme).
-- Chave primaria no codigo: uma regra, um limiar global.
CREATE TABLE IF NOT EXISTS tb_regra_alerta (
    codigo TEXT PRIMARY KEY,
    descricao TEXT,
    limiar REAL,
    severidade TEXT DEFAULT 'MEDIUM',
    ativo INTEGER DEFAULT 1
);

-- M7.22: excecao de limiar por empresa e/ou rubrica. Tabela separada de proposito:
-- mexer na chave primaria de tb_regra_alerta exigiria recriar a tabela em toda base
-- antiga, e a excecao e naturalmente 1:N em relacao a regra.
CREATE TABLE IF NOT EXISTS tb_regra_limiar (
    codigo TEXT NOT NULL,
    empresa TEXT NOT NULL DEFAULT '',
    rubrica TEXT NOT NULL DEFAULT '',
    limiar REAL NOT NULL,
    ativo INTEGER DEFAULT 1,
    PRIMARY KEY (codigo, empresa, rubrica)
);

CREATE INDEX IF NOT EXISTS idx_score_periodo ON tb_qualidade_score (periodo);
CREATE INDEX IF NOT EXISTS idx_fonte_hash ON tb_fonte_dados (hash_arquivo);
CREATE INDEX IF NOT EXISTS idx_fonte_status ON tb_fonte_dados (status_processamento);
CREATE INDEX IF NOT EXISTS idx_etl_exec_inicio ON tb_etl_execucao (inicio_em);
"""

# Colunas adicionadas depois do 1o release (migracao incremental, idempotente).
MIGRATIONS: dict[str, dict[str, str]] = {
    "tb_fonte_dados": {
        "nome_documento": "TEXT",
        "extensao": "TEXT",
        "pasta_sistema": "TEXT",
        "api_json": "TEXT",
        "origem": "TEXT DEFAULT 'MANUAL'",
        "data_processamento": "TEXT",
        "duracao_ms": "INTEGER",
        "erro": "TEXT",
        "n_extracoes": "INTEGER DEFAULT 0",
        # Metricas de leitura do PDF (M8.12): n_paginas e o TAMANHO do documento,
        # n_paginas_lidas o que o parse percorreu de fato (limitado por politica de
        # profundidade). O throughput (paginas/seg) usa as lidas — dividir o total
        # do arquivo pelo tempo do parse inflaria o numero. NULL = nao medido.
        "n_paginas": "INTEGER",
        "n_paginas_lidas": "INTEGER",
        "n_tabelas": "INTEGER",
    },
    "tb_etl_execucao": {
        "paginas_lidas": "INTEGER DEFAULT 0",
        "tabelas_detectadas": "INTEGER DEFAULT 0",
    },
    # M7.27 — proveniencia: o numero veio do documento da propria empresa (RI),
    # de uma copia regulatoria (SEC) ou e derivado de outros fatos? A cadeia
    # fica no proprio fato para nao depender de refazer o ETL.
    "tb_fato_financeiro": {
        "profundidade_proveniencia": "INTEGER",
        "origem_proveniencia": "TEXT",
        "cadeia_proveniencia": "TEXT",
    },
    "tb_fato_operacional": {
        "profundidade_proveniencia": "INTEGER",
        "origem_proveniencia": "TEXT",
        "cadeia_proveniencia": "TEXT",
    },
}


class DatabaseManager:
    """Singleton de conexao SQLite com lock para uso em Workers/threads."""

    _instance: "DatabaseManager | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                    inst.init_db()
                    cls._instance = inst
        return cls._instance

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
        self.migrate()

    def migrate(self) -> list[str]:
        """ALTER TABLE ... ADD COLUMN para bancos criados por versoes anteriores."""
        aplicadas: list[str] = []
        with self.connect() as conn:
            for tabela, colunas in MIGRATIONS.items():
                existentes = {r["name"] for r in conn.execute(f"PRAGMA table_info({tabela})")}
                for coluna, ddl in colunas.items():
                    if coluna not in existentes:
                        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {ddl}")
                        aplicadas.append(f"{tabela}.{coluna}")
            conn.commit()
        return aplicadas

    def reset(self) -> None:
        with self.connect() as conn:
            for tbl in ("tb_review_queue", "tb_quality_alerts", "tb_fato_operacional",
                        "tb_fato_financeiro", "tb_depara_rubrica", "tb_fonte_dados",
                        "tb_etl_execucao", "tb_projecao", "tb_auditoria_decisao",
                        "tb_qualidade_historico", "tb_qualidade_score",
                        "tb_regra_alerta", "tb_regra_limiar", "tb_macro_fator",
                        "tb_cik_empresa"):
                conn.execute(f"DELETE FROM {tbl};")
            conn.commit()
