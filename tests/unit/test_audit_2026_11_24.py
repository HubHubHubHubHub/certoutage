"""Counterexamples M1–M7 from the audit of 24 November 2026."""
from dataclasses import replace
from decimal import Decimal, Inexact, Rounded, localcontext
from fractions import Fraction

import numpy as np
import pytest
from flint import arb

from certoutage import (Model, Numerics, SNRGrid, floor, largest_interferer_bound,
                        required_snr, threshold_difference)
from certoutage import _generate, _runtime
from certoutage._vendor import commun, ppp, thermal_backend


def test_m1_rejects_inexact_grid_under_low_decimal_precision():
    with localcontext() as context:
        context.prec = 3
        with pytest.raises(ValueError, match="exact multiples"):
            SNRGrid(start="1.0001", stop="2.0001", step="0.5")


def test_m1_exact_grid_is_used_with_decimal_rounding_trapped():
    expected = required_snr(Model(convention="C-INR"), 1, "1e-5",
                            SNRGrid("1.0078125", "2.0078125", "0.5"))
    with localcontext() as context:
        context.prec = 3
        context.traps[Inexact] = context.traps[Rounded] = True
        grid = SNRGrid("1.0078125", "2.0078125", "0.5")
        actual = required_snr(Model(convention="C-INR"), 1, "1e-5", grid)
    assert (grid.start, grid.stop, grid.step) == (1 + 1 / 128, 2 + 1 / 128, .5)
    assert actual == expected
    for value in (actual.lower_db, actual.upper_db):
        assert (Fraction(value) - Fraction(grid.start)) % Fraction(grid.step) == 0


@pytest.mark.parametrize("scale,expected", [
    ("0.4" + "9" * 450, "[1.0000, 1.0001]"),
    ("0.5" + "0" * 449 + "1", "[0.9999, 1.0000]"),
])
def test_m2_long_quotients_round_outwards(scale, expected):
    enclosure = replace(floor(Model(convention="C-INR"), 1), lower=.5, upper=.5)
    assert enclosure.format(scale=scale) == expected
    with localcontext() as context:
        context.prec = 3
        context.traps[Inexact] = context.traps[Rounded] = True
        rendered = enclosure.format(scale=scale)
    assert rendered == expected
    lower, upper = map(Fraction, rendered[1:-1].split(", "))
    assert lower <= Fraction(1, 2) / Fraction(scale) <= upper


def test_m2_large_quotient_and_exact_boundary():
    enclosure = replace(floor(Model(convention="C-INR"), 1), lower=.5, upper=.5)
    assert enclosure.format(scale="0.5") == "[1.0000, 1.0000]"
    rendered = enclosure.format(scale="1e-500", places=0)
    lower, upper = map(Fraction, rendered[1:-1].split(", "))
    assert lower == upper == Fraction(10 ** 500, 2)


@pytest.mark.parametrize("lam,power", [("0.1", 12), ("0.01", 12)])
def test_m3_generated_ppp_checks_all_archive_laplace_points(monkeypatch, lam, power):
    original = _generate.transform
    checked = []

    def record(s, intensity, eta):
        if isinstance(s, arb):
            checked.append(s)
        return original(s, intensity, eta)

    monkeypatch.setattr(_generate, "transform", record)
    with _runtime.arithmetic(160):
        _generate.environment_arrays(lam, 4, power, "PPP")
        assert len(checked) == 3
        assert all(value.overlaps(arb(s)) for value, s in zip(checked, ("0.1", "0.5", "1")))


def test_m3_laplace_guard_rejects_inconsistent_inversion(monkeypatch):
    original = _generate.transform

    def inconsistent(s, lam, eta):
        # Keep inversion coefficients intact, corrupt only its independent check.
        return arb(2) if isinstance(s, arb) else original(s, lam, eta)

    monkeypatch.setattr(_generate, "transform", inconsistent)
    with _runtime.arithmetic(160), pytest.raises(ArithmeticError, match="Laplace"):
        _generate.environment_arrays("0.1", 4, 12, "PPP")


@pytest.mark.parametrize("convert", [commun.out, thermal_backend.outward])
def test_m4_nonfinite_balls_raise_arithmetic_error(convert):
    with pytest.raises(ArithmeticError, match="finite"):
        convert(arb("nan"))


@pytest.mark.parametrize("convert", [commun.out, thermal_backend.outward])
def test_m4_inward_transport_is_rejected(monkeypatch, convert):
    original = np.nextafter
    monkeypatch.setattr(np, "nextafter", lambda value, direction: original(value, -direction))
    with pytest.raises(ArithmeticError, match="outward"):
        convert(arb(1))


def test_m4_inconsistent_cdf_envelopes_are_rejected():
    with pytest.raises(ArithmeticError, match="envelopes"):
        ppp.envelopes(np.array([0., .8]), np.array([0., .2]), None, None)


def test_m4_negative_masses_are_rejected(monkeypatch):
    # Inject a conversion fault after the CDF consistency check.
    monkeypatch.setattr(ppp, "arb", lambda value: -arb(value))
    with pytest.raises(ArithmeticError, match="masses"):
        ppp.envelopes(np.array([0., .5]), np.array([0., .5]), None, None)


def test_m4_tighten_rejects_crossed_bounds():
    with pytest.raises(ArithmeticError, match="CDF"):
        thermal_backend.tighten(np.array([.8]), np.array([.2]))


def test_m4_series_and_poisson_preconditions_survive_optimization():
    with pytest.raises(ArithmeticError):
        thermal_backend.gamma_series(arb(-1), arb(1))
    with pytest.raises(ArithmeticError):
        commun.poisson_tail(arb(2), 0)


def test_m5_float32_is_read_by_decimal_string_and_selects_archive():
    model = Model(lam=np.float32(.1))
    assert model.lam == "0.1"
    assert Decimal.from_float(float(np.float32(.1))) != Decimal("0.1")
    result = floor(model, 1)
    assert result.contract.source == "provided-banks"
    assert any(name == "PPP_l0p1_e4.npz" for name, _ in result.contract.banks)
    assert result.as_dict() == floor(Model(lam="0.1"), 1).as_dict()
    assert Model(lam=.1 + .2).lam == "0.30000000000000004"


def test_m6_fresh_error_mentions_both_regenerated_distributions():
    with pytest.raises(ValueError, match="PPP.*Gamma"):
        Numerics(bank_policy="unknown")


def test_m6_stored_certificate_reports_its_actual_precision():
    result = largest_interferer_bound(Model(), 1, numerics=Numerics(precision_bits=512))
    assert result.contract.source == "provided-certificate"
    assert result.contract.precision_bits == result.contract.bank_precision_bits == 160
    assert result.as_dict() == largest_interferer_bound(Model(), 1).as_dict()


def test_m6_dft_endpoint_is_conservative_previous_node():
    with _runtime.arithmetic(160):
        coarse = _generate.environment_arrays("0.01", 4, 12, "PPP")
        dft = _generate.environment_arrays("0.01", 4, 14, "PPP")
    assert dft["xlo"][-1] <= 128 <= dft["xhi"][-1]
    assert .48 < dft["clo"][-1] < .50 < coarse["clo"][-1]
    assert dft["chi"][-1] == coarse["chi"][-1] == 1


@pytest.mark.parametrize("change,match", [
    ({"target": "2e-5"}, "target"),
    ({"user": 2}, "user"),
    ({"model": Model(convention="C-TX", lam=0)}, "convention"),
    ({"model": Model(N=20, convention="C-INR", lam=0)}, "N"),
])
def test_m7_refuses_incomparable_thresholds(change, match):
    arguments = dict(model=Model(convention="C-INR", lam=0), user=1, target="1e-5")
    first = required_snr(**arguments)
    second = required_snr(**(arguments | change))
    assert first.status == second.status == "feasible"
    with pytest.raises(ValueError, match=match):
        threshold_difference(first, second)


def test_m7_equivalent_targets_and_distinct_comparators_remain_comparable():
    model = Model(convention="C-INR")
    exact = required_snr(model, 1, "1e-5")
    other = required_snr(replace(model, lam="0.1000"), 1, Decimal("0.0000100"),
                         gain="eq3", interference="mean")
    difference = threshold_difference(other, exact)
    assert difference.lower == other.lower_db - exact.upper_db
    assert difference.upper == other.upper_db - exact.lower_db
