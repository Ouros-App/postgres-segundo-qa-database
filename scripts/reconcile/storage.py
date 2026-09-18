from __future__ import annotations

import json
from typing import Any


def ensure_reconciliation_tables(cur) -> None:
    """Create durable reconciliation run and latest-state tables."""
    cur.execute(
        "CREATE TABLE IF NOT EXISTS controle_scripts_sql ("
        "arquivo TEXT PRIMARY KEY, checksum VARCHAR(64) NOT NULL, "
        "commit_id VARCHAR(64) NOT NULL, "
        "executado_em TIMESTAMPTZ NOT NULL DEFAULT NOW())"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS qa_reconciliation_runs ("
        "id BIGSERIAL PRIMARY KEY, qa_commit VARCHAR(64) NOT NULL, "
        "prod_commit VARCHAR(64) NOT NULL, started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
        "finished_at TIMESTAMPTZ, status VARCHAR(16), "
        "summary JSONB NOT NULL DEFAULT '{}'::jsonb)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS qa_reconciliation_items ("
        "run_id BIGINT NOT NULL REFERENCES qa_reconciliation_runs(id) ON DELETE CASCADE, "
        "arquivo TEXT NOT NULL, checksum VARCHAR(64), status VARCHAR(16) NOT NULL, "
        "reason TEXT, error_code TEXT, error_detail TEXT, "
        "attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), applied_at TIMESTAMPTZ, "
        "PRIMARY KEY (run_id, arquivo))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS qa_reconciliation_state ("
        "arquivo TEXT PRIMARY KEY, checksum VARCHAR(64), status VARCHAR(16) NOT NULL, "
        "prod_commit VARCHAR(64) NOT NULL, last_error TEXT, "
        "last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), last_applied_at TIMESTAMPTZ)"
    )


def begin_run(conn, qa_commit: str, prod_commit: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO qa_reconciliation_runs (qa_commit, prod_commit) VALUES (%s, %s) RETURNING id",
            (qa_commit, prod_commit),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def record_result(
    conn,
    run_id: int,
    prod_commit: str,
    identity: str,
    status: str,
    *,
    checksum: str | None = None,
    reason: str | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    applied = status in {"APPLIED", "RECONCILED", "BASELINED"}
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO qa_reconciliation_items "
            "(run_id, arquivo, checksum, status, reason, error_code, error_detail, applied_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END)",
            (run_id, identity, checksum, status, reason, error_code, error_detail, applied),
        )
        cur.execute(
            "INSERT INTO qa_reconciliation_state "
            "(arquivo, checksum, status, prod_commit, last_error, last_attempt_at, last_applied_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW(), CASE WHEN %s THEN NOW() ELSE NULL END) "
            "ON CONFLICT (arquivo) DO UPDATE SET checksum = EXCLUDED.checksum, "
            "status = EXCLUDED.status, prod_commit = EXCLUDED.prod_commit, "
            "last_error = EXCLUDED.last_error, last_attempt_at = NOW(), "
            "last_applied_at = CASE WHEN %s THEN NOW() ELSE qa_reconciliation_state.last_applied_at END",
            (identity, checksum, status, prod_commit, error_detail, applied, applied),
        )
    conn.commit()


def finish_run(conn, run_id: int, status: str, summary: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE qa_reconciliation_runs SET finished_at = NOW(), status = %s, "
            "summary = %s::jsonb WHERE id = %s",
            (status, json.dumps(summary, ensure_ascii=False), run_id),
        )
    conn.commit()


def record_healthy_version(conn, cfg: dict, qa_commit: str, prod_commit: str, qident) -> None:
    """Reserve legacy controle_versoes for fully converged states."""
    table = cfg["database"]["version_table"]
    comment = f"QA reconciled successfully with production {prod_commit}"
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {qident(table)} (commit_id, comentario_commit) VALUES (%s, %s)",
                (qa_commit, comment),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
