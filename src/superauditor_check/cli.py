"""superauditor-check: check a running MCP server's get_session_findings against the SuperAuditor standard.

    superauditor-check -- <command that starts the server over stdio> [args...]
    superauditor-check --url https://host/mcp [--header "Name: value"]

Findings are live state, so the pulls run back to back, and a two-pull check
that fails is run once more before it is reported.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from superauditor_check import checks
from superauditor_check.client import ToolError, call_json, find_tool, open_session

PARAMETERS = ("session_key", "per_kind_limit", "include_summary")


async def run(args) -> tuple[list[checks.Result], str | None]:
    results: list[checks.Result] = []
    claimed = None
    base = {"session_key": args.session_key} if args.session_key else {}
    async with open_session(args.command or None, args.url, dict(args.header)) as session:
        tool = await find_tool(session, args.tool)
        if tool is None:
            return [checks.Result("tool", False, f"server lists no tool named {args.tool!r}")], None
        declared = set((tool.input_schema or {}).get("properties", {}) if hasattr(tool, "input_schema")
                       else (tool.inputSchema or {}).get("properties", {}))
        missing = [p for p in PARAMETERS if p not in declared]
        results.append(checks.Result("tool", not missing,
                                     f"missing parameters: {missing}" if missing else f"{args.tool} declares {', '.join(PARAMETERS)}"))

        default = await call_json(session, args.tool, dict(base))
        claimed = checks.claimed_version(default)
        schema = checks.load_schema()
        results.append(checks.check_shape(default, schema))
        results.append(checks.Result("default", default.get("per_kind_limit") == 5 and isinstance(default.get("summary"), str),
                                     f"no arguments: per_kind_limit={default.get('per_kind_limit')!r}, "
                                     f"summary {'present' if 'summary' in default else 'absent'} (expected 5, present)"))

        for attempt in (1, 2):
            low = await call_json(session, args.tool, {**base, "per_kind_limit": args.low, "include_summary": True})
            high = await call_json(session, args.tool, {**base, "per_kind_limit": args.high, "include_summary": False})
            pair = [checks.check_c2(low, args.low, high, args.high), checks.check_prefix(low, high)]
            if all(r.ok is not False for r in pair) or attempt == 2:
                break
        for response in (low, high):
            results.append(checks.check_shape(response, schema))
        try:
            zero = await call_json(session, args.tool, {**base, "per_kind_limit": 0})
            results.append(checks.check_zero_limit("response", zero))
        except ToolError:
            results.append(checks.check_zero_limit("tool_error", None))
        results += [
            checks.check_echo(low, args.low),
            checks.check_echo(high, args.high),
            checks.check_c1(low, args.low),
            checks.check_c1(high, args.high),
            checks.check_capped_consistent(low, args.low),
            checks.check_capped_consistent(high, args.high),
            checks.check_c3(low),
            checks.check_c3(high),
            checks.check_c4([default, low, high]),
            *pair,
            checks.check_summary(low, high),
            checks.check_version(default, args.require_version),
        ]
        results.append(checks.Result("findings", None,
                                     f"{high.get('total')} returned at limit {args.high} "
                                     f"({len(high.get('counts_by_kind', {}))} kind(s), capped: {high.get('capped_kinds')})"))
    return _collapse(results), claimed


def _collapse(results: list[checks.Result]) -> list[checks.Result]:
    """One line per check id: the first failure, else the first pass."""
    by_id: dict[str, checks.Result] = {}
    for r in results:
        prev = by_id.get(r.id)
        if prev is None or (r.ok is False and prev.ok is not False):
            by_id[r.id] = r
    return list(by_id.values())


def verdict(failed: list, claimed: str | None) -> str:
    """The last line names the version the result is about, so a pass is never read as more than it is."""
    if failed:
        return f"{len(failed)} check(s) failed."
    if claimed is None:
        return ("Passes the externally checkable requirements of SuperAuditor v1 only: the server names no version "
                "in _meta.superauditor, so it is read as v1. Add --require-version 1.1 to require v1.1.")
    return (f"Passes the externally checkable requirements of SuperAuditor {claimed}, the version the server claims. "
            "STANDARD.md section 9 lists the requirements only the server's own tests can show.")


def _describe(exc: BaseException) -> str:
    """The innermost message: the transport wraps a failed call in exception groups."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    if isinstance(exc, ToolError):
        return f"{exc} (a failed call is how a server may report a probe that did not run; STANDARD.md 5.4)"
    return f"{type(exc).__name__}: {exc}"


def _header(text: str) -> tuple[str, str]:
    name, sep, value = text.partition(":")
    if not sep:
        raise argparse.ArgumentTypeError(f"expected 'Name: value', got {text!r}")
    return name.strip(), value.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="superauditor-check", description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="streamable HTTP endpoint; omit to start the server over stdio")
    parser.add_argument("--header", type=_header, action="append", default=[], help="HTTP header, 'Name: value'")
    parser.add_argument("--tool", default="get_session_findings")
    parser.add_argument("--session-key", default=None)
    parser.add_argument("--low", type=int, default=1, help="lower per_kind_limit for the two-pull checks")
    parser.add_argument("--high", type=int, default=200, help="higher per_kind_limit for the two-pull checks")
    parser.add_argument("--require-version", default=None, help="fail unless _meta.superauditor is at least this")
    parser.add_argument("--json", action="store_true", help="print the results as JSON")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- server command and arguments (stdio)")
    args = parser.parse_args(argv)
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.url and not args.command:
        parser.error("give --url, or the server command after --")

    claimed = None
    try:
        results, claimed = asyncio.run(run(args))
    except Exception as exc:  # noqa: BLE001 - every failure is reported as a result, never as a traceback
        results = [checks.Result("call", False, _describe(exc))]

    failed = [r for r in results if r.ok is False]
    if args.json:
        print(json.dumps({"ok": not failed, "claimed_version": claimed, "results": [r.__dict__ for r in results]}, indent=2))
    else:
        for r in results:
            mark = {True: "PASS", False: "FAIL", None: "INFO"}[r.ok]
            print(f"{mark:4}  {r.id:8}  {r.detail}")
        print("\n" + verdict(failed, claimed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
