import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.reconcile.db import acquire_advisory_lock, safe_rollback
from scripts.reconcile.policy import (
    dependencies_satisfied,
    extract_required_roles,
    failure_status,
    load_reconcile_policy,
    migration_policy,
    read_upstream_commit,
    summarize,
)


class FakePgError(Exception):
    def __init__(self, message: str, pgcode: str | None = None):
        super().__init__(message)
        self.pgcode = pgcode


class RollbackFailureConnection:
    def rollback(self):
        raise RuntimeError("rollback exploded")


class FakeLockCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.connection.executed.append((query, params))

    def fetchone(self):
        return (self.connection.outcomes.pop(0),)


class FakeLockConnection:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.executed = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return FakeLockCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class ReconcileSqlTest(unittest.TestCase):
    def test_default_policy_prefers_reconciliation_and_data_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy = load_reconcile_policy(Path(tmp))
        self.assertTrue(policy["continue_on_error"])
        self.assertTrue(policy["reapply_on_change"])
        self.assertTrue(policy["preserve_data"])
        self.assertEqual(policy["unexpected_objects"], "report_only")

    def test_policy_supports_critical_and_dependency_metadata(self) -> None:
        policy = {
            "migrations": {
                "schema.sql": {"critical": True},
                "view.sql": {"depends_on": ["schema.sql"]},
            }
        }
        self.assertTrue(migration_policy(policy, "schema.sql")["critical"])
        self.assertEqual(migration_policy(policy, "view.sql")["depends_on"], ["schema.sql"])
        self.assertEqual(migration_policy(policy, "unknown.sql")["depends_on"], [])

    def test_role_preflight_extracts_grant_and_revoke_targets(self) -> None:
        sql = """
        GRANT USAGE ON SCHEMA public TO analytics_sync_ro;
        REVOKE ALL ON TABLE farms FROM midas_ro;
        GRANT SELECT ON TABLE farms TO PUBLIC;
        GRANT SELECT ON TABLE farms TO "Analytics Sync RO";
        """
        self.assertEqual(
            extract_required_roles(sql),
            {"analytics_sync_ro", "midas_ro", "Analytics Sync RO"},
        )

    def test_role_preflight_ignores_comments_and_literals(self) -> None:
        sql = r"""
        -- GRANT SELECT ON farms TO commented_role;
        /* REVOKE ALL ON farms FROM block_role; */
        SELECT 'GRANT SELECT ON farms TO string_role;';
        SELECT $$REVOKE ALL ON farms FROM dollar_role;$$;
        SELECT $body$GRANT SELECT ON farms TO tagged_role;$body$;
        GRANT SELECT ON farms TO real_role;
        """
        self.assertEqual(extract_required_roles(sql), {"real_role"})

    def test_role_preflight_does_not_treat_select_from_as_role(self) -> None:
        sql = "SELECT * FROM farms; GRANT SELECT ON farms TO analytics_sync_ro;"
        self.assertEqual(extract_required_roles(sql), {"analytics_sync_ro"})

    def test_explicit_dependency_blocks_only_downstream_migration(self) -> None:
        ok, blocked = dependencies_satisfied(
            ["schema.sql", "roles.sql"],
            {"schema.sql": "APPLIED", "roles.sql": "QUARANTINED"},
        )
        self.assertFalse(ok)
        self.assertEqual(blocked, ["roles.sql"])

        ok, blocked = dependencies_satisfied(["schema.sql"], {"schema.sql": "RECONCILED"})
        self.assertTrue(ok)
        self.assertEqual(blocked, [])

    def test_missing_object_is_blocked_only_by_declared_failed_dependencies(self) -> None:
        exc = FakePgError("relation does not exist", "42P01")
        self.assertEqual(failure_status(exc, {"schema.sql": "QUARANTINED"}), "BLOCKED")
        self.assertEqual(failure_status(exc, {"schema.sql": "APPLIED"}), "QUARANTINED")
        self.assertEqual(failure_status(exc, {}), "QUARANTINED")

    def test_summary_is_degraded_for_noncritical_quarantine(self) -> None:
        overall, summary = summarize(
            {
                "a.sql": {"status": "APPLIED"},
                "b.sql": {"status": "QUARANTINED"},
                "c.sql": {"status": "APPLIED"},
            },
            critical_failed=False,
        )
        self.assertEqual(overall, "DEGRADED")
        self.assertEqual(summary["counts"]["APPLIED"], 2)
        self.assertEqual(summary["counts"]["QUARANTINED"], 1)

    def test_summary_fails_only_when_critical_migration_failed(self) -> None:
        overall, _summary = summarize(
            {"schema.sql": {"status": "FAILED"}}, critical_failed=True
        )
        self.assertEqual(overall, "FAILED")

    def test_upstream_lock_tracks_exact_production_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            commit = "a" * 40
            (root / "upstream.lock").write_text(
                json.dumps({
                    "repository": "Ouros-App/postgres-segundo-prod-database",
                    "branch": "main",
                    "commit": commit,
                }),
                encoding="utf-8",
            )
            self.assertEqual(read_upstream_commit(root), commit)

    def test_upstream_lock_rejects_invalid_source_or_sha(self) -> None:
        cases = [
            {"repository": "Ouros-App/other", "branch": "main", "commit": "a" * 40},
            {"repository": "Ouros-App/postgres-segundo-prod-database", "branch": "dev", "commit": "a" * 40},
            {"repository": "Ouros-App/postgres-segundo-prod-database", "branch": "main", "commit": "abc123"},
        ]
        for payload in cases:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "upstream.lock").write_text(json.dumps(payload), encoding="utf-8")
                self.assertEqual(read_upstream_commit(root), "unknown")

    def test_advisory_lock_uses_bounded_try_lock(self) -> None:
        conn = FakeLockConnection([False, False, True])
        with patch("scripts.reconcile.db.time.sleep") as sleep:
            acquire_advisory_lock(conn, 123, attempts=3, delay_seconds=0.01)
        self.assertEqual(conn.commits, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertTrue(all("pg_try_advisory_lock" in query for query, _ in conn.executed))

    def test_advisory_lock_times_out_instead_of_waiting_forever(self) -> None:
        conn = FakeLockConnection([False, False])
        with patch("scripts.reconcile.db.time.sleep"):
            with self.assertRaises(TimeoutError):
                acquire_advisory_lock(conn, 123, attempts=2, delay_seconds=0)

    def test_safe_rollback_preserves_active_exception(self) -> None:
        try:
            raise ValueError("original")
        except ValueError:
            self.assertFalse(safe_rollback(RollbackFailureConnection()))

    def test_safe_rollback_raises_when_it_is_the_primary_failure(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "rollback exploded"):
            safe_rollback(RollbackFailureConnection())


if __name__ == "__main__":
    unittest.main()
