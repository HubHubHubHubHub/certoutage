"""Exact link inputs and conservative transport, using only embedded banks."""
from dataclasses import replace
from decimal import Decimal, localcontext, Inexact, Rounded, InvalidOperation
from fractions import Fraction
import math
import socket

from flint import arb
import numpy as np
import pytest

from certoutage import (Model, Numerics, Contract, SNRDecision, clear_cache, floor,
                       outage_enclosure, largest_interferer_bound, required_snr,
                       threshold_difference, compare_approximations)
from certoutage import _runtime as rt
from certoutage._vendor.commun import moment


def _refuse_network(*args, **kwargs):
    raise AssertionError("Link tests attempted network access")


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv("CERTOUTAGE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(socket, "socket", _refuse_network)
    monkeypatch.setattr(socket, "create_connection", _refuse_network)
    clear_cache()
    yield
    clear_cache()


def _hex(result):
    return result.lower.hex(), result.upper.hex()


def _overlap(left, right):
    assert max(left.lower, right.lower) <= min(left.upper, right.upper)


def test_defaults_are_the_letter():
    assert Model() == Model(d1="80/3", d2=160, g=1) == Model.from_link()
    assert Model(d1=Fraction(80, 3)) == Model()
    assert (Model().d1, Model().d2, Model().g) == ("80/3", "160", "1")


@pytest.mark.parametrize("settings,user,kind,db", [
    ({"convention": "C-INR"}, 1, "PPP", 0),
    ({"convention": "C-INR"}, 2, "mean", 10),
    ({}, 1, "Gamma", 5), ({}, 2, "PPP", 20),
    ({"N": 8, "lam": 0}, 1, "none", 12),
])
def test_explicit_defaults_preserve_hex(settings, user, kind, db):
    implicit = Model(**settings)
    explicit = Model(d1=Fraction(80, 3), d2=Decimal("160.00"), g="1/1", **settings)
    assert _hex(outage_enclosure(implicit, user, db, interference=kind)) == _hex(
        outage_enclosure(explicit, user, db, interference=kind))
    assert _hex(floor(implicit, user, interference=kind)) == _hex(
        floor(explicit, user, interference=kind))


@pytest.mark.parametrize("value", ["26.5", 26.5, Decimal("26.500"), Fraction(53, 2), "106/4"])
def test_equivalent_inputs_are_canonical(value):
    assert Model(d1=value, d2=value, g=value) == Model(d1="53/2", d2="53/2", g="53/2")
    assert Model(d1=value).d1 == "53/2"


@pytest.mark.parametrize("field", ["d1", "d2", "g"])
@pytest.mark.parametrize("value", [True, False, "nan", math.nan, Decimal("sNaN"),
                                  -1, "-inf", -math.inf, "1e-13", "1e13", "80/3/2",
                                  "1/0", Decimal("Infinity"), "Infinity", "+inf", None])
def test_invalid_coefficients_raise_value_error(field, value):
    with pytest.raises(ValueError, match=field):
        Model(**{field: value})


def test_coefficient_domain_endpoints_and_infinity():
    for field in ("d1", "d2"):
        with pytest.raises(ValueError, match=field):
            Model(**{field: 0})
        for infinity in ("inf", math.inf):
            assert getattr(Model(**{field: infinity}), field) == "inf"
    for infinity in ("inf", math.inf):
        with pytest.raises(ValueError, match="g"):
            Model(g=infinity)
    assert Model(g=0).g == "0"
    for value, canonical in [("1e-12", "1/1000000000000"), ("1e12", "1000000000000")]:
        model = Model(d1=value, d2=value, g=value)
        assert model.d1 == model.d2 == model.g == canonical


def test_from_link_two_thresholds_and_exact_context():
    with localcontext() as context:
        context.prec = 1
        for trap in (Inexact, Rounded, InvalidOperation):
            context.traps[trap] = True
        # theta1/p1 wins, then theta2/(p2-theta2*p1) wins.
        a = Model.from_link(p1="1/4", p2="3/4", theta1=2, theta2=1, ell1=1, ell2=1)
        b = Model.from_link(p1="1/4", p2="3/4", theta1="1/4", theta2=2, ell1=1, ell2=1)
        assert (a.d1, a.d2) == ("8", "2")
        assert (b.d1, b.d2) == ("8", "8")
        assert Model.from_link(theta1=2) == Model.from_link(theta1=2, theta2=2)
        assert Model.from_link(N=8, g="1/4").g == "1/4"


@pytest.mark.parametrize("field", ["p1", "p2", "theta1", "theta2", "ell1", "ell2"])
def test_from_link_rejects_nonpositive_or_nonfinite_inputs(field):
    for value in (0, -1, True, "nan", "inf", math.inf, "1/0"):
        with pytest.raises(ValueError, match=field):
            Model.from_link(**{field: value})


def test_from_link_rejects_overrides_and_names_out_of_domain_coefficient():
    for field in ("d1", "d2"):
        with pytest.raises(TypeError, match="d1 and d2"):
            Model.from_link(**{field: 1})
    with pytest.raises(TypeError):
        Model.from_link("0.3")
    with pytest.raises(ValueError, match="d1.*c1/ell1"):
        Model.from_link(ell1="1e-20")
    with pytest.raises(ValueError, match="d2.*c2/ell2"):
        Model.from_link(ell2="1e20")


@pytest.mark.parametrize("p2", ["0.6", "0.5"])
def test_infeasible_allocation_precedes_division(p2):
    model = Model.from_link(p1="0.3", p2=p2, theta2=2)
    assert model.d1 == model.d2 == "inf"


@pytest.mark.parametrize("convention", ["C-TX", "C-INR"])
@pytest.mark.parametrize("user", [1, 2])
@pytest.mark.parametrize("kind", ["PPP", "Gamma", "mean", "none"])
def test_infeasible_is_analytic_one(convention, user, kind):
    model = Model.from_link(p1=1, p2=1, convention=convention)
    for result in (outage_enclosure(model, user, 20, interference=kind),
                   floor(model, user, interference=kind), largest_interferer_bound(model, user)):
        assert _hex(result) == (1.0.hex(), 1.0.hex())
        assert result.contract.source == "analytic"
        assert "infeasible power allocation: outage is 1 at every SNR" in result.contract.notes
        assert not result.contract.banks
    assert required_snr(model, user, "0.1", interference=kind).status == "excluded"
    assert required_snr(model, user, "0.1", gain="chernoff", interference=kind).status == "inconclusive"


def test_infeasible_precedes_direct_zero_gain_and_inr_limit():
    model = Model(N=8, lam=0, d1="inf", d2="inf", g=0, convention="C-INR")
    for user in (1, 2):
        assert outage_enclosure(model, user, 20).lower == 1
        assert floor(model, user).lower == 1
        assert largest_interferer_bound(model, user).lower == 1
    # Only the selected link is infeasible.
    assert floor(Model(d1="inf", convention="C-INR"), 2).upper == 0


@pytest.mark.parametrize("kind", ["PPP", "Gamma", "mean", "none"])
def test_inr_scaling_overlaps_with_nondyadic_ratio(kind):
    model = Model(convention="C-INR")
    _overlap(outage_enclosure(model, 1, 20, interference=kind),
             outage_enclosure(replace(model, d1="8/3"), 1, 10, interference=kind))


@pytest.mark.parametrize("settings,kind", [({}, "PPP"), ({}, "Gamma"), ({}, "mean"),
                                        ({"N": 8, "lam": 0}, "none")])
def test_user_selects_only_d_in_bank_and_direct_routes(settings, kind):
    model = Model(**settings)
    for convention in ("C-TX", "C-INR"):
        model = replace(model, convention=convention)
        assert _hex(outage_enclosure(model, 2, 10, interference=kind)) == _hex(
            outage_enclosure(replace(model, d1=160), 1, 10, interference=kind))
        assert _hex(outage_enclosure(model, 1, 10, interference=kind)) == _hex(
            outage_enclosure(replace(model, d2="80/3"), 2, 10, interference=kind))


def test_largest_interferer_user_equivalence_and_certificate_guard():
    assert _hex(largest_interferer_bound(Model(), 2)) == _hex(
        largest_interferer_bound(Model(d1=160), 1))
    default = largest_interferer_bound(Model(), 1)
    assert default.contract.source == "provided-certificate"
    for model in (Model(d1="800/3"), Model(g=10)):
        scaled = largest_interferer_bound(model, 1)
        assert scaled.contract.source == "mixed"
        assert scaled.lower > default.upper


@pytest.mark.parametrize("kind", ["PPP", "Gamma", "mean"])
def test_tx_gain_folding_overlaps(kind):
    _overlap(outage_enclosure(Model(g=10), 1, 0, interference=kind),
             outage_enclosure(Model(d1="800/3"), 1, 10, interference=kind))


def test_tx_link_scaling_alone_is_not_an_identity():
    larger = outage_enclosure(Model(), 1, 20, interference="mean")
    smaller = outage_enclosure(Model(d1="8/3"), 1, 10, interference="mean")
    assert smaller.upper < larger.lower


def test_link_and_gain_monotonicity():
    assert outage_enclosure(Model(d1="8/3"), 1, 10).upper < outage_enclosure(Model(d1="800/3"), 1, 10).lower
    assert outage_enclosure(Model(g="1/10"), 1, 10).upper < outage_enclosure(Model(g=10), 1, 10).lower
    ds = ("8/3", "80/3", "1000/7", "800/3")
    gs = ("0", "1/10", "1", "10")
    for convention in ("C-TX", "C-INR"):
        rows = [[outage_enclosure(Model(d1=d, g=g, convention=convention), 1, 10)
                 for g in gs] for d in ds]
        for row in rows:
            assert all(b.upper >= a.lower for a, b in zip(row, row[1:]))
        for column in zip(*rows):
            assert all(b.upper >= a.lower for a, b in zip(column, column[1:]))


@pytest.mark.parametrize("convention", ["C-TX", "C-INR"])
@pytest.mark.parametrize("N", [24, 8])
def test_zero_gain_is_exactly_no_interference(convention, N):
    model = Model(N=N, convention=convention, g=0, d1=40)
    for user in (1, 2):
        expected = outage_enclosure(model, user, 10, interference="none")
        for kind in ("PPP", "Gamma", "mean", "none"):
            result = outage_enclosure(model, user, 10, interference=kind)
            assert _hex(result) == _hex(expected)
            assert f"interference={kind}" in result.contract.quantity
            assert "g=0: no interference contribution" in result.contract.notes
            limit = floor(model, user, interference=kind)
            assert _hex(limit) == (0.0.hex(), 0.0.hex())
            assert limit.contract.source == "analytic"
        bound = largest_interferer_bound(model, user)
        assert _hex(bound) == (0.0.hex(), 0.0.hex())
        assert bound.contract.source == "analytic"


def test_signal_lookup_extends_with_zero_and_one():
    with rt.arithmetic(160):
        signal = rt.signal(24, 1, False, 160)
        low, high = signal.lookup(np.array([-2, -1, signal.size, signal.size + 2]),
                                  np.array([-2, -1, signal.size, signal.size + 2]), "exact")
        lv, hv = signal.values["exact"]
        assert low[0].is_zero() and low[1].is_zero()
        assert high[0] == high[1] == hv[0]
        assert low[2] == low[3] == lv[-1]
        assert high[2] == high[3] == arb(1)
    assert outage_enclosure(Model(d1="1e12"), 1, 0, interference="none").upper == 1
    assert outage_enclosure(Model(d1="1e-12"), 1, 20, interference="none").lower == 0


@pytest.mark.parametrize("factor", [Fraction(1), Fraction(6), Fraction(3, 2), Fraction(1, 10),
                                   Fraction(75, 14), Fraction(1, 10**12), Fraction(10**12)])
def test_scale_outward_against_exact_fractions(factor):
    values = np.array([0., np.nextafter(0., 1.), np.finfo(float).tiny, 0.1, 1., 2.5e6])
    lo, hi = rt.scale_outward(values, values, factor)
    assert np.all(lo >= 0)
    for x, lower, upper in zip(values, lo, hi):
        exact = Fraction(float(x)) * factor
        assert Fraction(float(lower)) <= exact <= Fraction(float(upper))
    if factor == 1:
        assert lo is values and hi is values
    elif factor in (6, Fraction(3, 2)):
        assert [x.hex() for x in lo] == [x.hex() for x in np.maximum(0., np.nextafter(values * float(factor), -np.inf))]
        assert [x.hex() for x in hi] == [x.hex() for x in np.nextafter(values * float(factor), np.inf)]


def test_largest_grid_retains_only_exact_products():
    grid = np.arange(128 * 64 + 1, dtype=float) / 64
    for factor in (Fraction(1), Fraction(6), Fraction(1, 10), Fraction(75, 14)):
        low, high = rt.scale_grid_outward(grid, factor)
        for x, lo, hi in zip(grid, low, high):
            exact = Fraction(float(x)) * factor
            assert Fraction(float(lo)) <= exact <= Fraction(float(hi))
        if factor in (1, 6):
            assert [x.hex() for x in low] == [x.hex() for x in grid * float(factor)]
            assert [x.hex() for x in high] == [x.hex() for x in grid * float(factor)]


@pytest.mark.parametrize("N,m", [(8, 1), (64, 1), (8, 2)])
@pytest.mark.parametrize("d", [40, 500])
def test_direct_arbitrary_link_overlaps_bank(N, m, d):
    model = Model(N=N, m=m, d1=d)
    direct = outage_enclosure(model, 1, 10, interference="none")
    with rt.arithmetic(160):
        signal = rt.signal(N, m, False, 160)
        env = rt.environment(model, "none", Numerics())
        bank = env.point(signal, arb(10 * 128), model.convention, Fraction(d), Fraction(1))
    assert max(direct.lower, bank["lower"]) <= min(direct.upper, bank["upper"])


def test_thermal_cache_is_independent_of_link():
    ds = ("40", "80/3", "40", "500", "40", "160")
    warm = [_hex(outage_enclosure(Model(N=8, d1=d), 1, 10, interference="none")) for d in ds]
    cold = []
    for d in ds:
        clear_cache()
        cold.append(_hex(outage_enclosure(Model(N=8, d1=d), 1, 10, interference="none")))
    assert warm == cold


def test_contract_assumptions_and_parameter_order():
    original = (
        "independent amplitudes, thermal term and marked PPP",
        "W=(sum sqrt(E F))²(10+Z)²/101, Z standard normal",
        "powers E,F Exp(1) or Gamma(m,rate=m), covered integer m",
        "planar PPP outside R0=1; Exp(1) power marks",
        "d1=80/3, d2=160; perfect CSI and phase alignment",
        "numerical certificate of the model; no physical or latency guarantee",
    )
    assert Contract.assumptions == original
    for model in (Model(), Model(d1=40, d2="1/4", g="0.25"), Model(d1="inf", g=0)):
        results = (outage_enclosure(model, 1, 10), floor(model, 1), largest_interferer_bound(model, 1))
        for result in results:
            assert result.contract.parameters[-3:] == (("d1", model.d1), ("d2", model.d2), ("g", model.g))
            assumptions = result.contract.assumptions
            if model == Model():
                assert assumptions == original
            else:
                assert f"d1={model.d1}, d2={model.d2}" in assumptions[4]
                assert f"interference gain g={model.g}" in assumptions[3]
                assert ("infeasible power allocation" in assumptions[4]) == (model.d1 == "inf")


def test_comparison_rows_record_actual_links_and_limits():
    for model, label in ((Model(d1=40, g=0), "E F_W(d_i g J_max)"),
                         (Model(d1="inf", g="1/4", convention="C-INR"),
                          "C-INR largest-interferer floor (limit = 1)")):
        rows = compare_approximations(model, 1, "0.1")
        assert rows[-1].label == label
        for row in rows:
            for contract in (row.floor.contract, row.decision.contract):
                assert contract.parameters[-3:] == (("d1", model.d1), ("d2", model.d2), ("g", model.g))
                assert f"interference gain g={model.g}" in contract.assumptions[3]
                assert f"d1={model.d1}, d2={model.d2}" in contract.assumptions[4]


def _decision(**fields):
    base = floor(Model(convention="C-INR", **fields), 1)
    return SNRDecision("feasible", 0., 1., base, "test finite bracket", 0, "test", target="0.1")


@pytest.mark.parametrize("field,value", [("d1", "40"), ("d2", "40"), ("g", "2")])
def test_threshold_difference_rejects_different_links(field, value):
    with pytest.raises(ValueError, match=f"same parameter {field}"):
        threshold_difference(_decision(), _decision(**{field: value}))


def test_threshold_difference_compares_rationals_and_missing_keys():
    a = _decision(g="1/4")
    parameters = dict(a.contract.parameters)
    parameters.update(d1=Fraction(80, 3), d2=160, g="0.25")
    b = replace(a, evaluation_contract=replace(a.contract, parameters=tuple(parameters.items())))
    assert threshold_difference(a, b).lower == -1
    for field in ("d1", "d2", "g"):
        missing = tuple((k, v) for k, v in a.contract.parameters if k != field)
        b = replace(a, evaluation_contract=replace(a.contract, parameters=missing))
        for left, right in ((a, b), (b, a)):
            with pytest.raises(ValueError, match=f"Parameter {field} missing"):
                threshold_difference(left, right)
    infinite = _decision(d1="inf")
    assert threshold_difference(infinite, infinite).upper == 1
    with pytest.raises(ValueError, match="d1"):
        threshold_difference(_decision(), infinite)


def test_second_cumulant_and_gamma_matching():
    with rt.arithmetic(160):
        for eta in (3, 4):
            mean = moment("0.1", eta, 1, 1)
            variance = moment("0.1", eta, 1, 2)
            expected = 2 * arb.pi() * arb("0.1") * 2 / (2 * eta - 2)
            assert variance.overlaps(expected)
            shape, scale = mean**2 / variance, variance / mean
            assert (shape * scale**2).overlaps(variance)
            # Check the actual generated Gamma CDF against the distribution
            # with mean kappa_1 and variance kappa_2, near its central mass.
            data = rt.environment_arrays("0.1", eta, 12, "GAMMA")
            for x in (float(mean) / 2, float(mean), float(mean) * 2):
                i = int(np.searchsorted(data["xlo"], x))
                point = arb(float(data["xlo"][i])).union(arb(float(data["xhi"][i])))
                expected_cdf = (point / scale).gamma_lower(shape, regularized=True)
                actual_cdf = arb(float(data["clo"][i])).union(arb(float(data["chi"][i])))
                assert expected_cdf.overlaps(actual_cdf)
