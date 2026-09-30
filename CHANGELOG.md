# Changelog

## v1.1 — draft

Clarifications from the second implementation, plus one key. A v1 implementation
conforms to v1.1 once it adds `_meta.superauditor` and meets C10 and C11.

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
- §9: C10–C12, and which requirements the fixtures, the checker or an
  implementation's own tests can show.
- New in this repository: the response JSON Schema, a reference delivery
  transform to copy, and `superauditor-check`, a black-box checker.

## v1 — 2026-07-31

Extracted from the CScheduler 0.9.0 pilot: the finding object, the severity
vocabulary and its static assignment, the `get_session_findings` pull tool,
honest caps, session identity and isolation, and the migration contract for an
existing broadcast. Published in the CPersona repository with the conformance
fixtures now in `conformance/v1/`.
