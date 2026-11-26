"""examples/table_ii.py --json gives back the reference Table II, bit for bit.

The fixture is the T28b output of 24/11/2026 (checked against the Letter source,
lines 455-458), without its only run-dependent field, ``wall_seconds``.
Floats are compared by ``float.hex``, which separates every binary64 value
(including -0.0 from 0.0).
"""
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "table_ii.json"


def _exact(value):
    if isinstance(value, float):
        return ("float", value.hex())
    if isinstance(value, dict):
        return {key: _exact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_exact(item) for item in value]
    return value


def test_table_ii_example_is_bit_identical(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["table_ii.py", "--json"])
    runpy.run_path(str(ROOT / "examples" / "table_ii.py"), run_name="__main__")
    produced = json.loads(capsys.readouterr().out)
    seconds = produced.pop("wall_seconds")
    assert isinstance(seconds, float) and seconds >= 0
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert _exact(produced) == _exact(expected)
