from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any


def write_github_summary(
    summary: dict[str, Any],
    prod_commit: str,
    qa_commit: str,
    roles_repaired: list[str],
    core_missing_before: list[str],
    core_missing_after: list[str],
) -> None:
    """Publish a compact reconciliation report to the GitHub Actions summary."""
    lines = [
        "## QA SQL Reconciliation",
        "",
        f"- **Status:** `{summary['overall']}`",
        f"- **Production commit:** `{prod_commit}`",
        f"- **QA commit:** `{qa_commit}`",
        f"- **Generated:** `{datetime.now(timezone.utc).isoformat()}`",
        "",
    ]
    if roles_repaired:
        lines.extend(["### Security drift repaired", ""])
        lines.extend(f"- ✅ role `{role}` recriada/provisionada" for role in roles_repaired)
        lines.append("")
    if core_missing_before:
        lines.extend(["### Core schema drift", ""])
        lines.append("Missing before: " + ", ".join(f"`{x}`" for x in core_missing_before))
        after = ", ".join(f"`{x}`" for x in core_missing_after) if core_missing_after else "none"
        lines.append("Missing after: " + after)
        lines.append("")
    lines.extend(["### Migrations", "", "| Migration | Status | Reason |", "| --- | --- | --- |"])
    for identity, item in summary["items"].items():
        reason = (item.get("reason") or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{identity}` | **{item['status']}** | {reason} |")
    lines.extend(["", "### Counts", ""])
    for status, count in sorted(summary["counts"].items()):
        lines.append(f"- `{status}`: {count}")
    content = "\n".join(lines) + "\n"
    if path := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(content)
    print(content)
