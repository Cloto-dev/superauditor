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
])
def test_each_broken_server_fails_on_its_defect(variant, failed):
    ec, got = check(variant)
    assert ec == 1
    assert got == failed


def test_a_missing_version_fails_only_when_required():
    assert check("no_version") == (0, set())
    assert check("no_version", "--require-version", "1.1") == (1, {"C12"})
