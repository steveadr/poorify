import sqlite3
import os
from datetime import datetime, timezone

HARNESS_DIR = os.path.join(os.getcwd(), ".poorify", "core")
DB_PATH = os.path.join(HARNESS_DIR, "harness_state.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS execution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_file TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    output_summary TEXT,
    status TEXT CHECK(status IN ('SUCCESS', 'FAILED')),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS long_term_milestones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    milestone_description TEXT NOT NULL,
    compressed_steps_count INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS technical_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_project_path TEXT NOT NULL,
    target_file TEXT NOT NULL,
    pre_conditions TEXT NOT NULL,
    post_conditions TEXT NOT NULL,
    strict_constraints TEXT
);

CREATE TABLE IF NOT EXISTS migration_router (
    file_path TEXT PRIMARY KEY,
    cyclomatic_complexity INTEGER NOT NULL,
    ingestion_mode TEXT CHECK(ingestion_mode IN ('SKELETON', 'FULL')) NOT NULL
);

CREATE TABLE IF NOT EXISTS business_assertions (
    rule_key TEXT PRIMARY KEY,
    target_file TEXT NOT NULL,
    input_mock_json TEXT NOT NULL,
    expected_output TEXT NOT NULL,
    last_validated DATETIME
);

CREATE TABLE IF NOT EXISTS cascade_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_task_id INTEGER,
    affected_file TEXT NOT NULL,
    error_message TEXT NOT NULL,
    status TEXT CHECK(status IN ('PENDING', 'FIXED')) DEFAULT 'PENDING'
);

CREATE TABLE IF NOT EXISTS token_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    target_file TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cached_tokens INTEGER DEFAULT 0,
    context_window_size INTEGER DEFAULT 0,
    context_window_max INTEGER DEFAULT 0,
    retry_attempt INTEGER DEFAULT 0,
    skeleton_savings INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection() -> sqlite3.Connection:
    os.makedirs(HARNESS_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)


def log_execution(target_file: str, action: str, summary: str,
                  status: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO execution_logs (target_file, action_taken, output_summary, status) VALUES (?, ?, ?, ?)",
            (target_file, action, summary, status))
        return cur.lastrowid


def get_recent_logs(limit: int = 20) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM execution_logs ORDER BY timestamp DESC LIMIT ?",
            (limit,)).fetchall()


def compress_logs() -> None:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT COUNT(*) as cnt FROM execution_logs").fetchone()
        if rows["cnt"] < 20:
            return
        logs = conn.execute(
            "SELECT * FROM execution_logs ORDER BY timestamp ASC LIMIT 20"
        ).fetchall()
        descriptions = [
            f"{r['target_file']}: {r['action_taken']}" for r in logs
        ]
        summary = "; ".join(descriptions)
        conn.execute(
            "INSERT INTO long_term_milestones (milestone_description, compressed_steps_count) VALUES (?, ?)",
            (summary, len(logs)))
        ids = tuple(r["id"] for r in logs)
        conn.execute(f"DELETE FROM execution_logs WHERE id IN ({','.join('?' * len(ids))})", ids)


def prune_irrelevant_logs(current_mission_file: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM execution_logs WHERE target_file NOT LIKE ?",
            (f"%{current_mission_file}%",))


def save_technical_spec(sub_project_path: str, target_file: str,
                        pre_conditions: str, post_conditions: str,
                        strict_constraints: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO technical_specs (sub_project_path, target_file, pre_conditions, post_conditions, strict_constraints) VALUES (?, ?, ?, ?, ?)",
            (sub_project_path, target_file, pre_conditions, post_conditions,
             strict_constraints))
        return cur.lastrowid


def get_technical_spec(target_file: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM technical_specs WHERE target_file = ? ORDER BY id DESC LIMIT 1",
            (target_file,)).fetchone()


def set_router_entry(file_path: str, complexity: int,
                     mode: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO migration_router (file_path, cyclomatic_complexity, ingestion_mode) VALUES (?, ?, ?)",
            (file_path, complexity, mode))


def get_router_entry(file_path: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM migration_router WHERE file_path = ?",
            (file_path,)).fetchone()


def save_assertion(rule_key: str, target_file: str,
                   input_mock: str, expected_output: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO business_assertions (rule_key, target_file, input_mock_json, expected_output, last_validated) VALUES (?, ?, ?, ?, ?)",
            (rule_key, target_file, input_mock, expected_output,
             datetime.now(timezone.utc).isoformat()))


def get_assertions_for_file(target_file: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM business_assertions WHERE target_file = ?",
            (target_file,)).fetchall()


def add_cascade_task(root_task_id: int, affected_file: str,
                     error_message: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO cascade_tasks (root_task_id, affected_file, error_message) VALUES (?, ?, ?)",
            (root_task_id, affected_file, error_message))
        return cur.lastrowid


def get_pending_cascade_tasks() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM cascade_tasks WHERE status = 'PENDING' ORDER BY id ASC"
        ).fetchall()


def mark_cascade_fixed(task_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE cascade_tasks SET status = 'FIXED' WHERE id = ?",
            (task_id,))


def log_token_metric(pipeline_id: str, phase: str, target_file: str,
                     input_tokens: int = 0, output_tokens: int = 0,
                     cached_tokens: int = 0,
                     context_window_size: int = 0,
                     context_window_max: int = 0,
                     retry_attempt: int = 0,
                     skeleton_savings: int = 0,
                     duration_ms: int = 0) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO token_metrics (pipeline_id, phase, target_file, input_tokens, output_tokens, cached_tokens, context_window_size, context_window_max, retry_attempt, skeleton_savings, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pipeline_id, phase, target_file, input_tokens, output_tokens,
             cached_tokens, context_window_size, context_window_max,
             retry_attempt, skeleton_savings, duration_ms))


def get_metrics_for_pipeline(pipeline_id: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM token_metrics WHERE pipeline_id = ? ORDER BY id ASC",
            (pipeline_id,)).fetchall()


def get_all_pipeline_ids() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT DISTINCT pipeline_id, MIN(timestamp) as first_ts FROM token_metrics GROUP BY pipeline_id ORDER BY first_ts DESC"
        ).fetchall()


def get_aggregate_metrics() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT phase, COUNT(*) as runs, AVG(input_tokens) as avg_input, AVG(output_tokens) as avg_output, AVG(cached_tokens) as avg_cached, MAX(context_window_size) as max_ctx, AVG(duration_ms) as avg_dur, SUM(skeleton_savings) as total_saved FROM token_metrics GROUP BY phase ORDER BY phase"
        ).fetchall()


def inspect_module(keyword: str) -> dict:
    pattern = f"%{keyword}%"
    result = {}
    with get_connection() as conn:
        result["specs"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM technical_specs WHERE target_file LIKE ? OR sub_project_path LIKE ?",
                (pattern, pattern)).fetchall()
        ]
        result["router"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM migration_router WHERE file_path LIKE ?",
                (pattern,)).fetchall()
        ]
        result["assertions"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM business_assertions WHERE target_file LIKE ? OR rule_key LIKE ?",
                (pattern, pattern)).fetchall()
        ]
        result["metrics"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM token_metrics WHERE target_file LIKE ?",
                (pattern,)).fetchall()
        ]
        result["cascade"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM cascade_tasks WHERE affected_file LIKE ? OR error_message LIKE ?",
                (pattern, pattern)).fetchall()
        ]
        result["logs"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM execution_logs WHERE target_file LIKE ?",
                (pattern,)).fetchall()
        ]
    return result
