# Changelog

## v1.1 — 2026-09-30

Clarifications from the second implementation, one key, and one correction. A
v1 implementation conforms to v1.1 once it adds `_meta.superauditor` and meets
C10, C11, C13 and C14.

- §7 (correction): an authorization boundary is not a read filter. A response
  never contains findings about data the caller may not read; within that
  authority, read filters are still not inherited. v1 listed "tenant" among the
  axes not to filter by, which required disclosing one tenant's findings to
  another where a tenant is an authorization boundary.
- §5.1: `per_kind_limit` below 1 is refused, or replaced by the default and
  echoed; it is never applied.

- §3: a detector's own `kind` or `severity` is never delivered under the
  reserved name; it is moved to another payload key, and a move never
  overwrites a key the detector already emitted.
- §4: a detector that escalates by a deterministic rule gives each tier its
  own kind with its own static severity.
- §5.2: `_meta.superauditor` states the version of the standard a response
  conforms to. Absent means v1.
- §5.4: a probe that did not run is reported, as a failed call or as a
  `check_crashed` finding in place of its findings.
- §6: the true number of findings in a capped kind stays out of scope.
- §9: C10–C14, and which requirements the fixtures, the checker or an
  implementation's own tests can show.
- New in this repository: the response JSON Schema, a reference delivery
  transform to copy, and `superauditor-check`, a black-box checker.

## v1 — 2026-07-31

Extracted from the CScheduler 0.9.0 pilot: the finding object, the severity
vocabulary and its static assignment, the `get_session_findings` pull tool,
honest caps, session identity and isolation, and the migration contract for an
existing broadcast. Published in the CPersona repository with the conformance
fixtures now in `conformance/v1/`.
