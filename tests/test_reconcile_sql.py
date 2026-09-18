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
    """Minimal PostgreSQL-style exception used by classification tests."""

    def __init__(self, message: str, pgcode: str | None = None):
        """Store an optional PostgreSQL SQLSTATE code."""
        super().__init__(message)
        self.pgcode = pgcode


class RollbackFailureConnection:
    """Connection double whose rollback always fails."""

    def rollback(self):
        """Raise a deterministic rollback failure."""
        raise RuntimeError("rollback exploded")


class FakeLockCursor:
    """Cursor double for advisory lock retry tests."""

    def __init__(self, connection):
        """Bind the cursor to its fake connection."""
        self.connection = connection

    def __enter__(self):
        """Enter the cursor context manager."""
        return self

    def __exit__(self, *_args):
        """Leave the cursor context without suppressing exceptions."""
        return False

    def execute(self, query, params=None):
        """Record SQL issued by the lock helper."""
        self.connection.executed.append((query, params))

    def fetchone(self):
        """Return the next configured advisory-lock outcome."""
        return (self.connection.outcomes.pop(0),)


class FakeLockConnection:
    """Connection double that simulates advisory-lock attempts."""

    def __init__(self, outcomes):
        """Initialize deterministic lock outcomes and counters."""
        self.outcomes = list(outcomes)
        self.executed = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        """Return a cursor bound to this connection double."""
        return FakeLockCursor(self)

    def commit(self):
        """Count transaction commits."""
        self.commits += 1

    def rollback(self):
        """Count transaction rollbacks."""
        self.rollbacks += 1


class ReconcileSqlTest(unittest.TestCase):
    def test_default_policy_prefers_reconciliation_and_data_preservation(self) -> None:
        """Verify conservative defaults preserve QA data while enabling repair."""
        with tempfile.TemporaryDirectory() as tmp:
            policy = load_reconcile_policy(Path(tmp))
        self.assertTrue(policy["continue_on_error"])
        self.assertTrue(policy["reapply_on_change"])
        self.assertTrue(policy["preserve_data"])
        self.assertEqual(policy["unexpected_objects"], "report_only")

    def test_policy_supports_critical_and_dependency_metadata(self) -> None:
        """Verify per-migration criticality and dependencies are normalized."""
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
        """Verify ordinary SELECT FROM clauses are not interpreted as roles."""
        sql = "SELECT * FROM farms; GRANT SELECT ON farms TO analytics_sync_ro;"
        self.assertEqual(extract_required_roles(sql), {"analytics_sync_ro"})

    def test_explicit_dependency_blocks_only_downstream_migration(self) -> None:
        """Verify only declared unhealthy dependencies block a migration."""
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
        """Verify SQLSTATE classification uses declared dependencies only."""
        exc = FakePgError("relation does not exist", "42P01")
        self.assertEqual(failure_status(exc, {"schema.sql": "QUARANTINED"}), "BLOCKED")
        self.assertEqual(failure_status(exc, {"schema.sql": "APPLIED"}), "QUARANTINED")
        self.assertEqual(failure_status(exc, {}), "QUARANTINED")

    def test_summary_is_degraded_for_noncritical_quarantine(self) -> None:
        """Verify noncritical quarantine produces a DEGRADED run."""
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
        """Verify critical migration failures produce a FAILED run."""
        overall, _summary = summarize(
            {"schema.sql": {"status": "FAILED"}}, critical_failed=True
        )
        self.assertEqual(overall, "FAILED")

    def test_upstream_lock_tracks_exact_production_commit(self) -> None:
        """Verify a valid upstream lock preserves the exact production SHA."""
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
        """Verify invalid repository, branch, or SHA metadata fails closed."""
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
        """Verify advisory lock acquisition retries for a bounded period."""
        conn = FakeLockConnection([False, False, True])
        with patch("scripts.reconcile.db.time.sleep") as sleep:
            acquire_advisory_lock(conn, 123, attempts=3, delay_seconds=0.01)
        self.assertEqual(conn.commits, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertTrue(all("pg_try_advisory_lock" in query for query, _ in conn.executed))

    def test_advisory_lock_times_out_instead_of_waiting_forever(self) -> None:
        """Verify lock contention cannot block reconciliation indefinitely."""
        conn = FakeLockConnection([False, False])
        with patch("scripts.reconcile.db.time.sleep"):
            with self.assertRaises(TimeoutError):
                acquire_advisory_lock(conn, 123, attempts=2, delay_seconds=0)

    def test_safe_rollback_preserves_active_exception(self) -> None:
        """Verify rollback failure cannot mask the primary exception."""
        try:
            raise ValueError("original")
        except ValueError:
            self.assertFalse(safe_rollback(RollbackFailureConnection()))

    def test_safe_rollback_raises_when_it_is_the_primary_failure(self) -> None:
        """Verify rollback failures still surface when no primary error exists."""
        with self.assertRaisesRegex(RuntimeError, "rollback exploded"):
            safe_rollback(RollbackFailureConnection())


if __name__ == "__main__":
    unittest.main()
