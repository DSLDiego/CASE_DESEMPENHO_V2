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
    detalhe TEXT
);

CREATE INDEX IF NOT EXISTS idx_fato_emp_per
    ON tb_fato_financeiro (nome_empresa, periodo, rubrica_padronizada);
CREATE INDEX IF NOT EXISTS idx_oper_emp_per
    ON tb_fato_operacional (nome_empresa, periodo, indicador);
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
                        "tb_etl_execucao"):
                conn.execute(f"DELETE FROM {tbl};")
            conn.commit()
