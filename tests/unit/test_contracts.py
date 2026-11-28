import math
from decimal import Decimal
from dataclasses import replace
from importlib.resources import files

from flint import ctx
import pytest

from certoutage import (Model, Numerics, SNRGrid, floor, outage_enclosure, required_snr,
                        largest_interferer_bound, threshold_difference, clear_cache, IntegrityError)


@pytest.mark.parametrize("kwargs", [dict(N=0), dict(N=65), dict(N=True), dict(m=1.5),
    dict(eta=2), dict(lam=-1), dict(lam="nan"), dict(lam=True),
    dict(lam=11), dict(R0=2), dict(convention="TX")])
def test_invalid_models(kwargs):
    with pytest.raises(ValueError):
        Model(**kwargs)


@pytest.mark.parametrize("args", [(1, "nan"), (1, math.inf), (0, 1), (True, 1), (1, 1001)])
def test_invalid_queries(args):
    with pytest.raises(ValueError):
        outage_enclosure(Model(), *args)


@pytest.mark.parametrize("target", [0, 1, -0.01, "NaN", True])
def test_invalid_targets(target):
    with pytest.raises(ValueError):
        required_snr(Model(), 1, target)


def test_grid_and_numerics_validation():
    for kw in [dict(step=0), dict(start=5, stop=4), dict(step="0.1"), dict(stop=95, step=2)]:
        with pytest.raises(ValueError):
            SNRGrid(**kw)
    for kw in [dict(precision_bits=53), dict(ppp_dft_power=11), dict(bank_policy="guess")]:
        with pytest.raises(ValueError):
            Numerics(**kw)


def test_censored_left_is_feasible_without_invented_lower():
    result = required_snr(Model(convention="C-INR"), 1, "0.99", SNRGrid(10, 11))
    assert result.status == "feasible" and result.lower_db == -math.inf
    assert result.upper_db == 10 and "censored" in result.reason
    with pytest.raises(ValueError):
        threshold_difference(result, result)


def test_finite_grid_never_excludes_every_snr():
    result = required_snr(Model(convention="C-INR"), 1, "1e-5", SNRGrid(-40, -39))
    assert result.status == "inconclusive" and result.reason == "search grid exhausted"


def test_chernoff_cannot_exclude_outage():
    result = required_snr(Model(N=20), 1, "1e-5", gain="chernoff")
    assert result.floor.lower > 1e-5 and result.status == "inconclusive"
    assert "Chernoff" in result.scope
    with pytest.raises(ValueError):
        floor(Model(m=2), 1, gain="chernoff")


def test_context_is_restored_and_provenance_visible():
    old = ctx.prec
    ctx.prec = 80
    try:
        r = outage_enclosure(Model(), 1, 0, numerics=Numerics(precision_bits=192))
        assert ctx.prec == 80
        assert r.contract.precision_bits == 192 and r.contract.bank_precision_bits == 160
        assert len(r.contract.banks) == 2 and r.contract.source == "provided-banks"
    finally:
        ctx.prec = old


def test_monotonicity_and_zero_floor():
    m = Model(convention="C-INR")
    rows = [outage_enclosure(m, 2, x) for x in [-10, 0, 10, 40]]
    assert all(a.lower >= b.lower and a.upper >= b.upper for a, b in zip(rows, rows[1:]))
    assert floor(m, 2).as_dict() == {"lower": 0.0, "upper": 0.0}
    assert floor(Model(lam=0), 1).as_dict() == {"lower": 0.0, "upper": 0.0}


def test_rounding_is_outward():
    r = floor(Model(), 1)
    assert r.format(scale="1e-5") == "[1.7136, 1.7478]"
    with pytest.raises(ValueError):
        r.format(scale=0)


def test_integrity_check_precedes_deserialization(monkeypatch):
    from certoutage import _banks
    original = _banks.files

    class Broken:
        def joinpath(self, *args):
            self.path = args
            return self
        def read_bytes(self):
            if self.path == ("data/MANIFEST.json",):
                return original("certoutage").joinpath(*self.path).read_bytes()
            return b"corrupted archive bank"

    clear_cache()
    monkeypatch.setattr(_banks, "files", lambda _: Broken())
    with pytest.raises(IntegrityError, match="SHA-256"):
        outage_enclosure(Model(), 1, 0)
    clear_cache()


def test_central_largest_bound_is_not_a_ppp_upper_bound():
    b = largest_interferer_bound(Model(), 1)
    assert b.upper < 1e-5 < floor(Model(), 1).lower
    assert b.contract.source == "provided-certificate"


def test_threshold_display_on_fine_grid_is_outward():
    from certoutage import ThresholdDifference
    assert ThresholdDifference(1 / 128, 1 / 128).format() == "[0.0078, 0.0079]"


def test_tiny_intensity_returns_valid_coarse_enclosure():
    result = outage_enclosure(Model(lam="1e-500"), 1, 0)
    assert 0 <= result.lower <= result.upper <= 1
    assert result.contract.source == "mixed"


def test_almost_archived_intensity_does_not_select_wrong_bank(monkeypatch):
    from certoutage import _runtime as runtime
    from certoutage import _banks
    calls = []
    def generate(lam, eta, power, kind):
        calls.append(lam)
        return _banks.arrays("PPP_l0p1_e4.npz")
    monkeypatch.setattr(runtime, "environment_arrays", generate)
    lam = "0.1000000000000000000000000001"
    with runtime.arithmetic(160):
        env = runtime.Environment(Model(lam=lam), "PPP", Numerics())
    assert calls == [lam] and env.generated and not env.names


def test_largest_inr_limit_is_labelled_correctly():
    result = largest_interferer_bound(Model(convention="C-INR"), 1)
    assert result.as_dict() == {"lower": 0.0, "upper": 0.0}
    assert "lim" in result.contract.quantity
