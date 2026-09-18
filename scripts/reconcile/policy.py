from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

POLICY_FILE = "reconcile.yaml"
UPSTREAM_LOCK_FILE = "upstream.lock"
SUCCESS_STATUSES = {"APPLIED", "RECONCILED", "UNCHANGED", "BASELINED"}
FAILURE_STATUSES = {"QUARANTINED", "BLOCKED", "FAILED"}
DEPENDENCY_SQLSTATES = {"3F000", "42P01", "42703", "42704", "42883"}
ROLE_REFERENCE_RE = re.compile(
    r"\b(?:TO|FROM)\s+([A-Za-z_][A-Za-z0-9_$]*)\s*;", re.IGNORECASE
)


def load_reconcile_policy(root: Path) -> dict[str, Any]:
    """Load QA-only reconciliation behavior without modifying prod config."""
    import yaml

    path = root / POLICY_FILE
    raw: dict[str, Any] = {}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{POLICY_FILE} deve conter um objeto YAML")
        raw = loaded.get("reconciliation", loaded)
        if not isinstance(raw, dict):
            raise ValueError("reconciliation deve ser um objeto YAML")

    policy: dict[str, Any] = {
        "continue_on_error": bool(raw.get("continue_on_error", True)),
        "reapply_on_change": bool(raw.get("reapply_on_change", True)),
        "preserve_data": bool(raw.get("preserve_data", True)),
        "unexpected_objects": raw.get("unexpected_objects", "report_only"),
        "migrations": raw.get("migrations", {}) or {},
    }
    if policy["unexpected_objects"] not in {"report_only", "ignore"}:
        raise ValueError("unexpected_objects deve ser report_only ou ignore")
    if not isinstance(policy["migrations"], dict):
        raise ValueError("reconciliation.migrations deve ser um objeto")
    return policy


def migration_policy(policy: dict[str, Any], identity: str) -> dict[str, Any]:
    """Return normalized per-migration QA reconciliation policy."""
    raw = policy.get("migrations", {}).get(identity, {}) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Politica invalida para migration {identity}")
    depends_on = raw.get("depends_on", []) or []
    if not isinstance(depends_on, list) or not all(isinstance(item, str) for item in depends_on):
        raise ValueError(f"depends_on invalido para {identity}")
    return {"critical": bool(raw.get("critical", False)), "depends_on": depends_on}


def extract_required_roles(content: str) -> set[str]:
    """Find GRANT/REVOKE role targets that must exist before migration execution."""
    roles = {match.group(1) for match in ROLE_REFERENCE_RE.finditer(content)}
    return {role for role in roles if role.upper() != "PUBLIC"}


def read_upstream_commit(root: Path) -> str:
    """Read the exact production commit mirrored by the sync workflow."""
    path = root / UPSTREAM_LOCK_FILE
    if not path.is_file():
        return "unknown"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "unknown"
    commit = payload.get("commit") if isinstance(payload, dict) else None
    return commit if isinstance(commit, str) and commit else "unknown"


def dependencies_satisfied(depends_on: list[str], results: dict[str, str]) -> tuple[bool, list[str]]:
    """Require explicit dependencies to be healthy in the current run."""
    blocked = [dep for dep in depends_on if results.get(dep) not in SUCCESS_STATUSES]
    return not blocked, blocked


def error_payload(exc: BaseException) -> tuple[str | None, str]:
    """Normalize database/Python failures for quarantine metadata."""
    code = getattr(exc, "pgcode", None)
    detail = str(exc).strip() or exc.__class__.__name__
    return code, detail[:4000]


def failure_status(exc: BaseException, earlier_results: dict[str, str]) -> str:
    """Classify downstream missing-object failures as BLOCKED."""
    code = getattr(exc, "pgcode", None)
    if code in DEPENDENCY_SQLSTATES and any(
        status in FAILURE_STATUSES for status in earlier_results.values()
    ):
        return "BLOCKED"
    return "QUARANTINED"


def summarize(results: dict[str, dict[str, Any]], critical_failed: bool) -> tuple[str, dict[str, Any]]:
    """Build a HEALTHY/DEGRADED/FAILED reconciliation summary."""
    counts: dict[str, int] = {}
    for item in results.values():
        status = item["status"]
        counts[status] = counts.get(status, 0) + 1
    degraded = any(status in FAILURE_STATUSES for status in counts)
    overall = "FAILED" if critical_failed else "DEGRADED" if degraded else "HEALTHY"
    return overall, {"overall": overall, "counts": counts, "items": results}
