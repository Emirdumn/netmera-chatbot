"""SQLite şema + bağlantı. İki Streamlit süreci arasında paylaşım için WAL modu."""
import sqlite3

from config.settings import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT (datetime('now')),
    language TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'bot'
        CHECK (status IN ('bot', 'waiting_human', 'with_human', 'closed'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'human_agent')),
    content TEXT NOT NULL,
    agent_name TEXT,
    tool_calls_json TEXT,
    sources_json TEXT,
    orchestrator_json TEXT,
    flow_status_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS handoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    department TEXT NOT NULL,
    reason TEXT,
    summary TEXT,
    urgency TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'claimed', 'closed')),
    assigned_to TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    claimed_at TEXT
);

CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    is_online INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tool_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    tool_name TEXT NOT NULL,
    args_json TEXT,
    summary TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS session_notes (
    session_id INTEGER PRIMARY KEY REFERENCES sessions(id),
    profile_json TEXT,
    case_json TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

_connection = None


def get_connection():
    global _connection
    if _connection is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
    return _connection


def create_schema():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
