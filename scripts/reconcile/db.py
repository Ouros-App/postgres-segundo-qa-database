from __future__ import annotations

import sys
import time

import psycopg2


def safe_rollback(conn) -> bool:
    """Rollback without replacing an exception already being handled."""
    active_exception = sys.exception()
    try:
        conn.rollback()
        return True
    except Exception as rollback_error:
        print(f"[WARN] rollback falhou: {rollback_error}", file=sys.stderr)
        if active_exception is None:
            raise
        return False


def acquire_advisory_lock(
    conn,
    lock_id: int,
    *,
    attempts: int = 10,
    delay_seconds: float = 1.0,
) -> None:
    """Acquire a session advisory lock with a bounded wait."""
    if attempts < 1:
        raise ValueError("attempts deve ser >= 1")

    for attempt in range(attempts):
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (lock_id,))
                acquired = bool(cur.fetchone()[0])
            conn.commit()
        except Exception:
            safe_rollback(conn)
            raise

        if acquired:
            return
        if attempt + 1 < attempts:
            time.sleep(delay_seconds)

    raise TimeoutError(
        f"Nao foi possivel adquirir advisory lock {lock_id} apos {attempts} tentativas"
    )


def get_recorded_checksum(conn, identity: str) -> str | None:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT checksum FROM controle_scripts_sql WHERE arquivo = %s", (identity,))
            row = cur.fetchone()
        return row[0] if row else None
    finally:
        safe_rollback(conn)


def check_missing_roles(conn, roles: set[str]) -> list[str]:
    if not roles:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)", (sorted(roles),))
            existing = {row[0] for row in cur.fetchall()}
        return sorted(roles - existing)
    finally:
        safe_rollback(conn)


def inspect_roles_with_bootstrap(cfg: dict, role_names: set[str], connect) -> set[str]:
    """Inspect roles before prod provisioning so repaired security drift is visible."""
    if not role_names:
        return set()
    db = cfg["database"]
    boot = db["bootstrap"]
    try:
        conn = connect(cfg, boot["db"], boot["user"], boot["password"])
    except psycopg2.Error:
        return set()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)", (sorted(role_names),))
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def missing_core_tables(conn, core_tables) -> list[str]:
    missing: list[str] = []
    try:
        with conn.cursor() as cur:
            for table in core_tables:
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                if cur.fetchone()[0] is None:
                    missing.append(table)
        return missing
    finally:
        safe_rollback(conn)


def expand_content(conn, raw_content: str, expand_sql_secrets) -> str:
    try:
        with conn.cursor() as cur:
            return expand_sql_secrets(raw_content, cur)
    finally:
        safe_rollback(conn)


def baseline_status(conn, query: str, identity: str, configure_transaction_safety, baseline_is_applied) -> bool:
    try:
        with conn.cursor() as cur:
            configure_transaction_safety(cur)
            return baseline_is_applied(cur, query, identity)
    finally:
        safe_rollback(conn)


def transactional_probe(conn, content: str, configure_transaction_safety, validate_core_schema) -> None:
    """Execute the exact migration against QA and always roll it back."""
    try:
        with conn.cursor() as cur:
            configure_transaction_safety(cur)
            cur.execute(content)
            validate_core_schema(cur)
    finally:
        safe_rollback(conn)


def apply_migration(
    conn,
    content: str,
    identity: str,
    checksum: str,
    commit_id: str,
    configure_transaction_safety,
    validate_core_schema,
    record_script,
) -> None:
    try:
        with conn.cursor() as cur:
            configure_transaction_safety(cur)
            cur.execute(content)
            validate_core_schema(cur)
            record_script(cur, identity, checksum, commit_id)
        conn.commit()
    except Exception:
        safe_rollback(conn)
        raise


def record_baseline(conn, identity: str, checksum: str, commit_id: str, record_script) -> None:
    try:
        with conn.cursor() as cur:
            record_script(cur, identity, checksum, commit_id)
        conn.commit()
    except Exception:
        safe_rollback(conn)
        raise
