"""Checks on get_session_findings responses, as seen from outside the server.

Every function here is pure: it reads responses (already-parsed JSON objects)
and returns a Result. What a black box can show is limited to what two pulls at
different limits reveal; STANDARD.md §9 says which requirements that covers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources

SEVERITIES = ("critical", "warn", "info")


@dataclass
class Result:
    id: str
    ok: bool | None  # None: not checked, with the reason in detail
    detail: str


def load_schema() -> dict:
    # A built wheel carries the schema inside the package; a source checkout
    # (editable install, tests) reads the one canonical copy under schema/.
    packaged = resources.files("superauditor_check").joinpath("response.schema.json")
    if packaged.is_file():
        return json.loads(packaged.read_text())
    from pathlib import Path

    return json.loads((Path(__file__).resolve().parents[2] / "schema" / "get_session_findings.response.schema.json").read_text())


def _count(response: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in response.get("findings", []):
        counts[finding.get("kind")] = counts.get(finding.get("kind"), 0) + 1
    return counts


def _by_kind(response: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for finding in response.get("findings", []):
        out.setdefault(finding.get("kind"), []).append(finding)
    return out


def check_shape(response: dict, schema: dict) -> Result:
    import jsonschema

    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(response), key=lambda e: list(e.path))
    if errors:
        where = "/".join(str(p) for p in errors[0].path) or "(root)"
        return Result("shape", False, f"{len(errors)} schema error(s); first at {where}: {errors[0].message}")
    return Result("shape", True, "matches schema/get_session_findings.response.schema.json")


def check_echo(response: dict, limit: int) -> Result:
    got = response.get("per_kind_limit")
    if got != limit:
        return Result("echo", False, f"asked per_kind_limit={limit}, response echoes {got!r}")
    return Result("echo", True, f"per_kind_limit echoed as {limit}")


def check_c1(response: dict, limit: int) -> Result:
    over = {k: n for k, n in _count(response).items() if n > limit}
    if over:
        return Result("C1", False, f"kinds over per_kind_limit={limit}: {over}")
    return Result("C1", True, f"no kind exceeds {limit}")


def check_c3(response: dict) -> Result:
    findings = response.get("findings", [])
    problems = []
    if response.get("total") != len(findings):
        problems.append(f"total={response.get('total')!r} but {len(findings)} findings returned")
    if response.get("counts_by_kind") != _count(response):
        problems.append(f"counts_by_kind={response.get('counts_by_kind')!r}, findings give {_count(response)}")
    by_severity: dict[str, int] = {}
    for finding in findings:
        by_severity[finding.get("severity")] = by_severity.get(finding.get("severity"), 0) + 1
    if response.get("counts_by_severity") != by_severity:
        problems.append(f"counts_by_severity={response.get('counts_by_severity')!r}, findings give {by_severity}")
    if problems:
        return Result("C3", False, "; ".join(problems))
    return Result("C3", True, "total and both counts agree with findings")


def check_c4(responses: list[dict]) -> Result:
    seen: dict[str, str] = {}
    for response in responses:
        for finding in response.get("findings", []):
            kind, severity = finding.get("kind"), finding.get("severity")
            if severity not in SEVERITIES:
                return Result("C4", False, f"kind {kind!r} has severity {severity!r}, not one of {SEVERITIES}")
            if seen.setdefault(kind, severity) != severity:
                return Result("C4", False, f"kind {kind!r} delivered as both {seen[kind]!r} and {severity!r}")
    return Result("C4", True, f"{len(seen)} kind(s), one severity each")


def check_capped_consistent(response: dict, limit: int) -> Result:
    """Within one response: a capped kind returned exactly `limit` rows, and was named once."""
    capped = response.get("capped_kinds", [])
    counts = _count(response)
    problems = []
    if len(capped) != len(set(capped)):
        problems.append(f"capped_kinds repeats a kind: {capped}")
    for kind in capped:
        if counts.get(kind, 0) != limit:
            problems.append(f"{kind!r} is capped but {counts.get(kind, 0)} returned (limit {limit})")
    if problems:
        return Result("C2-self", False, "; ".join(problems))
    return Result("C2-self", True, "every capped kind returned exactly the limit")


def check_c2(low: dict, low_limit: int, high: dict, high_limit: int) -> Result:
    """Two pulls: a kind with more than `low_limit` findings at the higher limit was capped at the lower one,
    and a kind reported capped at the lower limit does have more than `low_limit`."""
    if high_limit <= low_limit:
        return Result("C2", None, "needs a higher second limit")
    n_low, n_high = _count(low), _count(high)
    capped_low, capped_high = set(low.get("capped_kinds", [])), set(high.get("capped_kinds", []))
    problems = []
    for kind in sorted(set(n_low) | set(n_high) | capped_low, key=str):
        exists_more = n_high.get(kind, 0) > low_limit or kind in capped_high
        if exists_more and kind not in capped_low:
            problems.append(f"{kind!r}: {n_high.get(kind, 0)} at limit {high_limit} but not capped at {low_limit}")
        if kind in capped_low and not exists_more:
            problems.append(
                f"{kind!r}: capped at {low_limit} but only {n_high.get(kind, 0)} exist at limit {high_limit}"
                " (capped inferred from count == limit?)"
            )
        if kind not in capped_high and n_high.get(kind, 0) <= low_limit and n_low.get(kind, 0) != n_high.get(kind, 0):
            problems.append(f"{kind!r}: {n_low.get(kind, 0)} returned at {low_limit}, {n_high.get(kind, 0)} at {high_limit}")
    if problems:
        return Result("C2", False, "; ".join(problems))
    return Result("C2", True, f"capped_kinds at limit {low_limit} agrees with a pull at {high_limit}")


def check_prefix(low: dict, high: dict) -> Result:
    """§6: the rows kept at the lower limit are the first rows of the same kind at the higher limit."""
    low_by, high_by = _by_kind(low), _by_kind(high)
    for kind, rows in low_by.items():
        head = high_by.get(kind, [])[: len(rows)]
        if [json.dumps(r, sort_keys=True) for r in rows] != [json.dumps(r, sort_keys=True) for r in head]:
            return Result("order", False, f"kind {kind!r}: rows kept at the lower limit are not the first rows at the higher one")
    return Result("order", True, "each kind's rows at the lower limit lead the higher pull")


def check_summary(with_summary: dict, without_summary: dict) -> Result:
    if not isinstance(with_summary.get("summary"), str):
        return Result("summary", False, "include_summary=true returned no summary string")
    if "summary" in without_summary:
        return Result("summary", False, "include_summary=false still returned a summary")
    return Result("summary", True, "present when asked for, absent when declined")


def check_version(response: dict, required: str | None) -> Result:
    meta = response.get("_meta") or {}
    claimed = meta.get("superauditor")
    if claimed is None:
        if required:
            return Result("C12", False, f"no _meta.superauditor; {required} required")
        return Result("C12", None, "no _meta.superauditor: read as a v1 implementation")
    if required and _version(claimed) < _version(required):
        return Result("C12", False, f"claims {claimed}, {required} required")
    return Result("C12", True, f"claims SuperAuditor {claimed}")


def _version(text: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(text).split("."))
    except ValueError:
        return (-1,)  # malformed; the schema check names it
