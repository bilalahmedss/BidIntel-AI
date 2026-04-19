import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bidintel.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    NOT NULL UNIQUE,
    full_name     TEXT    NOT NULL DEFAULT '',
    password_hash TEXT    NOT NULL,
    token_version INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title             TEXT    NOT NULL,
    rfp_id            TEXT    NOT NULL DEFAULT '',
    issuer            TEXT    NOT NULL DEFAULT '',
    status            TEXT    NOT NULL DEFAULT 'draft',
    deadline          TEXT    NOT NULL DEFAULT '',
    company_knowledge_data TEXT NOT NULL DEFAULT '',
    response_rfp      TEXT    NOT NULL DEFAULT '',
    rfp_filename      TEXT    NOT NULL DEFAULT '',
    response_filename TEXT    NOT NULL DEFAULT '',
    parsed_rfp_json   TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_members (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    role       TEXT    NOT NULL DEFAULT 'editor',
    joined_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_id, user_id)
);

CREATE TABLE IF NOT EXISTS sections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL,
    content     TEXT    NOT NULL DEFAULT '',
    order_index INTEGER NOT NULL DEFAULT 0,
    source      TEXT    NOT NULL DEFAULT 'manual',
    locked_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sections_project ON sections(project_id, order_index);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id             TEXT    NOT NULL UNIQUE,
    project_id         INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status             TEXT    NOT NULL DEFAULT 'queued',
    financial_scenario TEXT    NOT NULL DEFAULT 'expected',
    error_message      TEXT,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_jobs_project ON analysis_jobs(project_id);

CREATE TABLE IF NOT EXISTS analysis_results (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                 TEXT    NOT NULL UNIQUE REFERENCES analysis_jobs(job_id) ON DELETE CASCADE,
    project_id             INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    financial_scenario     TEXT    NOT NULL,
    rfp_meta_json          TEXT    NOT NULL DEFAULT '{}',
    gates_json             TEXT    NOT NULL DEFAULT '[]',
    criterion_results_json TEXT    NOT NULL DEFAULT '[]',
    gate_results_json      TEXT    NOT NULL DEFAULT '[]',
    wps_summary_json       TEXT    NOT NULL DEFAULT '{}',
    scenarios_json         TEXT    NOT NULL DEFAULT '{}',
    poison_pills_json      TEXT    NOT NULL DEFAULT '[]',
    created_at             TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_results_project ON analysis_results(project_id);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    role       TEXT    NOT NULL,
    content    TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_chat_project ON chat_messages(project_id, created_at);

CREATE TABLE IF NOT EXISTS lookup_docs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL UNIQUE,
    size_bytes  INTEGER NOT NULL DEFAULT 0,
    uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    uploaded_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db() -> None:
    DATA_DIR = DB_PATH.parent
    for d in ["uploads/rfp", "uploads/response", "company_brain", "chroma_kb", "outputs"]:
        (DATA_DIR / d).mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.executescript(SCHEMA)
        user_columns = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "token_version" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
        project_columns = {r[1] for r in conn.execute("PRAGMA table_info(projects)").fetchall()}
        if "company_knowledge_data" not in project_columns:
            conn.execute(
                "ALTER TABLE projects ADD COLUMN company_knowledge_data TEXT NOT NULL DEFAULT ''"
            )
        if "response_rfp" not in project_columns:
            conn.execute("ALTER TABLE projects ADD COLUMN response_rfp TEXT NOT NULL DEFAULT ''")
    # Reset any stuck running jobs from a previous crash
    conn = get_db()
    try:
        conn.execute(
            "UPDATE analysis_jobs SET status='error', error_message='Server restarted' WHERE status='running'"
        )
        conn.commit()
    finally:
        conn.close()


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(r) if r else None


def rows(rs: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rs]
