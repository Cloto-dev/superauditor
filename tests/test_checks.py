"""Each check fails on the defect it names and passes the reference output."""

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))

import reference_delivery as ref  # noqa: E402
from superauditor_check import checks  # noqa: E402

SEVERITY = {"stale": "info", "contradiction": "warn", "orphan": "info"}
# 3 stale, 1 contradiction, 2 orphan: at limit 1, stale and orphan are capped and contradiction is exactly at it.
DETECTED = [
    {"kind": "stale", "id": 1}, {"kind": "contradiction", "id": 2}, {"kind": "stale", "id": 3},
    {"kind": "orphan", "id": 4}, {"kind": "stale", "id": 5}, {"kind": "orphan", "id": 6},
]


def pull(limit, include_summary=True):
    def probes(n, _key):
        seen, out = {}, []
        for f in DETECTED:
            seen[f["kind"]] = seen.get(f["kind"], 0) + 1
            if seen[f["kind"]] <= n:
                out.append(dict(f))
        return out

    return ref.get_session_findings(probes, SEVERITY, "0.0.1", None, limit, include_summary)


def ok(result):
    return result.ok is True


def test_the_reference_output_passes_every_check():
    low, high = pull(1), pull(200, include_summary=False)
    schema = checks.load_schema()
    results = [
        checks.check_shape(low, schema), checks.check_shape(high, schema),
        checks.check_echo(low, 1), checks.check_c1(low, 1), checks.check_c3(low),
        checks.check_capped_consistent(low, 1), checks.check_c4([low, high]),
        checks.check_c2(low, 1, high, 200), checks.check_prefix(low, high),
        checks.check_summary(low, high), checks.check_version(low, "1.1"),
    ]
    assert all(ok(r) for r in results), [r for r in results if not ok(r)]


def test_shape_names_a_missing_required_key():
    bad = pull(1)
    del bad["capped_kinds"]
    result = checks.check_shape(bad, checks.load_schema())
    assert result.ok is False and "capped_kinds" in result.detail


def test_shape_refuses_a_severity_outside_the_vocabulary():
    bad = pull(1)
    bad["findings"][0]["severity"] = "error"
    assert checks.check_shape(bad, checks.load_schema()).ok is False


def test_echo_catches_a_limit_the_server_did_not_apply():
    assert checks.check_echo(pull(1), 2).ok is False


def test_c1_catches_a_kind_over_the_limit():
    assert checks.check_c1(pull(2), 1).ok is False
    assert checks.check_c1(pull(2), 2).ok is True


@pytest.mark.parametrize("field,value", [("total", 6), ("counts_by_kind", {"stale": 1}), ("counts_by_severity", {"info": 99})])
def test_c3_catches_each_count_that_disagrees_with_findings(field, value):
    bad = pull(1)
    bad[field] = value
    assert checks.check_c3(bad).ok is False


def test_c4_catches_one_kind_with_two_severities_across_pulls():
    low, high = pull(1), pull(200)
    high = copy.deepcopy(high)
    high["findings"][2]["severity"] = "warn"  # a stale row, while stale is info in the other pull
    assert checks.check_c4([low]).ok is True
    assert checks.check_c4([low, high]).ok is False


def test_c2_catches_truncation_that_goes_unreported():
    low, high = pull(1), pull(200)
    low["capped_kinds"] = []
    result = checks.check_c2(low, 1, high, 200)
    assert result.ok is False and "stale" in result.detail


def test_c2_catches_a_cap_inferred_from_count_equal_to_limit():
    # contradiction has exactly one finding: at limit 1 it is not capped.
    low, high = pull(1), pull(200)
    low["capped_kinds"] = low["capped_kinds"] + ["contradiction"]
    result = checks.check_c2(low, 1, high, 200)
    assert result.ok is False and "contradiction" in result.detail


def test_c2_catches_rows_dropped_below_the_limit():
    # contradiction has one finding and the limit is 1: the lower pull must return it. Counts are kept
    # consistent, so only the comparison between the pulls can see the loss.
    low, high = pull(1), pull(200)
    low["findings"] = [f for f in low["findings"] if f["kind"] != "contradiction"]
    low["total"] = len(low["findings"])
    low["counts_by_kind"].pop("contradiction")
    low["counts_by_severity"].pop("warn")
    assert checks.check_c3(low).ok is True
    result = checks.check_c2(low, 1, high, 200)
    assert result.ok is False and "contradiction" in result.detail


def test_c2_trusts_a_cap_the_higher_pull_also_reports():
    # At the higher limit the kind is capped again: more exist, so the lower cap is right.
    low, high = pull(1), pull(2)
    assert checks.check_c2(low, 1, high, 2).ok is True


def test_c2_self_catches_a_capped_kind_that_returned_less_than_the_limit():
    bad = pull(2)
    bad["capped_kinds"] = bad["capped_kinds"] + ["contradiction"]
    assert checks.check_capped_consistent(bad, 2).ok is False


def test_order_catches_a_server_that_keeps_the_last_rows():
    low, high = pull(1), pull(200)
    low["findings"] = [f for f in high["findings"] if f["id"] in (5, 2, 6)]  # the last row of each kind
    assert checks.check_prefix(low, high).ok is False


def test_summary_catches_both_directions():
    low, high = pull(1), pull(200, include_summary=False)
    assert checks.check_summary(low, high).ok is True
    assert checks.check_summary({**low, "summary": None}, high).ok is False
    assert checks.check_summary(low, {**high, "summary": "x"}).ok is False


def test_version_is_informational_unless_required():
    bare = pull(1)
    del bare["_meta"]["superauditor"]
    assert checks.check_version(bare, None).ok is None
    assert checks.check_version(bare, "1.1").ok is False
    assert checks.check_version(pull(1), "1.1").ok is True
    assert checks.check_version(pull(1), "1.2").ok is False


def test_the_reference_refuses_a_probe_that_emits_its_own_severity():
    with pytest.raises(ValueError):
        ref.deliver([{"kind": "stale", "severity": "warn"}], 5, SEVERITY)


@pytest.mark.parametrize("outcome,response,passes", [
    ("tool_error", None, True),
    ("response", {"ok": False, "error": "per_kind_limit must be at least 1"}, True),
    ("response", {"findings": [], "per_kind_limit": 5}, True),
    ("response", {"findings": [], "per_kind_limit": 0}, False),
    ("response", {"findings": []}, False),
])
def test_c14_accepts_refusal_or_an_echoed_default_and_nothing_else(outcome, response, passes):
    assert checks.check_zero_limit(outcome, response).ok is passes


@pytest.mark.parametrize("bad", [0, -1, True, "5", 2.5])
def test_the_reference_refuses_a_limit_it_must_not_apply(bad):
    with pytest.raises(ValueError):
        ref.get_session_findings(lambda n, k: [], SEVERITY, "0.0.1", None, bad)
