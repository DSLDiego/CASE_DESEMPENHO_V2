-- Benchmarking Financeiro PoC — schema SQLite v0/v3
-- Modelo: empresas x periodos x indicadores x fontes, com rastreabilidade e qualidade.
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS company (
  company_id   TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  country      TEXT,
  currency     TEXT NOT NULL,
  is_peer      INTEGER NOT NULL DEFAULT 1,
  in_poc       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS period (
  period_id    TEXT PRIMARY KEY,
  year         INTEGER NOT NULL,
  quarter      INTEGER NOT NULL,
  label        TEXT NOT NULL,
  report_type  TEXT NOT NULL DEFAULT 'QUARTER',
  is_ytd       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS indicator (
  indicator_id TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  category     TEXT NOT NULL,
  unit         TEXT NOT NULL DEFAULT 'USD_M',
  definition   TEXT
);

CREATE TABLE IF NOT EXISTS source (
  source_id    TEXT PRIMARY KEY,
  company_id   TEXT NOT NULL REFERENCES company(company_id),
  document     TEXT NOT NULL,
  url          TEXT,
  url_final    TEXT,
  downloaded_at TEXT,
  version      INTEGER NOT NULL DEFAULT 1,
  sha256       TEXT,
  size_bytes   INTEGER,
  content_type TEXT,
  etag         TEXT,
  last_modified TEXT,
  local_path   TEXT,
  is_official  INTEGER NOT NULL DEFAULT 0,
  authority    TEXT DEFAULT 'UNKNOWN',
  is_demo      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS observation (
  obs_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id   TEXT NOT NULL REFERENCES company(company_id),
  period_id    TEXT NOT NULL REFERENCES period(period_id),
  indicator_id TEXT NOT NULL REFERENCES indicator(indicator_id),
  value        REAL,
  currency     TEXT,
  scale        REAL NOT NULL DEFAULT 1,
  unit         TEXT,
  source_id    TEXT REFERENCES source(source_id),
  confidence   REAL NOT NULL DEFAULT 0.6,
  evidence     TEXT,
  page         INTEGER,
  sheet        TEXT,
  method       TEXT DEFAULT 'HEURISTIC',
  parser_version TEXT,
  extractor_version TEXT,
  is_demo      INTEGER NOT NULL DEFAULT 0,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(company_id, period_id, indicator_id, source_id)
);

-- Visao publicada: melhor observacao por (empresa, periodo, indicador)
CREATE VIEW IF NOT EXISTS metric_current AS
SELECT o.* FROM observation o
INNER JOIN (
  SELECT company_id, period_id, indicator_id, MAX(confidence) AS mc, MAX(created_at) AS mt
  FROM observation GROUP BY company_id, period_id, indicator_id
) b ON b.company_id=o.company_id AND b.period_id=o.period_id AND b.indicator_id=o.indicator_id
WHERE o.confidence = b.mc;

CREATE TABLE IF NOT EXISTS file_manifest (
  url          TEXT PRIMARY KEY,
  company_id   TEXT,
  period_id    TEXT,
  local_path   TEXT,
  sha256       TEXT,
  size_bytes   INTEGER,
  etag         TEXT,
  last_modified TEXT,
  downloaded_at TEXT NOT NULL DEFAULT (datetime('now')),
  version      INTEGER NOT NULL DEFAULT 1,
  status       TEXT NOT NULL DEFAULT 'DOWNLOADED'
);

CREATE TABLE IF NOT EXISTS etl_run (
  run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at   TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at  TEXT,
  mode         TEXT NOT NULL DEFAULT 'INCREMENTAL',
  files_total  INTEGER DEFAULT 0,
  files_ok     INTEGER DEFAULT 0,
  files_review INTEGER DEFAULT 0,
  files_failed INTEGER DEFAULT 0,
  notes        TEXT
);

CREATE TABLE IF NOT EXISTS etl_item (
  item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id       INTEGER REFERENCES etl_run(run_id),
  file_path    TEXT NOT NULL,
  company_id   TEXT,
  period_id    TEXT,
  status       TEXT NOT NULL DEFAULT 'PARSED',
  message      TEXT,
  elapsed_ms   INTEGER DEFAULT 0,
  sha256       TEXT,
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quality_issue (
  issue_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id   TEXT,
  period_id    TEXT,
  indicator_id TEXT,
  rule         TEXT NOT NULL,
  severity     TEXT NOT NULL DEFAULT 'INFO',
  message      TEXT NOT NULL,
  value        REAL,
  previous_value REAL,
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reconciliation (
  rec_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id   TEXT NOT NULL,
  period_id    TEXT NOT NULL,
  indicator_id TEXT NOT NULL,
  value_a      REAL,
  source_a     TEXT,
  value_b      REAL,
  source_b     TEXT,
  diff_pct     REAL,
  status       TEXT NOT NULL DEFAULT 'MATCH',
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quarantine (
  q_id         INTEGER PRIMARY KEY AUTOINCREMENT,
  file_path    TEXT NOT NULL,
  error        TEXT NOT NULL,
  stage        TEXT NOT NULL DEFAULT 'PARSE',
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
