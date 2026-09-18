#!/usr/bin/env python3
"""Reconcile mutable QA against the production database contract."""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

try:
    from scripts.apply_sql import (
        CORE_TABLES,
        assert_safe_sql,
        baseline_is_applied,
        configure_transaction_safety,
        connect,
        ensure_database,
        ensure_version_table,
        expand_sql_secrets,
        git_value,
        load_config,
        qident,
        record_script,
        sql_entries,
        validate_core_schema,
    )
    from scripts.reconcile.db import (
        acquire_advisory_lock,
        acquire_advisory_lock,
        apply_migration,
        baseline_status,
        check_missing_roles,
        expand_content,
        get_recorded_checksum,
        inspect_roles_with_bootstrap,
        missing_core_tables,
        record_baseline,
        safe_rollback,
        transactional_probe,
    )
    from scripts.reconcile.policy import (
        dependencies_satisfied,
        error_payload,
        extract_required_roles,
        failure_status,
        load_reconcile_policy,
        migration_policy,
        read_upstream_commit,
        summarize,
    )
    from scripts.reconcile.report import write_github_summary
    from scripts.reconcile.storage import (
        begin_run,
        ensure_reconciliation_tables,
        finish_run,
        record_healthy_version,
        record_result,
    )
except ModuleNotFoundError:
    from apply_sql import (  # type: ignore
        CORE_TABLES,
        assert_safe_sql,
        baseline_is_applied,
        configure_transaction_safety,
        connect,
        ensure_database,
        ensure_version_table,
        expand_sql_secrets,
        git_value,
        load_config,
        qident,
        record_script,
        sql_entries,
        validate_core_schema,
    )
    from reconcile.db import (  # type: ignore
        apply_migration,
        baseline_status,
        check_missing_roles,
        expand_content,
        get_recorded_checksum,
        inspect_roles_with_bootstrap,
        missing_core_tables,
        record_baseline,
        safe_rollback,
        transactional_probe,
    )
    from reconcile.policy import (  # type: ignore
        dependencies_satisfied,
        error_payload,
        extract_required_roles,
        failure_status,
        load_reconcile_policy,
        migration_policy,
        read_upstream_commit,
        summarize,
    )
    from reconcile.report import write_github_summary  # type: ignore
    from reconcile.storage import (  # type: ignore
        begin_run,
        ensure_reconciliation_tables,
        finish_run,
        record_healthy_version,
        record_result,
    )

ADVISORY_LOCK_ID = 84729341


def reconcile(root: Path) -> str:
    load_dotenv(root / ".env")
    cfg = load_config(root)
    policy = load_reconcile_policy(root)
    qa_commit = os.getenv("GITHUB_SHA") or git_value(root, "rev-parse", "HEAD")
    if qa_commit == "unknown":
        raise RuntimeError("Nao foi possivel identificar o commit atual do QA")
    prod_commit = read_upstream_commit(root)
    if prod_commit == "unknown":
        raise RuntimeError("upstream.lock ausente, invalido ou nao aponta para um commit exato do prod")

    referenced_roles: set[str] = set()
    entries = sql_entries(root, cfg)
    for path, mode, _baseline in entries:
        if mode != "never":
            referenced_roles.update(extract_required_roles(path.read_text(encoding="utf-8")))

    roles_before = inspect_roles_with_bootstrap(cfg, referenced_roles, connect)
    ensure_database(cfg)
    roles_after = inspect_roles_with_bootstrap(cfg, referenced_roles, connect)
    roles_repaired = sorted((referenced_roles - roles_before) & roles_after)

    db = cfg["database"]
    conn = connect(cfg, db["name"], db["owner"]["user"], db["owner"]["password"])
    results: dict[str, dict] = {}
    critical_failed = False
    locked = False
    try:
        with conn.cursor() as cur:
            configure_transaction_safety(cur)
            ensure_version_table(cur, root, cfg)
            ensure_reconciliation_tables(cur)
        conn.commit()

        run_id = begin_run(conn, qa_commit, prod_commit)
        core_before = missing_core_tables(conn, CORE_TABLES)

        acquire_advisory_lock(conn, ADVISORY_LOCK_ID)
        locked = True

        for path, mode, baseline_query in entries:
            identity = path.relative_to(root / db["sql_path"]).as_posix()
            item_policy = migration_policy(policy, identity)
            critical = item_policy["critical"]
            depends_on = item_policy["depends_on"]

            if mode == "never":
                status, reason = "DISABLED", "mode never vindo do contrato de prod"
                results[identity] = {"status": status, "reason": reason, "critical": critical}
                record_result(conn, run_id, prod_commit, identity, status, reason=reason)
                continue

            ok, blocked_by = dependencies_satisfied(
                depends_on, {name: item["status"] for name, item in results.items()}
            )
            if not ok:
                status = "BLOCKED"
                reason = "dependencias nao satisfeitas: " + ", ".join(blocked_by)
                results[identity] = {"status": status, "reason": reason, "critical": critical}
                record_result(conn, run_id, prod_commit, identity, status, reason=reason)
                critical_failed = critical_failed or critical
                continue

            recorded_checksum = get_recorded_checksum(conn, identity)
            raw_content = path.read_text(encoding="utf-8")
            try:
                assert_safe_sql(raw_content, identity)

                if mode == "once" and recorded_checksum and not baseline_query:
                    status, reason = "UNCHANGED", "migration once ja registrada"
                    results[identity] = {"status": status, "reason": reason, "critical": critical}
                    record_result(
                        conn, run_id, prod_commit, identity, status,
                        checksum=recorded_checksum, reason=reason,
                    )
                    continue

                if mode == "once" and baseline_query and baseline_status(
                    conn, baseline_query, identity, configure_transaction_safety, baseline_is_applied
                ):
                    checksum = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
                    record_baseline(conn, identity, checksum, qa_commit, record_script)
                    status, reason = "BASELINED", "dados existentes satisfazem baseline; SQL nao executado"
                    results[identity] = {"status": status, "reason": reason, "critical": critical}
                    record_result(
                        conn, run_id, prod_commit, identity, status,
                        checksum=checksum, reason=reason,
                    )
                    continue

                content = expand_content(conn, raw_content, expand_sql_secrets)
                checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
                if mode == "on_change" and recorded_checksum == checksum and not policy["reapply_on_change"]:
                    status, reason = "UNCHANGED", "checksum sem alteracoes"
                    results[identity] = {"status": status, "reason": reason, "critical": critical}
                    record_result(
                        conn, run_id, prod_commit, identity, status,
                        checksum=checksum, reason=reason,
                    )
                    continue

                missing_roles = check_missing_roles(conn, extract_required_roles(content))
                if missing_roles:
                    raise RuntimeError("roles obrigatorias ausentes: " + ", ".join(missing_roles))

                transactional_probe(conn, content, configure_transaction_safety, validate_core_schema)
                apply_migration(
                    conn, content, identity, checksum, qa_commit,
                    configure_transaction_safety, validate_core_schema, record_script,
                )

                if mode == "on_change" and recorded_checksum == checksum:
                    status = "RECONCILED"
                    reason = "checksum igual; reaplicado para corrigir/confirmar drift do QA"
                else:
                    status = "APPLIED"
                    reason = "transactional probe aprovado e migration aplicada"
                results[identity] = {"status": status, "reason": reason, "critical": critical}
                record_result(
                    conn, run_id, prod_commit, identity, status,
                    checksum=checksum, reason=reason,
                )
            except Exception as exc:
                safe_rollback(conn)
                code, detail = error_payload(exc)
                dependency_results = {
                    dep: results[dep]["status"]
                    for dep in depends_on
                    if dep in results
                }
                status = failure_status(exc, dependency_results)
                if critical:
                    status = "FAILED"
                    critical_failed = True
                reason = f"{exc.__class__.__name__}: {detail}"
                results[identity] = {
                    "status": status, "reason": reason, "critical": critical, "error_code": code,
                }
                record_result(
                    conn, run_id, prod_commit, identity, status,
                    checksum=recorded_checksum, reason=reason,
                    error_code=code, error_detail=detail,
                )
                print(f"[{status}] {identity}: {reason}", file=sys.stderr)
                if not policy["continue_on_error"]:
                    break

        core_after = missing_core_tables(conn, CORE_TABLES)
        overall, summary = summarize(results, critical_failed)
        summary["drift"] = {
            "roles_repaired": roles_repaired,
            "core_missing_before": core_before,
            "core_missing_after": core_after,
            "data_policy": "preserve" if policy["preserve_data"] else "unspecified",
            "unexpected_objects": policy["unexpected_objects"],
        }
        if overall == "HEALTHY":
            record_healthy_version(conn, cfg, qa_commit, prod_commit, qident)
        finish_run(conn, run_id, overall, summary)
        write_github_summary(summary, prod_commit, qa_commit, roles_repaired, core_before, core_after)
        return overall
    finally:
        if locked:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_ID,))
                conn.commit()
            except psycopg2.Error:
                safe_rollback(conn)
        conn.close()


def main() -> None:
    status = reconcile(Path(__file__).resolve().parents[1])
    if status == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
