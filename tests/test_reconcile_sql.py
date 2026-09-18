import json
import tempfile
import unittest
from pathlib import Path

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
        """
        self.assertEqual(extract_required_roles(sql), {"analytics_sync_ro", "midas_ro"})

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

    def test_missing_object_after_failure_is_classified_as_blocked(self) -> None:
        exc = FakePgError("relation does not exist", "42P01")
        self.assertEqual(failure_status(exc, {"schema.sql": "QUARANTINED"}), "BLOCKED")
        self.assertEqual(failure_status(exc, {"schema.sql": "APPLIED"}), "QUARANTINED")

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

    def test_upstream_lock_tracks_production_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "upstream.lock").write_text(
                json.dumps({
                    "repository": "Ouros-App/postgres-segundo-prod-database",
                    "commit": "abc123",
                }),
                encoding="utf-8",
            )
            self.assertEqual(read_upstream_commit(root), "abc123")


if __name__ == "__main__":
    unittest.main()
