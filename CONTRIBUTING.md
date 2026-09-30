# Contributing

SuperAuditor is a small standard, and it grows from evidence. The most useful
contribution is a report from an implementation: what you built, and where the
text did not tell you what to do.

## Adding an implementation

Open a pull request that adds a row to the table in [README.md](README.md) with:

- the server and a link to it;
- what it detects, in a few words;
- the version it claims in `_meta.superauditor`;
- the output of `superauditor-check --require-version <that version>` against it.

The checker shows only what is visible from outside. Say how your own tests show
the rest (STANDARD.md §9 lists which requirements those are).

## Proposing a change to the standard

Open an issue first. A proposal is much easier to accept when it carries:

- **the case** — the server, the detector output or response, and what went
  wrong or could not be expressed;
- **the change** — the text you would add or replace;
- **its cost to existing implementations** — whether a conforming server would
  stop conforming.

How a change is versioned (STANDARD.md §10):

- a clarification that leaves every conforming implementation conforming is a
  **minor** version;
- a change that would make a conforming implementation non-conforming is a
  **major** version, with a migration note;
- a defect in the text that lets a server leak data or report something false
  is corrected in the next minor version and says so in the changelog, as v1.1
  did for §7.

New normative requirements come from a running implementation that needed them.
A field or behaviour no implementation ships stays a proposal until one does.

## Changes to this repository

- Keep the response schema, the fixtures and `examples/reference_delivery.py` in
  step with STANDARD.md. CI runs the fixtures through the reference and runs the
  checker against conforming and deliberately broken servers.
- A new check in `superauditor-check` comes with a broken server in
  `tests/sample_server.py` that the check fails and the conforming server passes.
- Write in English.
