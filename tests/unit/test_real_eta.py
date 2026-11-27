"""Real eta: independent identities, certified remainders and offline API checks."""
from dataclasses import replace
from decimal import Decimal, localcontext, Inexact, Rounded
from fractions import Fraction
import json
import math
import socket
from time import perf_counter

from flint import acb, arb, ctx
import numpy as np
import pytest

from certoutage import (Model, Numerics, SNRGrid, Contract, Enclosure, SNRDecision,
                       clear_cache, outage_enclosure, floor, largest_interferer_bound,
                       threshold_difference)
from certoutage import _runtime as rt, _generate as gen, _transform as tf
from certoutage._vendor import ppp
from certoutage.models import _bounded, _fraction


def _refuse_network(*args, **kwargs):
    raise AssertionError("Real-eta tests attempted network access")


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv("CERTOUTAGE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(socket, "socket", _refuse_network)
    monkeypatch.setattr(socket, "create_connection", _refuse_network)
    clear_cache()
    yield
    clear_cache()


def _signature(value):
    value = acb(value)
    return tuple((x.mid(), x.rad()) for x in (value.real, value.imag))


def _finite_overlap(left, right):
    assert left.is_finite() and right.is_finite()
    assert left.overlaps(right)


@pytest.mark.parametrize("value,canonical", [
    (3, 3), (3.0, 3), ("3.00", 3), (Decimal("3"), 3),
    (4, 4), (4.0, 4), ("4e0", 4), (Decimal("4.000"), 4),
    ("3.50", "3.5"), (3.5, "3.5"), (Decimal("3.50"), "3.5"),
    ("5.00", "5"), ("2.250", "2.25"), ("2.1", "2.1"), (8, "8"),
])
def test_eta_canonicalization(value, canonical):
    model = Model(eta=value)
    assert model == Model(eta=canonical)
    assert type(model.eta) is type(canonical) and model.eta == canonical
    assert hash(model) == hash(Model(eta=canonical))
    with localcontext() as context:
        context.prec = 1
        context.traps[Inexact] = context.traps[Rounded] = True
        assert Model(eta=value) == model


@pytest.mark.parametrize("value", [True, False, "NaN", math.nan, Decimal("sNaN"),
                                  math.inf, -math.inf, "Infinity", "7/2", 2, 2.05,
                                  8.5, "1e1000000000", "1e-1000000000"])
def test_eta_invalid_fast(value):
    started = perf_counter()
    with pytest.raises(ValueError, match="eta"):
        Model(eta=value)
    assert perf_counter() - started < 0.1


def test_exponent_bounds_precede_fraction():
    enclosure = Enclosure(0.25, 0.5, Contract("test", "analytic", 160))
    calls = [lambda: Model(d1="1e1000000000"),
             lambda: Model(g="1e-1000000000"),
             lambda: SNRGrid(start="1e1000000000"),
             lambda: enclosure.format(scale="1e1000000000"),
             lambda: _fraction(Decimal("1e-1000000000"), "value")]
    for call in calls:
        started = perf_counter()
        with pytest.raises(ValueError):
            call()
        assert perf_counter() - started < 0.1
    for spelling in ("0e-1000000000", "0e1000000000"):
        assert Model(g=spelling).g == "0"
        assert SNRGrid(start=spelling).start == 0
        assert _fraction(spelling, "value") == 0
    for exponent in (-4000, 4000):
        value = Decimal(f"1e{exponent}")
        assert _bounded(value, "value") == value
        assert _fraction(value, "value") == Fraction(value)
    for exponent in (-4001, 4001):
        with pytest.raises(ValueError):
            _bounded(Decimal(f"1e{exponent}"), "value")
    assert _fraction(0.1, "value") == Fraction(1, 10)
    assert _fraction("7/2", "value") == Fraction(7, 2)


def test_canonical_cache_and_bank_names(monkeypatch):
    with rt.arithmetic(160):
        a = rt.environment(Model(eta=3), "PPP", Numerics(ppp_dft_power=12))
        for spelling in (3.0, "3.00", Decimal("3")):
            assert rt.environment(Model(eta=spelling), "PPP", Numerics(ppp_dft_power=12)) is a
        assert a.names == ["PPP_l0p1_e3.npz"] and not a.generated
        assert rt.environment_name("0.1", Model(eta="3.50").eta, "PPP") == "PPP_l0p1_e3p5.npz"
        # Even a manifest containing a general-eta name must not permit reuse.
        original_manifest = rt._banks.manifest
        with monkeypatch.context() as patch:
            patch.setattr(rt._banks, "manifest", lambda: {
                **original_manifest(), "PPP_l0p1_e3p5.npz": {}})
            b = rt.environment(Model(eta="3.50"), "PPP", Numerics(ppp_dft_power=12))
        assert b.generated and b.names == [] and b is not a
        assert rt.environment(Model(eta=3.5), "PPP", Numerics(ppp_dft_power=12)) is b
        for eta in (3, 4):
            assert type(tf.eta_value(eta)) is int
        assert isinstance(tf.eta_value("3.5"), arb)


@pytest.mark.parametrize("eta", [3, 4])
def test_explicit_transform_is_identical(eta):
    with rt.arithmetic(160):
        for imag in (0, "0.3", 1, 40, 1000):
            s = acb(arb(20) / 128, arb(imag))
            assert _signature(tf.transform(s, "0.1", eta)) == _signature(ppp.transform(s, "0.1", eta))


def test_explicit_arrays_are_identical(monkeypatch):
    with rt.arithmetic(160):
        actual = gen.environment_arrays("0.1", 3, 12, "PPP")
        monkeypatch.setattr(gen, "transform", ppp.transform)
        original = gen.environment_arrays("0.1", 3, 12, "PPP")
    assert actual.keys() == original.keys()
    for name in actual:
        assert actual[name].tobytes() == original[name].tobytes()


@pytest.mark.parametrize("eta", [3, 4])
def test_general_matches_explicit_frequency_grid(eta):
    ratios = []
    with rt.arithmetic(160):
        for k in range((1 << 11) + 1):
            s = acb(arb(20) / 128, 2 * arb.pi() * k / 128)
            general = tf.J_general(s, arb(eta), allow_fallback=False)
            explicit = ppp.J(s, eta)
            _finite_overlap(general, explicit)
            ratio = general.rad() / explicit.rad()
            assert ratio <= 2**16
            ratios.append(float(ratio.upper()))
    print("S17 frequency radii", json.dumps(dict(eta=eta, max_ratio=max(ratios))))


@pytest.mark.parametrize("eta", [3, 4])
@pytest.mark.parametrize("lam", ["0.1", "1"])
def test_general_arrays_overlap_with_bounded_width(monkeypatch, eta, lam):
    with rt.arithmetic(160):
        explicit = gen.environment_arrays(lam, eta, 16, "PPP")
        monkeypatch.setattr(gen, "transform", lambda s, lam, eta:
                            (-2 * arb.pi() * arb(lam) * tf.J_general(s, arb(eta), allow_fallback=False)).exp())
        general = gen.environment_arrays(lam, eta, 16, "PPP")
    assert np.all(np.maximum(explicit["clo"], general["clo"]) <= np.minimum(explicit["chi"], general["chi"]))
    ew, gw = explicit["chi"] - explicit["clo"], general["chi"] - general["clo"]
    assert np.all(gw <= ew * (1 + 2**-20) + 2**-130)
    positive = ew > 0
    print("S17 array widths", json.dumps(dict(eta=eta, lam=lam,
          max_ratio=float(np.max(gw[positive] / ew[positive])),
          equal_fraction=float(np.mean(gw == ew)), nodes=len(ew))))


@pytest.mark.parametrize("eta", ["2.5", "3", "3.3", "3.5", "4", "5", "6.5", "8"])
@pytest.mark.parametrize("imag", ["0.3", "1", "40", "1000"])
def test_general_matches_independent_integral(eta, imag):
    with rt.arithmetic(160):
        s = acb(arb(20) / 128, arb(imag))
        exponents = (2 * Fraction(eta) - 5, 2 * Fraction(eta))
        powers = [int(x) if x.denominator == 1 else arb(str(x)) for x in exponents]
        fractional = any(x.denominator != 1 for x in exponents)

        def integrand(v, analytic):
            if fractional and analytic and not v.real > 0:
                return acb("nan")
            if fractional and not analytic and v.imag.is_zero():
                # The path is [0,1]; restrict endpoint balls to the real path.
                # Real nonnegative powers stay bounded at zero. No complex
                # analyticity is claimed on this endpoint interval.
                v = v.real.nonnegative_part()
            return 2 * s * v ** powers[0] / (1 + s * v ** powers[1])

        reference = acb.integral(integrand, 0, 1, rel_tol=arb(2)**-60)
        _finite_overlap(reference, tf.J_general(s, arb(eta), allow_fallback=False))


@pytest.mark.parametrize("eta", ["2.1", "2.125", "2.2", "2.25"])
@pytest.mark.parametrize("imag", ["0.3", "1", "40", "1000"])
def test_general_matches_independent_integral_near_two(eta, imag):
    # Below eta=2.5 the substitution r=v^(-2) of the previous test has a
    # singular integrand at v=0. Here r=v^(-p), p=1/(eta-2), gives
    # J(s) = p s ∫_0^1 dv / (1 + s v^(p eta)), with integer p and p*eta.
    with rt.arithmetic(160):
        s = acb(arb(20) / 128, arb(imag))
        p = 1 / (Fraction(eta) - 2)
        assert p.denominator == 1 and (p * Fraction(eta)).denominator == 1
        power = int(p * Fraction(eta))

        def integrand(v, analytic):
            return int(p) * s / (1 + s * v ** power)

        reference = acb.integral(integrand, 0, 1, rel_tol=arb(2)**-60)
        assert reference.rad() < arb(2)**-40 * abs(reference).lower()
        _finite_overlap(reference, tf.J_general(s, arb(eta), allow_fallback=False))


@pytest.mark.parametrize("z", [acb(-1), acb(0, 1), acb(0, -1), acb(-0.5, 0.25)])
def test_pfaff_truncated_series_contains_reference(z):
    with rt.arithmetic(160):
        b = arb("0.4")
        reference = z.hypgeom_2f1(1, b, b + 1, abc=True)
        for terms in (1, 2, 5):
            result = tf.pfaff_2f1(z, b, max_terms=terms)
            assert result.is_finite() and reference.is_finite()
            assert result.contains(reference)
        _finite_overlap(tf.pfaff_2f1(z, b), reference)


def test_pfaff_rejects_uncertified_ratio():
    with rt.arithmetic(160):
        for z in (acb("0.75"), acb(1), acb(arb("0 +/- 1"))):
            with pytest.raises(ArithmeticError, match="certified"):
                tf.pfaff_2f1(z, arb("0.5"))


def test_hypergeom_argument_and_abc_flag():
    with rt.arithmetic(160):
        b = arb(2) / 3
        calls = []

        class Argument:
            def hypgeom_2f1(self, a, b, c, **kwargs):
                calls.append((a, b, c, kwargs))
                return acb(-1).hypgeom_2f1(a, b, c, **kwargs)

        result = tf._hypgeom_2f1(Argument(), b)
        assert calls[0][0] == 1 and calls[0][3] == {"abc": True}
        _finite_overlap(result, acb(-1).hypgeom_2f1(1, b, b + 1, abc=True))


@pytest.mark.parametrize("failure", ["nonfinite", "wide", "exception"])
def test_hypergeom_retry_and_fallback(monkeypatch, failure):
    with rt.arithmetic(160):
        s = acb("0.15625", 1)
        expected = tf.J_general(s, arb("3.5"))
        attempts, fallbacks = [], []
        original = tf.pfaff_2f1

        def fail(z, b):
            attempts.append(ctx.prec)
            if failure == "exception":
                raise ValueError("forced 2F1 failure")
            return acb("nan") if failure == "nonfinite" else acb(arb(1, 1))

        def fallback(z, b):
            fallbacks.append(ctx.prec)
            return original(z, b)

        monkeypatch.setattr(tf, "_hypgeom_2f1", fail)
        monkeypatch.setattr(tf, "pfaff_2f1", fallback)
        _finite_overlap(tf.J_general(s, arb("3.5")), expected)
        assert attempts == [160, 320] and fallbacks == [160] and ctx.prec == 160
        with pytest.raises(ArithmeticError, match="relative-radius"):
            tf.J_general(s, arb("3.5"), allow_fallback=False)
        assert ctx.prec == 160
        monkeypatch.setattr(tf, "pfaff_2f1", lambda z, b: acb("nan"))
        with pytest.raises(ArithmeticError, match="Non-finite"):
            tf.J_general(s, arb("3.5"))


def test_hypergeom_retry_recovers_without_fallback(monkeypatch):
    with rt.arithmetic(160):
        original = tf._hypgeom_2f1
        attempts = []

        def retry(z, b):
            attempts.append(ctx.prec)
            return acb("nan") if len(attempts) == 1 else original(z, b)

        monkeypatch.setattr(tf, "_hypgeom_2f1", retry)
        assert tf.J_general(acb("0.15625", 1), arb("3.5"), allow_fallback=False).is_finite()
        assert attempts == [160, 320] and ctx.prec == 160


def test_real_eta_grid_needs_no_fallback():
    with rt.arithmetic(160):
        for k in range((1 << 11) + 1):
            s = acb(arb(20) / 128, 2 * arb.pi() * k / 128)
            assert tf.J_general(s, arb("3.5"), allow_fallback=False).is_finite()
        for s in (0, acb(0, 1), -1, acb(arb("0 +/- 1"))):
            with pytest.raises(ValueError, match="Re"):
                tf.J_general(s, arb("3.5"))


@pytest.mark.parametrize("M", [8, 16])
def test_inverse_dft_normalization(M):
    with rt.arithmetic(160):
        values = [acb(arb(k + 1) / 7, arb(k * k - 2) / 11) for k in range(M)]
        actual = acb.dft(values, inverse=True)
        for j in range(M):
            expected = sum((values[k] * acb(0, 2 * arb.pi() * j * k / M).exp()
                            for k in range(M)), acb(0)) / M
            _finite_overlap(actual[j], expected)


def test_eta_monotonicity():
    numerics = Numerics(bank_policy="fresh")
    results = {key: [] for key in ("outage", "floor", "J_max")}
    for eta in (3, "3.5", 4):
        model = Model(eta=eta)
        results["outage"].append(outage_enclosure(model, 1, 20, numerics=numerics))
        results["floor"].append(floor(model, 1, numerics=numerics))
        results["J_max"].append(largest_interferer_bound(model, 1, numerics=numerics))
    for key, rows in results.items():
        assert all(a.upper >= b.lower for a, b in zip(rows, rows[1:]))
        # These sampled cases are informative enough for disjoint ordering.
        assert all(a.lower > b.upper for a, b in zip(rows, rows[1:]))
        print("S17 monotonicity", key, [(r.lower.hex(), r.upper.hex()) for r in rows])


@pytest.mark.parametrize("convention", ["C-TX", "C-INR"])
@pytest.mark.parametrize("user", [1, 2])
@pytest.mark.parametrize("kind", ["PPP", "Gamma", "mean", "none", "J_max"])
def test_real_eta_all_natures(convention, user, kind):
    model = Model(eta="3.5", convention=convention)
    numerics = Numerics(ppp_dft_power=12)
    results = ([largest_interferer_bound(model, user, numerics=numerics)] if kind == "J_max" else
               [outage_enclosure(model, user, 20, interference=kind, numerics=numerics),
                floor(model, user, interference=kind, numerics=numerics)])
    for result in results:
        assert 0 <= result.lower <= result.upper <= 1
        assert dict(result.contract.parameters)["eta"] == "3.5"
        notes = result.contract.notes
        # The analytic C-INR floor performs no PPP inversion (S19).
        inverted = kind == "PPP" and result.contract.source != "analytic"
        assert any("2F1 identities (Arb, abc=True)" in n for n in notes) == inverted
        assert any("outside the informative domain D_M" in n for n in notes) == inverted
        if kind == "J_max" and convention == "C-TX":
            assert result.contract.source == "mixed"


def test_ppp_domain_notes_and_legacy_contracts():
    numerics = Numerics(ppp_dft_power=18)
    real = outage_enclosure(Model(eta="3.5"), 1, 20, numerics=numerics)
    assert any("inside the informative domain D_M" in note for note in real.contract.notes)
    for eta in (3, 4):
        for value in (eta, float(eta), f"{eta}.00"):
            result = outage_enclosure(Model(eta=value), 1, 20)
            assert result.contract == outage_enclosure(Model(eta=eta), 1, 20).contract
            assert not any("2F1" in n or "D_M" in n for n in result.contract.notes)


def test_domain_notes_only_when_a_ppp_inversion_contributes():
    numerics = Numerics(ppp_dft_power=12)

    def ppp_notes(result):
        return [n for n in result.contract.notes if "2F1" in n or "D_M" in n]

    silent = [outage_enclosure(Model(lam=0, eta="3.5"), 1, 20, numerics=numerics),
              outage_enclosure(Model(lam=0, eta="3.5", N=16), 1, 20, numerics=numerics),
              outage_enclosure(Model(g=0, eta="3.5"), 1, 20, numerics=numerics),
              outage_enclosure(Model(g=0, eta="3.5", N=8), 1, 20, numerics=numerics),
              floor(Model(eta="3.5", convention="C-INR"), 1, numerics=numerics),
              floor(Model(lam=0, eta="3.5"), 1, numerics=numerics),
              outage_enclosure(Model.from_link(p1="0.5", p2="0.5", eta="3.5"), 1, 20,
                               numerics=numerics)]
    for result in silent:
        assert ppp_notes(result) == []
    assert ppp_notes(silent[2]) == [] and "g=0: no interference contribution" in silent[2].contract.notes
    # lam=0 and g=0 give the exact case without interference.
    none = outage_enclosure(Model(eta="3.5"), 1, 20, interference="none", numerics=numerics)
    assert (silent[0].lower, silent[0].upper) == (none.lower, none.upper)
    assert (silent[2].lower, silent[2].upper) == (none.lower, none.upper)
    # Positive witnesses: noninteger eta, and an integer eta other than 3 or 4
    # (stored as the string "5", it also takes the 2F1 path).
    for eta in ("3.5", 5):
        used = outage_enclosure(Model(lam="0.001", eta=eta), 1, 20, numerics=numerics)
        assert len(ppp_notes(used)) == 2
    for eta in (3, 4):
        explicit = outage_enclosure(Model(lam="0.001", eta=eta), 1, 20, numerics=numerics)
        assert ppp_notes(explicit) == []


@pytest.mark.parametrize("lam", ["0", "0.001", "10"])
@pytest.mark.parametrize("eta", ["2.1", "2.5", "8"])
@pytest.mark.parametrize("kind", ["PPP", "Gamma", "mean"])
def test_technical_domain_corners(lam, eta, kind):
    started = perf_counter()
    result = outage_enclosure(Model(lam=lam, eta=eta), 1, 20,
                              interference=kind, numerics=Numerics(ppp_dft_power=12))
    seconds = perf_counter() - started
    assert 0 <= result.lower <= result.upper <= 1
    assert seconds < 60
    print("S17 corner", json.dumps(dict(lam=lam, eta=eta, kind=kind, seconds=seconds)))


def test_remainders_e6_and_monotonicities():
    with rt.arithmetic(160):
        for eta, power, expected in [(4, 18, 1.06e-5), (4, 20, 3.7e-18), (5, 20, 0.091)]:
            r, _ = tf.remainders("0.1", eta, power)
            assert float(arb(20).exp() * r) == pytest.approx(expected, rel=0.01)
        _, tau = tf.remainders(10, "3.5", 18)
        assert float(tau) == pytest.approx(2.49e-10, rel=0.01)
        C_tau = arb(64) + arb("1e-10").log()
        assert float(C_tau) == pytest.approx(40.974, rel=0.01)
        assert float(C_tau / (2 * arb.pi())) == pytest.approx(6.521, rel=0.01)
        for eta in ("2.1", 3, "3.5", 4, 8):
            data = [tf.remainders(lam, eta, 18) for lam in ("0.01", "0.1", "1")]
            assert all(a[0] > b[0] and a[1] < b[1] for a, b in zip(data, data[1:]))
            radii = [tf.remainders("0.1", eta, p)[0] for p in (12, 16, 18, 20)]
            assert all(a > b for a, b in zip(radii, radii[1:]))
        data = [tf.remainders("0.1", eta, 18) for eta in ("2.1", "2.5", 3, "3.5", 4, 8)]
        assert all(a[0] < b[0] and a[1] > b[1] for a, b in zip(data, data[1:]))
        assert not tf.informative("0.1", 4, 18)
        assert tf.informative("0.1", 4, 20)
        assert not tf.informative(0, "3.5", 18)


def test_lambda_window_certifies_boundaries_and_empty_case():
    with rt.arithmetic(160):
        for eta, power in [("2.5", 16), ("3.5", 18), (4, 20), (8, 18)]:
            window = tf.lambda_window(eta, power)
            assert not window.empty
            left, right = window.lambda_R
            r0 = arb("1e-7") * (-arb(20)).exp()
            assert tf.remainders(arb(left), eta, power)[0] > r0
            assert tf.remainders(arb(right), eta, power)[0] < r0
            assert tf.remainders(arb(left).union(arb(right)), eta, power)[0].contains(r0)
            assert tf.informative(arb(right), eta, power)
            assert not tf.informative(arb(left), eta, power)
            lower_tau, upper_tau = window.lambda_tau
            exact_tau = (arb(64) + arb("1e-10").log()) * (arb(eta) - 2) / (2 * arb.pi())
            assert arb(lower_tau) <= exact_tau <= arb(upper_tau)
        # M=64 is in the monotone regime Omega=pi*M/128>=1 (M>=41; PROOFS.md,
        # Proposition 4.5), below the public DFT range.
        assert tf.lambda_window(8, 6).empty
        assert tf.lambda_window(8, 12, eps_tau="1e-30").empty
        with pytest.raises(ValueError):
            tf.lambda_window(4, 5)


def test_lambda_window_near_two():
    # D8: the window at the lower end of the accepted eta range (S19b).
    with rt.arithmetic(160):
        r0 = arb("1e-7") * (-arb(20)).exp()
        for eta, power in [("2.1", 18), ("2.1", 12), ("2.2", 18)]:
            window = tf.lambda_window(eta, power)
            assert not window.empty
            left, right = window.lambda_R
            assert tf.remainders(arb(left), eta, power)[0] > r0
            assert tf.remainders(arb(right), eta, power)[0] < r0
            assert tf.informative(arb(right), eta, power)
            assert not tf.informative(arb(left), eta, power)
            exact_tau = (arb(64) + arb("1e-10").log()) * (arb(eta) - 2) / (2 * arb.pi())
            assert arb(window.lambda_tau[0]) <= exact_tau <= arb(window.lambda_tau[1])
            print("S19b window", eta, power, window.lambda_R, window.lambda_tau)
        window = tf.lambda_window("2.1", 18)
        assert 0.0015 < window.lambda_R[0] <= window.lambda_R[1] < 0.0017
        assert window.lambda_tau[0] == pytest.approx(0.6521, rel=1e-3)
        assert tf.informative("0.1", "2.1", 18)
        assert not tf.informative("0.7", "2.1", 18)


def test_trivial_regime_above_the_aliasing_threshold():
    # tau*a0 >= 1 iff lam >= (64 + log expm1(20))(eta-2)/(2 pi), about
    # 13.37(eta-2) (PROOFS.md, Proposition 4.7; S19b).
    with rt.arithmetic(160):
        threshold = (arb(64) + arb(20).expm1().log()) * (arb("2.1") - 2) / (2 * arb.pi())
        assert arb("1.33") < threshold < arb("1.34")
        for lam, eta, expected in [("1.33", "2.1", False), ("1.34", "2.1", True),
                                   ("10", "2.5", True), ("10", "2.747", True),
                                   ("10", "2.748", False), ("10", 3, False), ("10", "3.5", False)]:
            assert tf.aliasing_exceeds_one(lam, eta, 12) is expected
            assert tf.aliasing_exceeds_one(lam, eta, 18) is expected
    numerics = Numerics(ppp_dft_power=12)

    def trivial(result):
        return any("tau*a0 >= 1" in n for n in result.contract.notes)

    below = outage_enclosure(Model(lam="1.33", eta="2.1"), 1, 20, numerics=numerics)
    above = outage_enclosure(Model(lam="1.34", eta="2.1"), 1, 20, numerics=numerics)
    weak = outage_enclosure(Model(lam="2", eta="2.1", g="1/100"), 1, 20, numerics=numerics)
    assert not trivial(below) and trivial(above) and trivial(weak)
    # Just below, the width is about tau*a0 = 0.65; above, the bound is trivial,
    # even with a weak interference gain.
    assert 0.3 < below.lower < 0.4 and below.upper == 1
    assert above.lower < 1e-20 and above.upper == 1
    assert weak.lower < 1e-20 and weak.upper == 1
    for result in (below, above, weak):
        assert any("outside the informative domain D_M" in n for n in result.contract.notes)
    # No note where no inversion contributes, nor on the explicit eta=3 path.
    assert not trivial(outage_enclosure(Model(lam="2", eta="2.1", g=0), 1, 20, numerics=numerics))
    assert not trivial(outage_enclosure(Model(lam="10", eta=3), 1, 20, numerics=numerics))


def test_threshold_difference_uses_exact_eta():
    result = outage_enclosure(Model(eta="3.5"), 1, 20, interference="none")
    first = SNRDecision("feasible", 10.0, 11.0, result, "test", 0, "test", target="0.1")
    fields = dict(result.contract.parameters)
    fields["eta"] = "4"
    second = replace(first, evaluation_contract=replace(result.contract, parameters=tuple(fields.items())))
    with pytest.raises(ValueError, match="eta"):
        threshold_difference(first, second)
    fields["eta"] = "3.50"
    second = replace(second, evaluation_contract=replace(result.contract, parameters=tuple(fields.items())))
    difference = threshold_difference(first, second)
    assert (difference.lower, difference.upper) == (-1.0, 1.0)


def test_exponent_guard_boundaries():
    # Small direct probes also kill a missing-guard mutation without allocating
    # the enormous integers used by the bounded-time validation test.
    for exponent in (-4001, 4001):
        with pytest.raises(ValueError, match="exponent"):
            _bounded(Decimal(f"1e{exponent}"), "value")


@pytest.mark.parametrize("convention,kind,expected", [
    ("C-TX", "PPP", ("0x1.acd83c15b8b9bp-19", "0x1.56868cafa9c81p-9")),
    ("C-INR", "PPP", ("0x1.5fe3a357a21c7p-72", "0x1.558b5e12a8c01p-9")),
    ("C-TX", "Gamma", ("0x1.a8f3ebc3f1ac0p-18", "0x1.b2d4742d04d21p-18")),
])
def test_real_eta_snapshot(convention, kind, expected):
    # S17 snapshot, not an independent check.
    result = outage_enclosure(Model(eta="3.5", convention=convention), 1, 20,
                              interference=kind, numerics=Numerics(ppp_dft_power=12))
    assert (result.lower.hex(), result.upper.hex()) == expected


@pytest.mark.parametrize("eta,expected", [("3.50", "3.5"), ("4.0", 4)])
def test_regenerate_tool_canonical_eta(monkeypatch, tmp_path, capsys, eta, expected):
    from pathlib import Path
    import runpy
    import sys
    tool = Path(__file__).resolve().parents[2] / "tools/regenerate_ppp.py"
    output = tmp_path / "bank.npz"
    monkeypatch.setattr(sys, "argv", [str(tool), "--eta", eta, "--lam", "0.001",
                                     "--power", "12", "--output", str(output)])
    runpy.run_path(str(tool), run_name="__main__")
    result = json.loads(capsys.readouterr().out)
    assert result["eta"] == expected and type(result["eta"]) is type(expected)
    assert output.is_file()
