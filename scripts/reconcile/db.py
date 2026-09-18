from __future__ import annotations

import psycopg2


def get_recorded_checksum(conn, identity: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT checksum FROM controle_scripts_sql WHERE arquivo = %s", (identity,))
        row = cur.fetchone()
    conn.rollback()
    return row[0] if row else None


def check_missing_roles(conn, roles: set[str]) -> list[str]:
    if not roles:
        return []
    with conn.cursor() as cur:
        cur.execute("SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)", (sorted(roles),))
        existing = {row[0] for row in cur.fetchall()}
    conn.rollback()
    return sorted(roles - existing)


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
    with conn.cursor() as cur:
        for table in core_tables:
            cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
            if cur.fetchone()[0] is None:
                missing.append(table)
    conn.rollback()
    return missing


def expand_content(conn, raw_content: str, expand_sql_secrets) -> str:
    with conn.cursor() as cur:
        content = expand_sql_secrets(raw_content, cur)
    conn.rollback()
    return content


def baseline_status(conn, query: str, identity: str, configure_transaction_safety, baseline_is_applied) -> bool:
    try:
        with conn.cursor() as cur:
            configure_transaction_safety(cur)
            return baseline_is_applied(cur, query, identity)
    finally:
        conn.rollback()


def transactional_probe(conn, content: str, configure_transaction_safety, validate_core_schema) -> None:
    """Execute the exact migration against QA and always roll it back."""
    try:
        with conn.cursor() as cur:
            configure_transaction_safety(cur)
            cur.execute(content)
            validate_core_schema(cur)
    finally:
        conn.rollback()


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
        conn.rollback()
        raise


def record_baseline(conn, identity: str, checksum: str, commit_id: str, record_script) -> None:
    try:
        with conn.cursor() as cur:
            record_script(cur, identity, checksum, commit_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
