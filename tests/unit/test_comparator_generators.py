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


from certoutage import _chernoff as ch
from certoutage._vendor.nak_grouped import Grouped


@pytest.mark.parametrize('N', [8, 64])
def test_chernoff_values_and_signs(banks, N):
    reference = banks[f'C_N{N}.npz']
    B, M = int(reference['B']), len(reference['chernoff_lo'])-1
    # Common stride-eight nodes: tiny a, the t=2 series, near the mean,
    # the endpoints, and the constant-one regime are all included.
    end = int(N*math.pi/4*M/B)//8
    nodes = sorted(set([0,1,2, end, end+1, M//8] + np.linspace(3,end-1,26,dtype=int).tolist()))
    near_two = False
    with rt.arithmetic(160):
        for k in nodes:
            j = 8*k
            a = arb(j)*B/M
            value, root = ch.chernoff_value(a, N)
            ref = arb(float(reference['chernoff_lo'][j])).union(arb(float(reference['chernoff_hi'][j])))
            assert value.overlaps(ref)
            if root:
                ml,mh=ch.moments(root['s_lower']),ch.moments(root['s_upper'])
                assert ml[1]/ml[0]>a/N and mh[1]/mh[0]<a/N
                near_two |= abs(root['s_lower']-2)<.8
        assert near_two
        for a in (arb('0.01'),N*arb('.4'),N*arb('.7')):
            expected,_=ch.chernoff_value(a,N)
            try:
                result,root=ch.chernoff_value(a,N,_guess=lambda *args:0.)
            except ArithmeticError:
                continue
            assert result.overlaps(expected)
            assert root is not None
            assert ch.moments(root['s_lower'])[1]/ch.moments(root['s_lower'])[0]>a/N
            assert ch.moments(root['s_upper'])[1]/ch.moments(root['s_upper'])[0]<a/N


@pytest.mark.parametrize('N',[9,21,63])
def test_chernoff_new_sizes(N):
    with rt.arithmetic(160):
        for a in [0]+[N*arb(j)/12 for j in range(1,11)]:
            value,_=ch.chernoff_value(a,N)
            assert value.is_finite() and value>=0 and value<=1


def test_chernoff_mean_guard(monkeypatch):
    # An exact stand-in for the mean tests equality, not merely a nearby float.
    # The optimizer must never run at or above this boundary.
    monkeypatch.setattr(ch,'mu',lambda m:arb(1))
    def refuse(*args):raise AssertionError('Root search reached the mean')
    with rt.arithmetic(160):
        assert ch.chernoff_value(8,8,_guess=refuse)==(arb(1),None)
        assert ch.chernoff_value(9,8,_guess=refuse)==(arb(1),None)
        assert ch.chernoff_value(0,8,_guess=refuse)==(arb(0),None)


@pytest.fixture(scope='module')
def chernoff_full():
    # Measured below ten seconds for N=8 on the local reference machine.
    return ch.chernoff_arrays(8)


def test_chernoff_full_bank_overlap(banks, chernoff_full):
    actual,ref=chernoff_full,banks['C_N8.npz']
    assert list(actual)==['chernoff_lo','chernoff_hi','B','N','stride']
    assert actual.diagnostics['roots']==4289  # historical C_N8.json
    assert np.all(np.maximum(actual['chernoff_lo'],ref['chernoff_lo'])<=
                  np.minimum(actual['chernoff_hi'],ref['chernoff_hi']))
    for name in ('chernoff_lo','chernoff_hi'):
        a,b=actual[name],ref[name];mask=(a>1e-300)&(b>1e-300)
        assert np.max(np.abs(a[mask]-b[mask])/b[mask])<=1e-8


def test_chernoff_signal_always_grouped(banks, monkeypatch):
    calls=[]
    original=Grouped.dot
    def record(self,*args):
        calls.append(1)
        return original(self,*args)
    monkeypatch.setattr(Grouped,'dot',record)
    indices=[0,1800,2048,2300,3328,5120]
    raw=gen.chernoff_signal_points(banks['C_N64.npz'],banks['commun.npz'],indices)
    assert len(calls)>=2*len(indices)
    assert raw['chernoff'].shape==(2,len(indices))
    assert np.all(raw['chernoff'][0]<=raw['chernoff'][1])
    assert np.all((9<=raw['levels'])&(raw['levels']<=13))


def test_chernoff_finish_envelope_and_guards():
    raw=dict(chernoff=np.array([[.8,.7,.75,.2],[.9,.8,.85,.4]]),levels=np.full(4,9,dtype=np.int8))
    parts=_parts(raw,[[2,0],[3,1]],methods=('chernoff',))
    result=gen.chernoff_finish_signal(parts,_size=4)
    assert list(result)==['chernoff','levels']
    # Coarse lower=[.8,.75,.75,.2], upper=[.9,.8,.8,.4].
    assert result['chernoff'][0].tolist()==[.8,.75,.75,.75,.75,.75,.75,.75,.75,.2,.2,.2,.2]
    assert result['chernoff'][1].tolist()==[.9,.9,.9,.9,.8,.8,.8,.8,.8,.8,.8,.8,.4]
    assert np.array_equal(result['levels'],[9]*4)
    for bad in ([parts[0]],parts+[parts[0]],_parts(raw,[[0,0,1,2,3]],('chernoff',))):
        with pytest.raises(ValueError):gen.chernoff_finish_signal(bad,_size=4)
    raw['chernoff'][0,0]=1
    with pytest.raises(ArithmeticError):gen.chernoff_finish_signal(_parts(raw,[[0,1,2,3]],('chernoff',)),_size=4)


def _tool(name):
    import importlib.util
    spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[2]/'tools'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_chernoff_comparator_self_and_one_ulp(tmp_path,banks):
    tool=_tool('compare_gain_banks')
    source=tmp_path/'C_N8.npz';changed=tmp_path/'changed.npz'
    data={k:v.copy() for k,v in banks['C_N8.npz'].items()}
    np.savez(source,**data)
    assert tool.compare_chernoff_bank(source,source,mode='bytes')['ok']
    assert tool.compare_chernoff_bank(source,source,mode='overlap')['ok']
    data['chernoff_hi'][50000]=np.nextafter(data['chernoff_hi'][50000],np.inf)
    np.savez(changed,**data)
    assert not tool.compare_chernoff_bank(changed,source,mode='bytes')['ok']
    # A degenerate interval shifted by one ulp is disjoint; a general interval
    # shifted by one ulp may still overlap and must not be rejected for that.
    data=dict(chernoff=np.array([[.25],[.25]]),levels=np.array([9],dtype=np.int8))
    np.savez(source,**data)
    data['chernoff']=np.nextafter(data['chernoff'],np.inf);np.savez(changed,**data)
    assert not tool.compare_chernoff_bank(changed,source,mode='overlap')['ok']


def test_chernoff_contains_known_optimum():
    with rt.arithmetic(256):
        # At t=2, L=1/3 and M1/L=2/5 (the independent density moments).
        # Thus a=2N/5 has its exact minimizer at 2; no root solver is needed.
        a=arb(16)/5
        exact=(2*a).exp()/arb(3)**8
        value,root=ch.chernoff_value(a,8,_guess=lambda *args:2.)
        assert root['s_lower']<2<root['s_upper']
        assert value.contains(exact)


def test_comparator_entries_pure_and_restore_context(monkeypatch,tmp_path,banks):
    monkeypatch.chdir(tmp_path)
    cache=Path.home()/'.cache/certoutage'
    before=sorted(cache.rglob('*')) if cache.exists() else None
    saved=ctx.prec,ctx.threads
    def fail(*args,**kwargs):raise ArithmeticError('Forced comparator failure')
    try:
        ctx.prec,ctx.threads=83,2
        for m in (2,3):
            gen.gain_arrays(8,m=m,power=10)
            assert (ctx.prec,ctx.threads)==(83,2)
        ch.chernoff_arrays(9,power=10)
        assert (ctx.prec,ctx.threads)==(83,2)
        gen.nakagami_signal_points(banks['m2_N8.npz'],banks['commun.npz'],[640])
        assert (ctx.prec,ctx.threads)==(83,2)
        gen.chernoff_signal_points(banks['C_N64.npz'],banks['commun.npz'],[2048])
        assert (ctx.prec,ctx.threads)==(83,2)
        with pytest.raises(ArithmeticError):ch.chernoff_arrays(8,power=10,_guess=fail)
        assert (ctx.prec,ctx.threads)==(83,2)
        monkeypatch.setattr(nak,'L',fail)
        with pytest.raises(ArithmeticError):gen.gain_arrays(8,m=2,power=10)
        assert (ctx.prec,ctx.threads)==(83,2)
        monkeypatch.setattr(gen,'_grouped_signal_point',fail)
        for fun,bank in ((gen.nakagami_signal_points,banks['m2_N8.npz']),
                         (gen.chernoff_signal_points,banks['C_N64.npz'])):
            with pytest.raises(ArithmeticError):fun(bank,banks['commun.npz'],[0])
            assert (ctx.prec,ctx.threads)==(83,2)
    finally:
        ctx.prec,ctx.threads=saved
    assert list(tmp_path.iterdir())==[]
    assert (sorted(cache.rglob('*')) if cache.exists() else None)==before


def test_generation_scope_cartesian():
    import itertools
    gains=('exact','eq3','chernoff','gamma','gg','x')
    ms=(0,1,2,3,4,2.5,True)
    ns=(7,8,21,64,65,True,8.0)
    for gain,m,N in itertools.product(gains,ms,ns):
        accepted=(type(m) is int and m in (1,2,3) and type(N) is int and 8<=N<=64
                  and gain in ('exact','eq3','chernoff') and (gain!='chernoff' or m==1))
        if not accepted:
            with pytest.raises(ValueError):gen.generation_scope(gain,m,N)
            if type(m) is not int or m not in (1,2,3):
                with pytest.raises(ValueError):gen.gain_arrays(8,m=m,power=10)
            if type(N) is not int or not 8<=N<=64:
                with pytest.raises(ValueError):gen.gain_arrays(N,power=10)
                with pytest.raises(ValueError):ch.chernoff_arrays(N,power=10)
                with pytest.raises(ValueError):ch.chernoff_value(0,N)
            continue
        scope=gen.generation_scope(gain,m,N)
        names={b['name'] for b in scope['banks']}
        expected={f'm{m}_N{N}.npz', f'SIG_{N}.npz' if m==1 else f'SIG_m{m}_N{N}.npz'}
        if gain=='chernoff':expected|={f'C_N{N}.npz',f'SIG_C_{N}.npz'}
        assert names==expected
        assert scope['shared_inputs']==['commun.npz']
        available=set(scope['shared_inputs'])
        for bank in scope['banks']:
            assert set(bank['requires'].values())<=available
            available.add(bank['name'])
        for path in scope['paths'].values():assert set(path)<=names
        assert scope['paths']['largest_interferer']==[f'SIG_{N}.npz' if m==1 else f'SIG_m{m}_N{N}.npz']


@pytest.mark.parametrize('gain,m,N',[('exact',1,9),('eq3',2,21),('exact',3,63),('chernoff',1,21)])
def test_scope_named_functions_accept(gain,m,N,banks,monkeypatch):
    import importlib
    # Exercise each named array entry with a reduced DFT and an explicit
    # one-node private merge size. The thermal computation itself is real.
    original_nak=gen.nakagami_signal_points
    original_c=gen.chernoff_signal_points
    original_s=gen.signal_points
    original_nf,original_cf,original_sf=gen.nakagami_finish_signal,gen.chernoff_finish_signal,gen.finish_signal
    monkeypatch.setattr(gen,'nakagami_signal_points',lambda g,c,i,**kw:original_nak(g,c,[0],**kw))
    monkeypatch.setattr(gen,'chernoff_signal_points',lambda g,c,i,**kw:original_c(g,c,[0],**kw))
    monkeypatch.setattr(gen,'signal_points',lambda g,c,i,**kw:original_s(g,c,[0],**kw))
    monkeypatch.setattr(gen,'nakagami_finish_signal',lambda p:original_nf(p,_size=1))
    monkeypatch.setattr(gen,'chernoff_finish_signal',lambda p:original_cf(p,_size=1))
    monkeypatch.setattr(gen,'finish_signal',lambda p:original_sf(p,_size=1))
    arrays={'commun.npz':banks['commun.npz']}
    for bank in gen.generation_scope(gain,m,N)['banks']:
        module,name=bank['function'].rsplit('.',1)
        function=getattr(importlib.import_module(module),name)
        kw=dict(bank['parameters'],**{key:arrays[value] for key,value in bank['requires'].items()})
        if not bank['requires']:kw['power']=10
        arrays[bank['name']]=function(**kw)
        assert arrays[bank['name']]


def test_rayleigh_reduced_historical_digest():
    # Historical T20 t4_backend.worker, with only M changed to 2**12.
    expected = {'B': 'a3fd08764e225228ee3e534d14ba14b56418d9f2c40c4b529cc9df6acafaff13',
     'N': '6cc16abd70eefb90dc0ba0d14fb088630873b2c6ad943f7442356735984c35a3',
     'exact_hi': 'e3c14f19a822cc02ac526112e8f2ad9b6726d65e537657da800008de43a6c327',
     'exact_lo': '419a552fc7df6eac3f270afae95f144efd5e593483b33592edf4889eda3dd0ed',
     'gauss_hi': '9b3ee53540fa233a13ad28559236b091ec6bb19067481a80c01ef64ecced437f',
     'gauss_lo': '0d968556703d30a5ccbcc921dd44ffdcf25f8f47f05f8a13abc920565127eb78'}
    actual = gen.gain_arrays(8, power=12)
    assert {k: sha256(v.tobytes()).hexdigest() for k, v in actual.items()} == expected


def test_nakagami_signal_container_matches_archive(banks,tmp_path):
    import json
    tool=_tool('compare_gain_banks')
    ref=banks['SIG_m2_N8.npz'];size=len(ref['units128'])
    part=dict(indices=np.arange(size,dtype=np.int64),exact=ref['exact'],gauss=ref['gauss'],
              levels=np.full(size,9,dtype=np.int8))
    result=gen.nakagami_finish_signal([part])
    assert result['exact'].flags.f_contiguous and result['gauss'].flags.f_contiguous
    output=tmp_path/'output';output.mkdir()
    filename='SIG_m2_N8.npz'
    np.savez_compressed(output/filename,**result)
    # Serialize the archived arrays independently with this platform's zlib.
    # Raw NPY layout must agree even when the DEFLATE stream changes by platform.
    reference_file=tmp_path/'reference.npz'
    np.savez_compressed(reference_file,**ref)
    reference_bytes=reference_file.read_bytes()
    assert (output/filename).read_bytes()==reference_bytes
    archive=tmp_path/'archive';(archive/'campaigns/t20').mkdir(parents=True)
    # Accept either authenticated archive container, never just matching values.
    # Fortran layout is part of the serialized NPY payload.
    entry=dict(file='banques/'+filename,
               original_sha256='e075d80c62227a434e86a56ba5f3b7af0597573e6957245f02f51df4aaadf57b',
               compressed_sha256=sha256(reference_bytes).hexdigest(),
               arrays={k:dict(dtype=str(v.dtype),shape=list(v.shape),sha256=sha256(v.tobytes()).hexdigest()) for k,v in ref.items()})
    (archive/'campaigns/t20/COMPRESSION_LOSSLESS.json').write_text(json.dumps([entry]))
    assert tool.compare(archive,output,m=2)['ok']
    # Exercise original-container acceptance separately, using the independently
    # written reference above as the original in this synthetic manifest.
    entry['original_sha256']=sha256(reference_bytes).hexdigest()
    entry['compressed_sha256']='0'*64
    (archive/'campaigns/t20/COMPRESSION_LOSSLESS.json').write_text(json.dumps([entry]))
    assert tool.compare(archive,output,m=2)['ok']
    result['exact'][1,512]=np.nextafter(result['exact'][1,512],np.inf)
    np.savez_compressed(output/filename,**result)
    assert not tool.compare(archive,output,m=2)['ok']
