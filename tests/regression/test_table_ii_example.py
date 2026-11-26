"""examples/table_ii.py --json gives back the reference Table II, bit for bit.

The fixture is the T28b output of 24/11/2026 (checked against the Letter source,
lines 455-458), without its only run-dependent field, ``wall_seconds``.
Floats are compared by ``float.hex``, which separates every binary64 value
(including -0.0 from 0.0). The declared link fields are added to the expected
model and contracts in memory; the archived fixture is left unchanged.
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


def _add_default_link_contracts(value):
    """Extend the archived schema only; keep every historical field and float."""
    if isinstance(value, dict):
        if "parameters" in value:
            value["parameters"].extend([["d1", "80/3"], ["d2", "160"], ["g", "1"]])
        for item in value.values():
            _add_default_link_contracts(item)
    elif isinstance(value, list):
        for item in value:
            _add_default_link_contracts(item)


def test_table_ii_example_is_bit_identical(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["table_ii.py", "--json"])
    runpy.run_path(str(ROOT / "examples" / "table_ii.py"), run_name="__main__")
    produced = json.loads(capsys.readouterr().out)
    seconds = produced.pop("wall_seconds")
    assert isinstance(seconds, float) and seconds >= 0
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expected["model"].update(d1="80/3", d2="160", g="1")
    _add_default_link_contracts(expected)
    assert _exact(produced) == _exact(expected)


def test_table_ii_text_is_computed_and_ignores_the_decimal_context(capsys, monkeypatch):
    """The text output prints the computed threshold, rounded outward, even under a hostile decimal context."""
    import decimal

    monkeypatch.setattr(sys, "argv", ["table_ii.py"])
    with decimal.localcontext() as context:
        context.prec = 1
        for trap in (decimal.Inexact, decimal.Rounded, decimal.InvalidOperation):
            context.traps[trap] = True
        runpy.run_path(str(ROOT / "examples" / "table_ii.py"), run_name="__main__")
    text = capsys.readouterr().out
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    gamma = expected["rows"][1]["result"]["decision"]
    assert (gamma["lower_db"], gamma["upper_db"]) == (4.5, 4.75)
    assert "Exact gain + Gamma: required SNR (threshold) [4.50, 4.75] dB." in text
    assert f"E F_W(d_i J_max): {expected['rows'][5]['display']}; inconclusive" in text
