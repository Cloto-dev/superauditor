"""SuperAuditor v1.1 — the delivery seam, to copy into your server.

Copy this file; do not depend on it (STANDARD.md: no shared library). It uses
the standard library only. What you supply:

- ``SEVERITY``: a static map from every kind your probes emit to a severity
  (STANDARD.md §4). Keep a test that fails when a probe emits a kind with no
  entry (C6).
- ``run_probes(limit, session_key)``: your detector. It returns findings in a
  stable order, each a dict with a ``kind`` and whatever payload a consumer
  needs, at most ``limit`` per kind. It must not write anything.

Then register ``get_session_findings`` as a read-only tool that returns
``get_session_findings(...)`` below, and run ``superauditor-check`` against the
server.

Two things this file leaves to you. If a probe raises, let the exception fail
the call (§5.4) — or catch it and emit a ``check_crashed`` finding naming the
probe instead of its findings. And if your server runs behind a shared remote
transport and the caller declared no ``session_key``, add
``"identity_shared": True`` to the response (§7).
"""

SUPERAUDITOR_VERSION = "1.1"
DEFAULT_PER_KIND_LIMIT = 5
FALLBACK_SEVERITY = "info"  # §4 rule 2: an unmapped kind never raises an alarm


def deliver(detector_output, per_kind_limit, severity):
    """Trim to per_kind_limit per kind, name the kinds that had more, count what is returned (§5.2, §6)."""
    kept, seen, capped = [], {}, []
    for finding in detector_output:
        if "severity" in finding:
            # §3: the probe's own value would be silently replaced below. Move it to another key.
            raise ValueError(f"probe for kind {finding['kind']!r} emitted its own 'severity'")
        kind = finding["kind"]
        seen[kind] = seen.get(kind, 0) + 1
        if seen[kind] > per_kind_limit:
            if kind not in capped:
                capped.append(kind)  # observed from the extra row, never inferred from == limit
            continue
        kept.append({**finding, "severity": severity.get(kind, FALLBACK_SEVERITY)})
    by_kind, by_severity = {}, {}
    for finding in kept:
        by_kind[finding["kind"]] = by_kind.get(finding["kind"], 0) + 1
        by_severity[finding["severity"]] = by_severity.get(finding["severity"], 0) + 1
    return {
        "findings": kept,
        "total": len(kept),  # returned, not existing: capped_kinds says when more exist
        "counts_by_kind": by_kind,
        "counts_by_severity": by_severity,
        "capped_kinds": capped,
        "per_kind_limit": per_kind_limit,
    }


def render_summary(delivered):
    """Prose rendered from the trimmed set, so it cannot disagree with the structure."""
    if not delivered["findings"]:
        return "Findings: none."
    kinds = ", ".join(f"{k} {n}" for k, n in delivered["counts_by_kind"].items())
    text = f"Findings: {delivered['total']} returned; {kinds}."
    if delivered["capped_kinds"]:
        text += f" More exist for: {', '.join(delivered['capped_kinds'])}."
    return text


def get_session_findings(run_probes, severity, server_version, session_key=None,
                         per_kind_limit=DEFAULT_PER_KIND_LIMIT, include_summary=True):
    """The tool body. Probing at limit + 1 is what makes capped_kinds an observation."""
    if isinstance(per_kind_limit, bool) or not isinstance(per_kind_limit, int) or per_kind_limit < 1:
        # §5.1: never apply it. A limit of 0 would return an empty set that reads as "no findings".
        raise ValueError(f"per_kind_limit must be an integer of at least 1, got {per_kind_limit!r}")
    detector_output = run_probes(per_kind_limit + 1, session_key)
    response = deliver(detector_output, per_kind_limit, severity)
    if include_summary:
        response["summary"] = render_summary(response)
    response["_meta"] = {"server_version": server_version, "superauditor": SUPERAUDITOR_VERSION}
    return response
