"""Vérifie la branche de génération, distincte des banques centrales."""
from certoutage import Model, Numerics, floor, outage_enclosure, required_snr


def test_new_intensity_and_two_precisions():
    model = Model(N=16, lam="0.2", eta=3, convention="C-TX")
    a = floor(model, 1)
    b = floor(model, 1, numerics=Numerics(precision_bits=192, ppp_dft_power=19))
    assert a.contract.source == b.contract.source == "mixed"
    assert a.lower > .002 and b.lower > .002
    assert max(a.lower, b.lower) <= min(a.upper, b.upper)
    assert b.upper - b.lower <= a.upper - a.lower
    assert required_snr(model, 1, ".002").status == "excluded"


def test_new_gamma_and_largest_distribution():
    from certoutage import largest_interferer_bound
    model = Model(N=16, lam="0.2", eta=3)
    gamma = floor(model, 1, interference="Gamma")
    bound = largest_interferer_bound(model, 1)
    assert gamma.contract.source == bound.contract.source == "mixed"
    assert 0 < gamma.lower <= gamma.upper < 1
    assert bound.lower <= floor(model, 1).upper
