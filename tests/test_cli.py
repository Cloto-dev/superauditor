"""The checker against a live stdio server: it passes the conforming one and fails each broken one on its defect."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER = [sys.executable, str(ROOT / "tests" / "sample_server.py")]


def check(variant, *extra):
    env = {**os.environ, "SA_VARIANT": variant}
    run = subprocess.run([sys.executable, "-m", "superauditor_check.cli", "--json", *extra, "--", *SERVER],
                         capture_output=True, text=True, env=env, timeout=120)
    report = json.loads(run.stdout)
    return run.returncode, {r["id"] for r in report["results"] if r["ok"] is False}


def test_a_conforming_server_passes():
    assert check("conforming") == (0, set())


@pytest.mark.parametrize("variant,failed", [
    ("silent_truncation", {"C2"}),
    ("inferred_cap", {"C2"}),
    ("keeps_last", {"order"}),
    ("true_total", {"C3"}),
    ("instance_severity", {"C4"}),
    ("summary_always_off", {"default", "summary"}),
    ("raises", {"call"}),
    ("applies_zero", {"C14"}),
])
def test_each_broken_server_fails_on_its_defect(variant, failed):
    ec, got = check(variant)
    assert ec == 1
    assert got == failed


def test_a_missing_version_fails_only_when_required():
    assert check("no_version") == (0, set())
    assert check("no_version", "--require-version", "1.1") == (1, {"C12"})


def test_a_server_that_replaces_zero_with_the_default_passes():
    assert check("defaults_on_zero") == (0, set())


def verdict(variant, *extra):
    env = {**os.environ, "SA_VARIANT": variant}
    run = subprocess.run([sys.executable, "-m", "superauditor_check.cli", *extra, "--", *SERVER],
                         capture_output=True, text=True, env=env, timeout=120)
    return run.stdout.strip().splitlines()[-1]


def test_the_last_line_names_the_version_a_pass_is_about():
    assert "SuperAuditor 1.1, the version the server claims" in verdict("conforming")
    last = verdict("no_version")
    assert "SuperAuditor v1 only" in last and "--require-version 1.1" in last
