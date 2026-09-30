# SuperAuditor

A small open standard for how an MCP server hands over the problems it finds in
its own stored state — stale records, contradictions, broken indexes — **on
request, with honest counts**, instead of attaching them to every response.
This repository holds the standard, its response schema, conformance fixtures,
a reference implementation to copy, and a checker that tells you whether a
running server conforms.

- [STANDARD.md](STANDARD.md) — the standard (v1.1)
- [schema/](schema/) — JSON Schema for the response
- [conformance/v1/](conformance/v1/) — language-independent fixtures
- [examples/reference_delivery.py](examples/reference_delivery.py) — the seam in about 70 lines of standard-library Python, to copy
- `superauditor-check` — the black-box checker (this package)

## Why

A server that already computes findings about itself has to decide when to hand
them over. Attaching them to every read is the easy choice and an expensive one:
in the first implementation, the findings block was a median of 44% of the
responses it rode on, and the only consumer read it once, at the end of a
session. SuperAuditor keeps detection as it is and makes delivery a pull.

## The contract in one screen

```
get_session_findings(session_key?, per_kind_limit = 5, include_summary = true)
```

```json
{
  "findings": [ { "kind": "stale_pending", "severity": "info", "task_id": 6, "days_stale": 62 } ],
  "total": 1,
  "counts_by_kind": { "stale_pending": 1 },
  "counts_by_severity": { "info": 1 },
  "capped_kinds": ["stale_pending"],
  "per_kind_limit": 1,
  "summary": "Findings: 1 returned; stale_pending 1. More exist for: stale_pending.",
  "_meta": { "server_version": "1.4.0", "superauditor": "1.1" }
}
```

- `severity` is one of `critical`, `warn`, `info`, and is a fixed property of
  the `kind`, never of one finding.
- `total` counts what was returned. `capped_kinds` names every kind that has
  more than were returned, observed, never guessed.
- The tool is read-only. What a server detects is its own business.

## Add it to your server

1. **Name your findings.** Give every kind of finding your probes emit a fixed
   severity in one table, and keep a test that fails when a probe emits a kind
   the table does not have.
2. **Add the tool.** Copy [examples/reference_delivery.py](examples/reference_delivery.py)
   and register `get_session_findings` as a read-only tool that returns its
   `get_session_findings(...)`. Your probes are called once, at the limit plus
   one.
3. **Check it:**

   ```bash
   uvx --from git+https://github.com/Cloto-dev/superauditor superauditor-check -- <command that starts your server>
   # or, for a server over streamable HTTP:
   uvx --from git+https://github.com/Cloto-dev/superauditor superauditor-check --url https://example.com/mcp --header "Authorization: Bearer $TOKEN"
   ```

The checker pulls the findings three times — with no arguments, at
`per_kind_limit=1` and at `per_kind_limit=200` — and compares the pulls: a kind
with two or more findings at the higher limit must have been reported capped at
the lower one, and the rows kept at the lower limit must be the first rows of
the higher pull. It reads nothing and writes nothing else. Some requirements
cannot be seen from outside; [STANDARD.md §9](STANDARD.md#9-conformance) says
which, and how to show them with your own tests.

## Use it from an agent

Nothing to install. Put this in the agent's instructions file (`CLAUDE.md`,
`AGENTS.md`, or your client's equivalent):

> When a session's work is done, call `get_session_findings` once on each server
> that offers it, passing your session key if you have one. Act on `warn` and
> `critical` findings, or say why not; `info` is a judgment call. `total` counts
> what was returned, not what exists: if `capped_kinds` names a kind, there are
> more — pull again with a higher `per_kind_limit` only for a kind you intend to
> clear. Do not call it on every turn.

## Implementations

| Server | What it detects | Conforms to |
| --- | --- | --- |
| [CPersona](https://github.com/Cloto-dev/CPersona) 2.5.10 and later | storage integrity of an agent's memory store | v1 (v1.1 in progress) |
| CScheduler (the pilot; not publicly distributed) | drift in a plan graph of scopes, goals and tasks | v1 (v1.1 in progress) |

Both are Python servers by the same maintainer. A third implementation, in
another language or by another team, is the evidence this standard most needs:
open an issue with what did not fit.

## Status and versioning

v1.1. Minor versions only add clarifications; a change that would make a
conforming implementation non-conforming is a new major version with a
migration note. A server states the version it conforms to in
`_meta.superauditor`.

## License

MIT — see [LICENSE](LICENSE).
