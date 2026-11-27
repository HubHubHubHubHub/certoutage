"""Rayleigh inversion, independent Laplace integrals and offline signal checks."""
from fractions import Fraction
from pathlib import Path
import math
import socket

import numpy as np
from flint import acb, arb, ctx
import pytest

from certoutage import _banks, _runtime as rt, clear_cache
from certoutage import _generate_gain as gen
from certoutage._vendor import nak_thermal, thermal_backend
from certoutage._vendor.nak_grouped import Grouped


def _refuse_network(*args, **kwargs):
    raise AssertionError("Gain-generator tests attempted network access")


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
    return {name: _banks.arrays(name) for name in ("m1_N8.npz", "m1_N64.npz", "commun.npz", "SIG_8.npz")}


@pytest.fixture(scope="module")
def reduced():
    return {8: gen.gain_arrays(8, power=12), 64: gen.gain_arrays(64, power=14)}


@pytest.fixture(scope="module")
def raw(banks):
    # Chosen by replaying the historical point loop, before final tightening.
    indices = [0, 9180, 10098, 10557, 13200, 13312, 14000, 20480]
    return gen.signal_points(banks["m1_N8.npz"], banks["commun.npz"], indices)


def test_gain_period_integer_grid():
    # Independent integer square intervals, including every square boundary.
    ceiling = 1
    for N in range(1, 1000001):
        if N > ceiling * ceiling:
            ceiling += 1
        assert gen.gain_period(N) == N + 16 * ceiling + 40
    assert [gen.gain_period(n) for n in (8, 12, 16, 20, 24, 32, 48, 64)] == [96, 116, 120, 140, 144, 168, 200, 232]


@pytest.mark.parametrize("N", [0, 7, 65, -1, True, False, np.bool_(True), 8.0, "8", None])
def test_gain_domain(N):
    with pytest.raises(ValueError, match=r"\[8, 64\]"):
        gen.gain_arrays(N)


@pytest.mark.parametrize("power", [9, 20, -1, True, 12.0, "12"])
def test_gain_power(power):
    with pytest.raises(ValueError, match=r"\[10, 19\]"):
        gen.gain_arrays(8, power=power)


def test_kernel_remainder_guards():
    with pytest.raises(ValueError, match="even M"):
        gen._gain_kernel(1, 0)
    with pytest.raises(ValueError, match="M >= N"):
        gen._gain_kernel(3, 1)
    for N in (True, 0, 1.5):
        with pytest.raises(ValueError, match="N"):
            gen._gain_kernel(N, 10)


@pytest.mark.parametrize("N,power", [(8, 12), (64, 14)])
def test_embedded_gain_overlap(banks, reduced, N, power):
    actual, reference = reduced[N], banks[f"m1_N{N}.npz"]
    assert list(actual) == ["N", "B", "exact_lo", "exact_hi", "gauss_lo", "gauss_hi"]
    for name in ("N", "B"):
        assert actual[name].shape == () and actual[name].dtype == np.int64
        assert actual[name].tobytes() == reference[name].tobytes()
    for method in ("exact", "gauss"):
        lo, hi = actual[method + "_lo"], actual[method + "_hi"]
        assert lo.dtype == hi.dtype == np.float64 and lo.shape == hi.shape == ((1 << power) + 1,)
        step = 1 << (19 - power)
        assert np.all(np.maximum(lo, reference[method + "_lo"][::step]) <=
                      np.minimum(hi, reference[method + "_hi"][::step]))
    # At this reduced grid the Fourier remainder is resolvable in binary64.
    if N == 8:
        assert 6e-10 < np.max(actual["exact_hi"] - actual["exact_lo"]) < 8e-10


def test_alias_is_one_sided(monkeypatch):
    # Vary only the tail input: the Fourier coefficients stay unchanged.
    # A visible test tail distinguishes the unidirectional alias from a
    # symmetric error or an omitted alias, without relying on tiny rounding.
    original = gen.L
    with rt.arithmetic(160):
        tail_root = (arb(96) / 8).exp() / 2
        monkeypatch.setattr(gen, "L", lambda s: acb(tail_root) if s == -1 else original(s))
        raised = gen.gain_arrays(8, power=12)
        monkeypatch.setattr(gen, "L", lambda s: acb(0) if s == -1 else original(s))
        zero = gen.gain_arrays(8, power=12)
    j = 250
    expected = float((arb(1) / 256 / arb(20).expm1()).mid())
    assert abs(raised["exact_lo"][j] - zero["exact_lo"][j]) < 2e-15
    assert abs((raised["exact_hi"][j] - zero["exact_hi"][j]) - expected) < 2e-15


@pytest.mark.parametrize("c_index,t_index", [(c,t) for c in range(5) for t in range(3)])
def test_laplace_independent_integral(c_index, t_index):
    with rt.arithmetic(160):
        cs = [arb(20)/96, arb(20)/144, arb(20)/232, arb(1), arb('1.9')]
        ts = [arb(0), arb(2), arb.pi() * (1 << 19) / 96]
        s = acb(cs[c_index], ts[t_index])
        # Rotate within the right half-plane to avoid high-frequency
        # oscillation. K0 is analytic away from its negative-real cut and
        # Re((s+2)*a)>0 throughout the swept sector, so the arc at infinity
        # vanishes. The origin is excluded, never claimed analytic.
        direction = (s + 2).conjugate() / abs(s + 2)
        epsilon, A = arb(2)**-40, 80 / abs(s + 2)

        def integrand(a, analytic):
            if not (a.real > 0 or a.imag > 0 or a.imag < 0):
                return acb("nan")
            return (-s*a).exp() * 4*a * (2*a).bessel_k(0)

        cuts = [epsilon, A/256, A/16, A/4, A]
        core = sum((acb.integral(integrand, a*direction, b*direction,
                                 rel_tol=arb(2)**-65, abs_tol=arb(2)**-75, eval_limit=10000)
                    for a, b in zip(cuts[:-1], cuts[1:])), acb(0))
        # K0(2z)=int exp(-2z cosh u)du. For r=Re(direction)>0:
        # |K0(2 direction*a)| <= E1(r*a) <= log(1/(r*a))+1 near 0.
        # Thus the omitted initial segment is <= eps^2*(2 log(1/(r eps))+3).
        # cosh u>=1+u^2/2 also gives |K0(2z)|<=sqrt(pi/(4 Re z))*exp(-2 Re z).
        # For a>=A, sqrt(a)<=a/sqrt(A), giving the explicit tail below.
        r = direction.real.lower()
        d = ((s + 2) * direction).real.lower()
        small = epsilon**2 * (2*(1/(r*epsilon)).log() + 3)
        tail = 2*arb.pi().sqrt()/(r*A).sqrt() * (-d*A).exp() * (A/d + 1/d**2)
        error = arb(0, (small + tail).upper())
        reference = core + acb(error, error)
        value = gen.L(s)
        assert reference.is_finite() and value.is_finite()
        assert reference.rad() < arb('1e-10')
        assert reference.overlaps(value)


def test_laplace_at_zero_and_derivative():
    with rt.arithmetic(160):
        assert gen.L(0).contains(1)
        h = arb(2)**-60
        difference = (gen.L(0).real - gen.L(h).real) / h
        # Forward difference; 0 <= E[A]-(1-L(h))/h <= h E[A^2]/2.
        # The independent density moment int 4a^3 K0(2a) da = Gamma(2)^2 = 1.
        derivative = difference + arb(0).union(h/2)
        assert derivative.overlaps(arb.pi()/4)
        assert derivative.rad() < arb('1e-17')


def test_signal_raw_matches_embedded(banks, raw):
    indices = raw["indices"]
    for method in ("exact", "gauss", "levels"):
        assert raw[method].tobytes() == banks["SIG_8.npz"][method][..., indices].tobytes()
    assert raw["levels"].dtype == np.int8
    assert np.any(raw["levels"] > 9)
    k = list(indices).index(10557)
    with rt.arithmetic(160):
        assert any(arb(float(b))-arb(float(a)) > arb('.004')*arb(float(a))
                   for a,b in (raw[m][:, k] for m in ("exact", "gauss")))
        assert all(arb(float(b))-arb(float(a)) <= max(arb('.004')*arb(float(a)), arb('2e-10'))
                   for a,b in (raw[m][:, k] for m in ("exact", "gauss")))


def test_signal_dispatch_at_forty(monkeypatch, banks):
    # The final binary64 values can conceal the different summation route.
    # Record actual dot calls at 39.5 and 40, while checking their results.
    with rt.arithmetic(160):
        calc = gen._SignalThermal(banks["m1_N8.npz"], banks["commun.npz"])
        grouped = Grouped(calc)
        original = grouped.dot
        calls = []
        def record(*args):
            calls.append(1)
            return original(*args)
        monkeypatch.setattr(grouped, "dot", record)
        for db in (39.5, 40):
            calls.clear()
            result, J = gen._signal_point(calc, grouped, db)
            assert bool(calls) == (db >= 40)
            j = int(db*128 + 8192)
            assert J == banks["SIG_8.npz"]["levels"][j]
            for method in ("exact", "gauss"):
                assert np.asarray(result[method]).tobytes() == banks["SIG_8.npz"][method][:, j].tobytes()


def _parts(raw, groups):
    return [dict(indices=np.asarray(group, dtype=np.int64),
                 **{name: raw[name][..., group] for name in ("exact", "gauss", "levels")}) for group in groups]


def test_signal_partition_bytes(banks):
    indices = list(range(13300, 13340))
    left = gen.signal_points(banks["m1_N8.npz"], banks["commun.npz"], indices[:20])
    right = gen.signal_points(banks["m1_N8.npz"], banks["commun.npz"], indices[20:])
    alternate = gen.signal_points(banks["m1_N8.npz"], banks["commun.npz"], indices[::2]+indices[1::2])
    for part in (left, right, alternate):
        part["indices"] -= indices[0]
    first = gen.finish_signal([left, right], _size=40)
    # The second partition uses odd/even nodes, presented in reverse part order.
    alternating_parts = [dict(indices=alternate["indices"][section],
                              **{name: alternate[name][..., section]
                                 for name in ("exact", "gauss", "levels")})
                         for section in (slice(20,40), slice(0,20))]
    second = gen.finish_signal(alternating_parts, _size=40)
    for name in first:
        assert first[name].tobytes() == second[name].tobytes()


def test_finish_signal_coverage_and_tightening():
    data = dict(exact=np.array([[.8,.7,.75,.2],[.9,.8,.85,.4]]),
                gauss=np.array([[.8,.7,.75,.2],[.9,.8,.85,.4]]), levels=np.full(4, 9, dtype=np.int8))
    parts = _parts(data, [[2,0],[3,1]])
    result = gen.finish_signal(parts, _size=4)
    assert list(result) == ["exact", "gauss", "levels"]
    assert np.array_equal(result["exact"], [[.8,.75,.75,.2],[.9,.8,.8,.4]])
    for bad in ([parts[0]], parts + [parts[0]], _parts(data, [[0,0,1,2,3]])):
        with pytest.raises(ValueError):
            gen.finish_signal(bad, _size=4)
    data["exact"][0,0] = 1
    with pytest.raises(ArithmeticError):
        gen.finish_signal(_parts(data, [[0,1,2,3]]), _size=4)


def test_generators_are_pure_and_restore_context(monkeypatch, tmp_path, banks):
    monkeypatch.chdir(tmp_path)
    home_cache = Path.home()/".cache/certoutage"
    before_cache = sorted(home_cache.rglob("*")) if home_cache.exists() else None
    saved = ctx.prec, ctx.threads
    try:
        ctx.prec, ctx.threads = 83, 2
        gen.gain_arrays(8, power=10)
        assert (ctx.prec, ctx.threads) == (83, 2)
        gen.signal_points(banks["m1_N8.npz"], banks["commun.npz"], [13312])
        assert (ctx.prec, ctx.threads) == (83, 2)
        def fail(*args, **kwargs):
            raise ArithmeticError("Forced kernel failure")
        monkeypatch.setattr(gen, "L", fail)
        with pytest.raises(ArithmeticError):
            gen.gain_arrays(8, power=10)
        assert (ctx.prec, ctx.threads) == (83, 2)
        monkeypatch.setattr(gen, "_signal_point", fail)
        with pytest.raises(ArithmeticError):
            gen.signal_points(banks["m1_N8.npz"], banks["commun.npz"], [13312])
        assert (ctx.prec, ctx.threads) == (83, 2)
    finally:
        ctx.prec, ctx.threads = saved
    assert list(tmp_path.iterdir()) == []
    assert (sorted(home_cache.rglob("*")) if home_cache.exists() else None) == before_cache


def test_vendor_constructors_are_unreachable(monkeypatch, banks):
    def refuse(*args, **kwargs):
        raise AssertionError("File-reading thermal constructor reached")
    monkeypatch.setattr(thermal_backend.Thermal, "__init__", refuse)
    monkeypatch.setattr(nak_thermal.Thermal, "__init__", refuse)
    with rt.arithmetic(160):
        runtime = rt.Thermal(8, 1, False)
        assert runtime.N == 8 and set(runtime.levels) == set(range(9,14))
    gen.signal_points(banks["m1_N8.npz"], banks["commun.npz"], [0])


def _tool(name):
    if name == "generate_gain":
        pytest.importorskip("resource", reason="The CLI uses Unix peak RSS accounting")
    import importlib.util
    path = Path(__file__).resolve().parents[2]/"tools"/(name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_comparator_detects_one_ulp(tmp_path):
    import hashlib
    import json
    tool = _tool("compare_gain_banks")
    data = dict(N=np.array(8), B=np.array(96), exact_lo=np.array([0., .25]),
                exact_hi=np.array([0., .5]), gauss_lo=np.array([0., .2]), gauss_hi=np.array([0., .6]))
    archive, output = tmp_path/"archive", tmp_path/"output"
    (archive/"campaigns/t23").mkdir(parents=True)
    output.mkdir()
    ref = dict(file="banques/N8.npz", original_sha256="0"*64,
               arrays={k: dict(sha256=hashlib.sha256(a.tobytes()).hexdigest(), dtype=str(a.dtype), shape=list(a.shape))
                       for k,a in data.items()})
    (archive/"campaigns/t23/COMPRESSION_LOSSLESS.json").write_text(json.dumps([ref]))
    np.savez(output/"N8.npz", **data)
    assert tool.compare(archive, output)["ok"]
    data["exact_hi"][1] = np.nextafter(data["exact_hi"][1], np.inf)
    np.savez(output/"N8.npz", **data)
    result = tool.compare(archive, output)
    assert not result["ok"]
    assert [k for k,v in result["banks"]["N8.npz"]["arrays"].items() if v["status"] == "different"] == ["exact_hi"]


def test_generation_cli_metadata_and_empty_output(monkeypatch, tmp_path, reduced):
    import json
    import sys
    tool = _tool("generate_gain")
    monkeypatch.setattr(tool, "gain_arrays", lambda N: reduced[N])
    output = tmp_path/"output"
    monkeypatch.setattr(sys, "argv", ["generate_gain.py", "--N", "8", "--output", str(output)])
    tool.main()
    metadata = json.loads((output/"N8.json").read_text())
    assert metadata["peak_rss_bytes"] > 0 and metadata["seconds"] >= 0
    assert all(k in metadata for k in ("python", "python_flint", "numpy", "sha256", "arrays"))
    assert str(tmp_path) not in json.dumps(metadata)
    assert not {"host", "hostname", "user", "username", "path"} & metadata.keys()
    with np.load(output/"N8.npz") as saved:
        assert saved.files == list(reduced[8])
    with pytest.raises(SystemExit) as error:
        tool.main()
    assert error.value.code == 2


def test_generation_cli_merge(monkeypatch, tmp_path):
    import sys
    tool = _tool("generate_gain")
    size = 20481
    a = np.linspace(.9, .1, size)
    data = dict(exact=np.vstack((a,a+.01)), gauss=np.vstack((a,a+.02)), levels=np.full(size,9,dtype=np.int8))
    parts = _parts(data, [list(range(0,size,2)),list(range(1,size,2))])
    paths = [tmp_path/"even.npz", tmp_path/"odd.npz"]
    for path,part in zip(paths,parts):
        np.savez(path, N=np.array(8,dtype=np.int64), **part)
    output = tmp_path/"merged"
    monkeypatch.setattr(sys,"argv",["generate_gain.py","--N","8","--output",str(output),"--merge",*map(str,paths)])
    tool.main()
    with np.load(output/"SIG_8.npz") as actual:
        assert actual.files == list(data)
        for name in data:
            assert actual[name].tobytes() == data[name].tobytes()


@pytest.mark.parametrize("N", [8, 23, 64])
def test_gain_cdf_order(N):
    data = gen.gain_arrays(N, power=10)
    for method in ("exact", "gauss"):
        lo, hi = data[method+"_lo"], data[method+"_hi"]
        assert np.all(np.isfinite(lo)) and np.all(np.isfinite(hi))
        assert np.all((0 <= lo) & (lo <= hi) & (hi <= 1))
        assert np.all(np.diff(lo) >= 0) and np.all(np.diff(hi) >= 0)
        assert lo[0] == hi[0] == 0 and hi[-1] == 1


def _historical_levels(z, phi, J, kappa):
    left, right = np.abs(float(kappa)+z[:-1]), np.abs(float(kappa)+z[1:])
    ml = [(arb(float(x))/(1<<J)).lower() for x in np.minimum(phi[0,:-1],phi[0,1:])]
    mh = [(arb(float(x))/(1<<J)).upper() for x in np.maximum(phi[1,:-1],phi[1,1:])]
    return np.minimum(left,right), np.maximum(left,right), (ml,mh)


def _same_levels(actual, expected):
    for i in (0,1):
        assert actual[i].dtype == expected[i].dtype
        assert actual[i].tobytes() == expected[i].tobytes()
    for a,b in zip(actual[2], expected[2]):
        assert [(x.mid(),x.rad()) for x in a] == [(x.mid(),x.rad()) for x in b]


def test_thermal_default_preserves_bytes(banks):
    common = banks["commun.npz"]
    with rt.arithmetic(160):
        runtime = rt.Thermal(8,1,False)
        for J in range(9,14):
            step = 1 << (13-J)
            z,phi = common["z"][::step],common["phi"][:,::step]
            expected = _historical_levels(z,phi,J,Fraction(10))
            _same_levels(gen.thermal_levels(z,phi,J,Fraction(10)),expected)
            _same_levels(runtime.levels[J],expected)


@pytest.mark.parametrize("kappa", [Fraction(7,3),Fraction(5,2),Fraction(1,3)])
def test_thermal_cells_enclose_exact_extrema(banks,kappa):
    common = banks["commun.npz"]
    with rt.arithmetic(160):
        for J in (9,13):
            step=1 << (13-J)
            z,phi=common["z"][::step],common["phi"][:,::step]
            lo,hi,masses=gen.thermal_levels(z,phi,J,kappa)
            crossing=np.flatnonzero((z[:-1]<=-float(kappa)) & (z[1:]>=-float(kappa)))
            selected=range(len(lo)) if J==9 else sorted(set(range(0,len(lo),197)) | set(crossing))
            for i in selected:
                left,right=kappa+Fraction(float(z[i])), kappa+Fraction(float(z[i+1]))
                minimum=0 if left<=0<=right else min(abs(left),abs(right))
                maximum=max(abs(left),abs(right))
                assert Fraction(float(lo[i])) <= minimum <= maximum <= Fraction(float(hi[i]))
                if left<=0<=right:
                    assert lo[i] == 0
                    if left<0<right:
                        assert min(abs(float(kappa)+z[i]),abs(float(kappa)+z[i+1])) > 0
            old=_historical_levels(z,phi,J,kappa)
            for actual,expected in zip(masses,old[2]):
                assert [(x.mid(),x.rad()) for x in actual] == [(x.mid(),x.rad()) for x in expected]


@pytest.mark.parametrize("kappa", [Fraction(12),Fraction(25,2),Fraction(20)])
def test_thermal_outside_shift_preserves_bytes(banks,kappa):
    common=banks["commun.npz"]
    with rt.arithmetic(160):
        for J in range(9,14):
            step=1 << (13-J)
            z,phi=common["z"][::step],common["phi"][:,::step]
            _same_levels(gen.thermal_levels(z,phi,J,kappa),_historical_levels(z,phi,J,kappa))


def test_thermal_amplitude_default_bytes():
    with rt.arithmetic(160):
        for j in np.linspace(0,20480,23,dtype=int):
            db=(int(j)-8192)/128
            expected=thermal_backend.Thermal.amplitude(None,db,1)
            actual=gen._signal_amplitude(db,Fraction(10))
            assert np.asarray(actual).tobytes()==np.asarray(expected).tobytes()
        for kappa in (Fraction(0),Fraction(1,3),Fraction(7,3),Fraction(25,2)):
            lo,hi=gen._signal_amplitude(0,kappa)
            square=(1+kappa*kappa)*Fraction(80,3)
            assert Fraction(float(lo))**2 <= square <= Fraction(float(hi))**2


@pytest.mark.parametrize("kappa", [10,10.0,"10",True,Fraction(-1)])
def test_kappa_requires_exact_nonnegative_fraction(banks,kappa):
    common=banks["commun.npz"]
    with pytest.raises(ValueError,match="Fraction"):
        gen.thermal_levels(common["z"][::16],common["phi"][:,::16],9,kappa)
    with pytest.raises(ValueError,match="Fraction"):
        gen.signal_points(banks["m1_N8.npz"],common,[],kappa=kappa)


def test_absolute_rounding_keeps_exact_values_and_bounds():
    for q in (Fraction(0),Fraction(1,3),Fraction(7,3),Fraction(1,2**1100),Fraction(10)**400):
        lo,hi=gen._absolute_outward(q)
        assert Fraction(float(lo))<=q
        assert math.isinf(hi) or q<=Fraction(float(hi))
    assert gen._absolute_outward(Fraction(5,2))==(2.5,2.5)
