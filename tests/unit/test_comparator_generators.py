"""Offline archive checks and independent integrals for comparator generators."""
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import socket
import math

import numpy as np
import pytest
from flint import acb, arb, ctx

from certoutage import _banks, _runtime as rt, clear_cache
from certoutage import _generate_gain as gen, _nakagami as nak


def _refuse_network(*args, **kwargs):
    raise AssertionError("Comparator-generator tests attempted network access")


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv("CERTOUTAGE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(socket, "socket", _refuse_network)
    monkeypatch.setattr(socket, "create_connection", _refuse_network)
    clear_cache()
    yield
    clear_cache()


@pytest.fixture(scope="module")
def banks():
    return {name: _banks.arrays(name) for name in (
        "m2_N8.npz", "m3_N8.npz", "SIG_m2_N8.npz", "SIG_m3_N8.npz", "commun.npz",
        "C_N8.npz", "C_N64.npz")}


@pytest.fixture(scope="module")
def reduced():
    return {(m, N, power): gen.gain_arrays(N, m=m, power=power)
            for m, N, power in ((2, 8, 12), (3, 8, 12), (3, 64, 14))}


# Filled from the isolated historical amplitude.py, with only M changed.
HISTORICAL = {(2, 8, 12): {'B': 'a3fd08764e225228ee3e534d14ba14b56418d9f2c40c4b529cc9df6acafaff13',
              'N': '6cc16abd70eefb90dc0ba0d14fb088630873b2c6ad943f7442356735984c35a3',
              'exact_hi': '40675efac7daf4bc06d2768a4b7df09dcd30bf94e0cd23bb2099043d45f7dc27',
              'exact_lo': '0edfeb05d29e6e5f5f98b2a31f499a7c822cd15653d0340ccee3a48a8b8cdaa7',
              'gauss_hi': '71b1c0233d447c381e311d519530554d75052458a8ad09a9cfc7234c8bcbabc8',
              'gauss_lo': '7f8e063ebe8495ac4bf0330092be109fe480996f51f73555ca0527e4a7f3b075',
              'm': 'd86e8112f3c4c4442126f8e9f44f16867da487f29052bf91b810457db34209a4'},
 (3, 8, 12): {'B': 'a3fd08764e225228ee3e534d14ba14b56418d9f2c40c4b529cc9df6acafaff13',
              'N': '6cc16abd70eefb90dc0ba0d14fb088630873b2c6ad943f7442356735984c35a3',
              'exact_hi': 'd4a62121a3be9b29865eef5e42dfe15b388b8c32b579109cead7b44f17fda005',
              'exact_lo': '22d7e0e446de9ae5d7ddcd16812b1233bd1e6236eef5a2bc586f51c9533a4044',
              'gauss_hi': '7cfec6f68acb8f93af83a0651c400b270390f9bfc1eb1a1a8942ea0fad7f2621',
              'gauss_lo': '582a690fd1c87768776e6af52ae2c5158b604cd48555f4288523236fafef4f47',
              'm': '35be322d094f9d154a8aba4733b8497f180353bd7ae7b0a15f90b586b549f28b'},
 (3, 64, 14): {'B': 'ac4fc487af43d39412a7f3fa4101e7128836a2fce14054521fff83f2721a82b9',
               'N': 'a06f129fc52abf6085679d7cd71dc41ec7580c7f5f73efef6d02dde22bb00994',
               'exact_hi': '98617e26734f4edf873f9205623269495cef0fcb6fe030577c2934a6938b35ed',
               'exact_lo': '9398d5ee73040e8d4771309c9319609d69f72b62ad228cf9affd6bc40da06ece',
               'gauss_hi': '5896aad9eae50127fa01da56b0b31eeb6d03137631e98eeba3d6ecf29a2c4135',
               'gauss_lo': '6da08c5695347428dcec9774059e7edb4d9840cfd5e81512b8a437fff8c7d442',
               'm': '35be322d094f9d154a8aba4733b8497f180353bd7ae7b0a15f90b586b549f28b'}}


def test_nakagami_historical_bytes(reduced):
    for key, data in reduced.items():
        assert list(data) == ["N", "m", "B", "exact_lo", "exact_hi", "gauss_lo", "gauss_hi"]
        assert {name: sha256(a.tobytes()).hexdigest() for name, a in data.items()} == HISTORICAL[key]
        for name in ("N", "m", "B"):
            assert data[name].shape == () and data[name].dtype == np.int64


@pytest.mark.parametrize("m", [2, 3])
def test_nakagami_embedded_overlap(banks, reduced, m):
    data, ref = reduced[m, 8, 12], banks[f"m{m}_N8.npz"]
    for method in ("exact", "gauss"):
        lo, hi = data[method + "_lo"], data[method + "_hi"]
        assert np.all(np.maximum(lo, ref[method + "_lo"][::128]) <=
                      np.minimum(hi, ref[method + "_hi"][::128]))


def _independent_transform(s, m):
    # Rotate inside Re(a)>0; K0 has no cut here, and Re((s+2m)a)>0.
    # Exclude the logarithmic origin and bound both omitted pieces explicitly.
    direction = (s + 2*m).conjugate() / abs(s + 2*m)
    epsilon, A = arb(2)**-44, 100 / abs(s + 2*m)
    p = 2*m-1
    C = 4 * arb(m)**(2*m) / arb.fac_ui(m-1)**2

    def integrand(a, analytic):
        if not (a.real > 0 or a.imag > 0 or a.imag < 0):
            return acb("nan")
        return (-s*a).exp() * C * a**p * (2*m*a).bessel_k(0)

    cuts = [epsilon, A/256, A/16, A/4, A/2, 3*A/4, A]
    core = sum((acb.integral(integrand, a*direction, b*direction,
                            rel_tol=arb(2)**-65, abs_tol=arb(2)**-75, eval_limit=10000)
                for a, b in zip(cuts[:-1], cuts[1:])), acb(0))
    r = direction.real.lower()
    d = ((s + 2*m)*direction).real.lower()
    # |K0(2m*direction*a)| <= log(1/(m*r*a))+1 near zero.
    small = C * epsilon**(p+1)/(p+1) * ((1/(m*r*epsilon)).log()+1+arb(1)/(p+1))
    # cosh(u)>=1+u^2/2 gives K0(2m*r*a)<=sqrt(pi/(4m*r*a))*exp(-2m*r*a).
    # For a>=A, a^(p-1/2)<=a^p/sqrt(A); integrate that integer power exactly.
    integral_tail = (-d*A).exp() * sum(
        (arb.fac_ui(p)/arb.fac_ui(p-k)*A**(p-k)/d**(k+1) for k in range(p+1)), arb(0))
    tail = C*(arb.pi()/(4*m*r*A)).sqrt()*integral_tail
    error = arb(0, (small+tail).upper())
    return core + acb(error, error)


@pytest.fixture(scope="module")
def independent_integrals():
    # Extra guard bits keep large-argument Bessel cancellations narrow.
    with rt.arithmetic(256):
        return [(m, s, _independent_transform(s, m)) for m in (2, 3)
                for c in (arb(20)/96, arb(20)/232, arb(1), arb(3))
                for t in (arb(0), arb(2), arb.pi()*(1 << 19)/232)
                for s in (acb(c, t),)]


def test_nakagami_independent_integral(independent_integrals):
    with rt.arithmetic(160):
        for m, s, reference in independent_integrals:
            value = nak.L(s, m)
            assert reference.is_finite() and value.is_finite()
            assert reference.rad() < arb('1e-10')
            assert reference.overlaps(value)


@pytest.mark.parametrize("m", [2, 3])
def test_nakagami_zero_and_derivative(m):
    with rt.arithmetic(160):
        assert nak.L(0, m).contains(1)
        h = arb(2)**-60
        difference = (nak.L(0, m).real - nak.L(h, m).real)/h
        # Forward difference: 0<=E[V]-(1-L(h))/h<=h E[V^2]/2.
        # E[V^2]=E[E]E[F]=1 for two independent Gamma(m,1/m) factors.
        derivative = difference + arb(0).union(h/2)
        assert derivative.overlaps(nak.mu(m))
        assert derivative.rad() < arb('1e-17')


def _density(a, m):
    return 4*arb(m)**(2*m)/arb.fac_ui(m-1)**2 * a**(2*m-1)*(2*m*a).bessel_k(0)


def _critical_bracket(m):
    def sign(a):
        x = 2*m*a
        return 2*m-1-x*x.bessel_k(1)/x.bessel_k(0)
    lo, hi = arb('0.001'), arb(5)
    assert sign(lo) > 0 and sign(hi) < 0
    for _ in range(90):
        mid = (lo+hi)/2
        if sign(mid)>0:
            lo=mid
        elif sign(mid)<0:
            hi=mid
        else:
            break
    assert sign(lo)>0 and sign(hi)<0
    return lo.union(hi)


@pytest.mark.parametrize("m", [1, 2, 3])
def test_variation_independent_maximum(m):
    with rt.arithmetic(160):
        peak = _critical_bracket(m)
        twice_max = 2*_density(peak, m)
        assert twice_max < nak.variation(m)
        assert twice_max.rad() < arb('1e-20')


def test_variation_frequency_bound(independent_integrals):
    with rt.arithmetic(160):
        checked=0
        for m, s, value in independent_integrals:
            if not s.imag.is_zero():
                assert abs(value) <= (nak.variation(m)+s.real)/abs(s.imag)
                checked+=1
        assert checked >= 12


@pytest.fixture(scope="module")
def raw(banks):
    return gen.nakagami_signal_points(banks['m2_N8.npz'], banks['commun.npz'],
                                      [0, 256, 512, 607, 624, 640, 680, 720, 800, 1024])


def test_nakagami_signal_archive(banks, raw):
    for name in ('exact', 'gauss'):
        assert raw[name].tobytes() == banks['SIG_m2_N8.npz'][name][:, raw['indices']].tobytes()
    assert np.any(raw['levels']>9)
    with rt.arithmetic(160):
        assert any(any(arb(b)-arb(a)>arb('.008')*arb(a) for a,b in
                       (raw[name][:,k] for name in ('exact','gauss')))
                   and raw['levels'][k]<13 for k in range(len(raw['indices'])))


def _parts(raw, groups, methods=('exact','gauss')):
    return [dict(indices=np.asarray(group, dtype=np.int64),
                 **{name: raw[name][..., group] for name in (*methods, 'levels')}) for group in groups]


def test_nakagami_partition_bytes(banks):
    args = banks['m2_N8.npz'], banks['commun.npz']
    full = gen.nakagami_signal_points(*args, [640,641,642,643])
    parts = [gen.nakagami_signal_points(*args, indices) for indices in ([643,641],[642,640])]
    for part in [full,*parts]:part['indices'] -= 640
    expected = gen.nakagami_finish_signal([full], _size=4)
    actual = gen.nakagami_finish_signal(parts, _size=4)
    assert list(actual)==['units128','exact','gauss']
    assert actual['units128'].tolist()==[-4096,-4088,-4080,-4072]
    for name in actual:assert actual[name].tobytes()==expected[name].tobytes()


def test_nakagami_finish_guards_and_no_tightening():
    values=np.array([[.8,.7,.75,.2],[.9,.8,.85,.4]])
    raw=dict(exact=values.copy(),gauss=values.copy(),levels=np.full(4,9,dtype=np.int8))
    parts=_parts(raw,[[2,0],[3,1]])
    actual=gen.nakagami_finish_signal(parts,_size=4)
    assert actual['exact'].tobytes()==values.tobytes()
    for bad in ([parts[0]],parts+[parts[0]],_parts(raw,[[0,0,1,2,3]])):
        with pytest.raises(ValueError):gen.nakagami_finish_signal(bad,_size=4)
    raw['exact'][0,0]=1
    with pytest.raises(ArithmeticError):gen.nakagami_finish_signal(_parts(raw,[[0,1,2,3]]),_size=4)


@pytest.mark.parametrize('m',[0,4,2.5,True,np.bool_(True),'2',None])
def test_nakagami_domain(m):
    with pytest.raises(ValueError,match='integer'):
        gen.gain_arrays(8,m=m,power=10)
