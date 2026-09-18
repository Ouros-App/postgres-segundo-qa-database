from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

POLICY_FILE = "reconcile.yaml"
UPSTREAM_LOCK_FILE = "upstream.lock"
EXPECTED_UPSTREAM_REPOSITORY = "Ouros-App/postgres-segundo-prod-database"
EXPECTED_UPSTREAM_BRANCH = "main"
SUCCESS_STATUSES = {"APPLIED", "RECONCILED", "UNCHANGED", "BASELINED"}
FAILURE_STATUSES = {"QUARANTINED", "BLOCKED", "FAILED"}
DEPENDENCY_SQLSTATES = {"3F000", "42P01", "42703", "42704", "42883"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
DOLLAR_QUOTE_RE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")
ROLE_IDENTIFIER_RE = re.compile(r'"(?:""|[^"])*"|[A-Za-z_][A-Za-z0-9_$]*')
GRANT_TARGET_RE = re.compile(r"\bTO\b", re.IGNORECASE)
REVOKE_TARGET_RE = re.compile(r"\bFROM\b", re.IGNORECASE)
ROLE_TAIL_RE = re.compile(
    r"\b(?:WITH\s+GRANT\s+OPTION|WITH\s+ADMIN\s+OPTION|CASCADE|RESTRICT)\b",
    re.IGNORECASE,
)
SPECIAL_ROLE_KEYWORDS = {"PUBLIC", "CURRENT_USER", "SESSION_USER", "CURRENT_ROLE"}


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


def _mask_sql_comments_and_literals(content: str) -> str:
    """Mask SQL comments and string/dollar literals while preserving statements."""
    out = list(content)
    length = len(content)
    i = 0
    block_depth = 0

    def mask(start: int, end: int) -> None:
        """Replace token contents with spaces while preserving newlines."""
        for pos in range(start, end):
            if out[pos] != "\n":
                out[pos] = " "

    while i < length:
        if block_depth:
            if content.startswith("/*", i):
                mask(i, i + 2)
                block_depth += 1
                i += 2
                continue
            if content.startswith("*/", i):
                mask(i, i + 2)
                block_depth -= 1
                i += 2
                continue
            mask(i, i + 1)
            i += 1
            continue

        if content.startswith("--", i):
            end = content.find("\n", i + 2)
            if end == -1:
                end = length
            mask(i, end)
            i = end
            continue

        if content.startswith("/*", i):
            mask(i, i + 2)
            block_depth = 1
            i += 2
            continue

        if content[i] == "'":
            start = i
            i += 1
            while i < length:
                if content[i] == "'":
                    if i + 1 < length and content[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            mask(start, i)
            continue

        if content[i] == "$":
            delimiter_match = DOLLAR_QUOTE_RE.match(content, i)
            if delimiter_match:
                delimiter = delimiter_match.group(0)
                start = i
                body_start = delimiter_match.end()
                end = content.find(delimiter, body_start)
                i = length if end == -1 else end + len(delimiter)
                mask(start, i)
                continue

        i += 1

    return "".join(out)


def _decode_role_identifier(token: str) -> tuple[str, bool]:
    """Decode a PostgreSQL role identifier and report whether it was quoted."""
    token = token.strip()
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1].replace('""', '"'), True
    return token, False


def _statement_roles(statement: str) -> set[str]:
    """Extract role targets from one masked GRANT or REVOKE statement."""
    stripped = statement.strip()
    if not stripped:
        return set()

    upper = stripped.upper()
    if upper.startswith("GRANT "):
        matches = list(GRANT_TARGET_RE.finditer(stripped))
    elif upper.startswith("REVOKE "):
        matches = list(REVOKE_TARGET_RE.finditer(stripped))
    else:
        return set()
    if not matches:
        return set()

    clause = stripped[matches[-1].end():]
    tail = ROLE_TAIL_RE.search(clause)
    if tail:
        clause = clause[:tail.start()]

    roles: set[str] = set()
    cursor = 0
    while cursor < len(clause):
        while cursor < len(clause) and (clause[cursor].isspace() or clause[cursor] == ","):
            cursor += 1
        if cursor >= len(clause):
            break
        match = ROLE_IDENTIFIER_RE.match(clause, cursor)
        if not match:
            break
        role, quoted = _decode_role_identifier(match.group(0))
        if quoted or role.upper() not in SPECIAL_ROLE_KEYWORDS:
            roles.add(role)
        cursor = match.end()
    return roles


def extract_required_roles(content: str) -> set[str]:
    """Find GRANT/REVOKE targets while ignoring comments and SQL literals."""
    masked = _mask_sql_comments_and_literals(content)
    roles: set[str] = set()
    for statement in masked.split(";"):
        roles.update(_statement_roles(statement))
    return roles


def read_upstream_commit(root: Path) -> str:
    """Read and validate the exact production commit mirrored by the sync workflow."""
    path = root / UPSTREAM_LOCK_FILE
    if not path.is_file():
        return "unknown"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "unknown"
    if not isinstance(payload, dict):
        return "unknown"
    if payload.get("repository") != EXPECTED_UPSTREAM_REPOSITORY:
        return "unknown"
    if payload.get("branch") != EXPECTED_UPSTREAM_BRANCH:
        return "unknown"
    commit = payload.get("commit")
    return commit if isinstance(commit, str) and SHA_RE.fullmatch(commit) else "unknown"


def dependencies_satisfied(depends_on: list[str], results: dict[str, str]) -> tuple[bool, list[str]]:
    """Require explicit dependencies to be healthy in the current run."""
    blocked = [dep for dep in depends_on if results.get(dep) not in SUCCESS_STATUSES]
    return not blocked, blocked


def error_payload(exc: BaseException) -> tuple[str | None, str]:
    """Normalize database/Python failures for quarantine metadata."""
    code = getattr(exc, "pgcode", None)
    detail = str(exc).strip() or exc.__class__.__name__
    return code, detail[:4000]


def failure_status(exc: BaseException, dependency_results: dict[str, str]) -> str:
    """Classify an object error as BLOCKED only when a declared dependency failed."""
    code = getattr(exc, "pgcode", None)
    if code in DEPENDENCY_SQLSTATES and any(
        status in FAILURE_STATUSES for status in dependency_results.values()
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
