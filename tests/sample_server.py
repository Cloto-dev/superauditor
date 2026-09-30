"""A tiny MCP server with get_session_findings, conforming or broken on purpose (SA_VARIANT).

The conforming variant is examples/reference_delivery.py as a server would use
it. Each other variant breaks exactly one requirement, so a checker that does
not fail on it is not checking that requirement.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))

import reference_delivery as ref  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402

VARIANT = os.environ.get("SA_VARIANT", "conforming")
SEVERITY = {"stale": "info", "contradiction": "warn", "orphan": "info"}
# Three kinds: 3 rows, 1 row, 2 rows. At a limit of 1 the first and last are capped and the middle
# one sits exactly at the limit, which is where a cap inferred from count == limit goes wrong.
DETECTED = [
    {"kind": "stale", "id": 1}, {"kind": "contradiction", "id": 2}, {"kind": "stale", "id": 3},
    {"kind": "orphan", "id": 4}, {"kind": "stale", "id": 5}, {"kind": "orphan", "id": 6},
]


def run_probes(limit, session_key):
    if VARIANT == "raises":
        raise RuntimeError("probe failed")
    out, seen = [], {}
    for finding in DETECTED:
        seen[finding["kind"]] = seen.get(finding["kind"], 0) + 1
        if seen[finding["kind"]] <= limit:
            out.append(dict(finding))
    return out


def respond(session_key, per_kind_limit, include_summary):
    if per_kind_limit < 1 and VARIANT == "applies_zero":
        response = ref.deliver(run_probes(per_kind_limit + 1, session_key), per_kind_limit, SEVERITY)
        response["_meta"] = {"server_version": "0.0.1", "superauditor": ref.SUPERAUDITOR_VERSION}
        return response
    if per_kind_limit < 1 and VARIANT == "defaults_on_zero":
        per_kind_limit = ref.DEFAULT_PER_KIND_LIMIT
    response = ref.get_session_findings(run_probes, SEVERITY, "0.0.1", session_key, per_kind_limit, include_summary)
    if VARIANT == "silent_truncation":
        response["capped_kinds"] = []
    elif VARIANT == "inferred_cap":
        response["capped_kinds"] = [k for k, n in response["counts_by_kind"].items() if n == per_kind_limit]
    elif VARIANT == "keeps_last":
        kept = []
        for kind in dict.fromkeys(f["kind"] for f in DETECTED):
            rows = [dict(f, severity=SEVERITY[kind]) for f in DETECTED if f["kind"] == kind]
            kept += rows[-per_kind_limit:]
        response["findings"] = kept
    elif VARIANT == "true_total":
        response["total"] = len(DETECTED)
    elif VARIANT == "instance_severity":
        for finding in response["findings"]:
            if finding["kind"] == "stale" and finding["id"] == 3:
                finding["severity"] = "warn"
        response["counts_by_severity"] = {}
        for finding in response["findings"]:
            response["counts_by_severity"][finding["severity"]] = response["counts_by_severity"].get(finding["severity"], 0) + 1
    elif VARIANT == "no_version":
        del response["_meta"]["superauditor"]
    elif VARIANT == "summary_always_off":
        response.pop("summary", None)
    return response


server = MCPServer("superauditor-sample")


@server.tool(name="get_session_findings", description="Findings on demand (SuperAuditor).")
def get_session_findings(session_key: str | None = None, per_kind_limit: int = 5, include_summary: bool = True) -> dict:
    return respond(session_key, per_kind_limit, include_summary)


if __name__ == "__main__":
    server.run("stdio")
