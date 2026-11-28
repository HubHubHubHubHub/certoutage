"""examples/free_parameters.py runs offline and gives consistent certified answers."""
import json
import math
from pathlib import Path
import runpy
import socket
import sys

import pytest

from certoutage import clear_cache

ROOT = Path(__file__).resolve().parents[2]


def _refuse_network(*args, **kwargs):
    raise AssertionError("The example attempted network access")


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv("CERTOUTAGE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(socket, "socket", _refuse_network)
    monkeypatch.setattr(socket, "create_connection", _refuse_network)
    clear_cache()
    yield
    clear_cache()


def test_free_parameter_example(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["free_parameters.py", "--json"])
    runpy.run_path(str(ROOT / "examples" / "free_parameters.py"), run_name="__main__")
    produced = json.loads(capsys.readouterr().out)
    rows = {(r["convention"], r["user"]): r for r in produced["rows"]}
    assert len(rows) == 4
    # c1 = max(1.5/0.25, 2/(0.75 - 2*0.25)) = 8 = c2; d = c / ell.
    assert all((r["d1"], r["d2"]) == ("80", "400") for r in rows.values())
    for user in (1, 2):
        inr, tx = rows["C-INR", user], rows["C-TX", user]
        assert inr["floor"] == [0.0, 0.0] and inr["status"] == "feasible"
        assert tx["status"] == "excluded" and tx["floor"][0] > float(produced["target"])
        assert all(len(r["domain"]) == 1 and "inside" in r["domain"][0] for r in (inr, tx))
    # C-INR scaling identity (PROOFS.md, Proposition 1.7): P_2(5 rho) = P_1(rho)
    # since d2 = 5 d1, so the exact thresholds differ by 10 log10(5) dB. The two
    # certified brackets must be compatible with this difference.
    a, b = rows["C-INR", 1]["threshold_db"], rows["C-INR", 2]["threshold_db"]
    assert b[0] - a[1] <= 10 * math.log10(5) <= b[1] - a[0]


def test_new_size_plan(capsys, monkeypatch):
    from certoutage import _banks, _generate_gain
    monkeypatch.setattr(_generate_gain, "gain_arrays", _refuse_network)
    monkeypatch.setattr(sys, "argv", ["new_size.py", "--plan", "--json"])
    runpy.run_path(str(ROOT / "examples" / "new_size.py"), run_name="__main__")
    result = json.loads(capsys.readouterr().out)
    assert result["plan_only"] and result["prepared"] == []
    assert result["estimated_seconds"] == [75, 75]
    assert [r["logical"] for r in result["plan"]] == ["m2_N21.npz", "SIG_m2_N21.npz"]
    assert all(r["origin"] == "missing" for r in result["plan"])
    assert "one CPU core" in result["expected_cost"]
    assert not _banks.cache_dir().exists()
