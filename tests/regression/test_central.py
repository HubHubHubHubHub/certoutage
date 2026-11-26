"""Les quatre affirmations centrales passent exclusivement par l'API publique."""
import csv
import json
from pathlib import Path

import pytest

from certoutage import (Model, floor, outage_enclosure, required_snr,
                        compare_approximations, largest_interferer_bound,
                        threshold_difference)

FIXTURES = Path(__file__).parent / "fixtures"
METHODS = {"exact_PPP": ("exact", "PPP"), "exact_mean": ("exact", "mean"),
           "gauss_mean": ("eq3", "mean"), "gauss_gamma": ("eq3", "Gamma"),
           "chernoff_PPP": ("chernoff", "PPP")}


@pytest.mark.parametrize("name", ["D1", "D2", "D3"])
def test_all_raw_points_and_decisions(name):
    reference = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    model = Model(N=reference["N"], convention=reference["convention"])
    decisions = {}
    for key, old in reference["brackets"].items():
        gain, interference = METHODS[key]
        new = required_snr(model, 1, "1e-5", gain=gain, interference=interference)
        expected_status = {"FINI": "feasible", "INATTEIGNABLE": "excluded",
                           "MAJORANT_NE_CERTIFIE_AUCUN_SNR": "inconclusive"}[old["status"]]
        assert new.status == expected_status
        assert (new.lower_db, new.upper_db, new.undecided_points) == (old["lower_db"], old["upper_db"], old["undecided"])
        assert new.floor.as_dict() == old["floor"]
        decisions[key] = new
    for row in csv.DictReader((FIXTURES / f"{name}_POINTS.csv").open(encoding="utf-8", newline="")):
        gain, interference = METHODS[row["method"]]
        kw = dict(gain=gain, interference=interference)
        actual = (floor(model, 1, **kw) if row["snr_db"] == "inf" else
                  outage_enclosure(model, 1, row["snr_db"], **kw))
        assert actual.as_dict() == {k: float(row[k]) for k in ("lower", "upper")}
    for key, left, right in [("interference", "exact_mean", "exact_PPP"),
                              ("gain", "gauss_mean", "exact_mean"),
                              ("total", "gauss_mean", "exact_PPP"),
                              ("chernoff", "chernoff_PPP", "exact_PPP")]:
        if reference["errors"][key]["status"] == "FINI":
            result = threshold_difference(decisions[left], decisions[right])
            assert (result.lower, result.upper) == tuple(reference["errors"][key][k] for k in ("lower", "upper"))


@pytest.mark.parametrize("N,display", [(20, "[0.7500, 0.9375]"), (24, "[-0.7500, -0.5625]")])
def test_signs_display(N, display):
    model = Model(N=N, convention="C-INR")
    exact = required_snr(model, 1, "1e-5")
    approx = required_snr(model, 1, "1e-5", gain="eq3", interference="mean")
    assert threshold_difference(approx, exact).format() == display


def test_floor_and_decisive_displays():
    assert floor(Model(N=20), 1).format(scale="1e-4") == "[1.5887, 1.6155]"
    assert floor(Model(N=24), 1).format(scale="1e-5") == "[1.7136, 1.7478]"
    assert required_snr(Model(N=20), 1, "1e-5", interference="mean").upper_db == 0.25
    for N in [20, 24]:
        old = json.loads((FIXTURES / f"MINORANTS_N{N}.json").read_text(encoding="utf-8"))
        row = next(r for r in old["results"] if r["kind"] == "largest_jump" and r["lam"] == "0.1")
        bound = largest_interferer_bound(Model(N=N), 1)
        assert bound.as_dict() == {"lower": row["integrated_lower"], "upper": row["integrated_upper"]}
        assert bound.contract.source == "provided-certificate"


def test_gamma_all_raw_floors_and_thresholds():
    old = json.loads((FIXTURES / "gamma.json").read_text(encoding="utf-8"))
    for row in old["rows"]:
        gain = "exact" if row["gain"] == "exact" else "eq3"
        kind = {"GAMMA": "Gamma"}.get(row["interference"], row["interference"])
        model = Model(N=row["N"])
        assert floor(model, 1, gain=gain, interference=kind).as_dict() == row["ctx_floor"]
        for convention in ["C-INR", "C-TX"]:
            result = required_snr(Model(N=row["N"], convention=convention), 1, "1e-5", gain=gain, interference=kind)
            expected = row[convention + "_threshold"]
            assert (result.lower_db, result.upper_db) == (expected["lower_db"], expected["upper_db"])
            assert result.status == ("feasible" if expected["status"] == "FINI" else "excluded")


def test_table_ii_displays_and_diagnostics():
    rows = compare_approximations(Model(), 1, "1e-5")
    assert rows[0].floor.format(scale="1e-5") == "[1.7136, 1.7478]"
    assert rows[1].floor.format(scale="1e-5") == "[0.5629, 0.5757]"
    assert rows[2].floor.format(scale="1e-5", places=3) == "[1.639, 1.668]"
    assert rows[-1].floor.upper < 9.784e-6
    assert [r.decision.status for r in rows] == ["excluded", "feasible", "excluded", "feasible", "feasible", "inconclusive"]
    assert rows[1].diagnostic == "falsely feasible"
    assert rows[2].diagnostic == "masked"
