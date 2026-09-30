"""The fixtures are self-consistent, and the reference to copy passes them."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))

import reference_delivery as ref  # noqa: E402

FIXTURES = sorted((ROOT / "conformance" / "v1").glob("*.json"))
CASES = [(path.name, case) for path in FIXTURES for case in json.loads(path.read_text())["cases"]]


def test_the_fixture_validator_passes():
    run = subprocess.run([sys.executable, str(ROOT / "conformance" / "v1" / "validate.py")], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.parametrize("name,case", CASES, ids=[f"{n}::{c['name']}" for n, c in CASES])
def test_the_reference_delivery_passes_every_case(name, case):
    got = ref.deliver(case["detector_output"], case["per_kind_limit"], case["severity_map"])
    for key, expected in case["expect"].items():
        assert got[key] == expected, (key, got[key], expected)
