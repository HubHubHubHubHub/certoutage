"""Offline preparation plumbing; complete numerical generation is opt-in."""
from dataclasses import FrozenInstanceError, asdict
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
from time import perf_counter

from flint import ctx
import numpy as np
import pytest

import certoutage as co
from certoutage import _banks, _generate_gain as gen, _chernoff as ch, _prepare as prep
from certoutage import _runtime as rt


def forbidden(*args, **kwargs):
    raise AssertionError("Unexpected calculation, write or network access")


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv("CERTOUTAGE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    co.clear_cache()
    yield
    monkeypatch.undo()
    co.clear_cache()


def fake_gain(N, *, m=1, power=19, bits=160):
    assert bits == 160 and power == 19 and ctx.prec == 160 and ctx.threads == 1
    result = dict(N=np.array(N, dtype=np.int64), B=np.array(gen.gain_period(N), dtype=np.int64))
    if m != 1:
        result["m"] = np.array(m, dtype=np.int64)
    for method in ("exact", "gauss"):
        result[method + "_lo"] = np.zeros((1 << power) + 1)
        result[method + "_hi"] = np.ones((1 << power) + 1)
    return result


def fake_signal(gain, common, *, bits=160, kappa=Fraction(10)):
    assert kappa == Fraction(10) and bits == 160 and ctx.prec == 160 and ctx.threads == 1
    m = int(gain.get("m", 1))
    size = 20481 if m == 1 else 1025
    result = {method: np.array([np.zeros(size), np.ones(size)]) for method in ("exact", "gauss")}
    if m == 1:
        result["levels"] = np.full(size, 9, dtype=np.int8)
    else:
        result["units128"] = np.arange(-4096, 4097, 8, dtype=np.int64)
    return result


def fake_chernoff(N, *, stride=8, power=19, bits=160):
    assert stride == 8 and bits == 160 and power == 19
    return dict(N=np.array(N, dtype=np.int64), B=np.array(gen.gain_period(N), dtype=np.int64),
                stride=np.array(8, dtype=np.int64), chernoff_lo=np.zeros((1 << 19) + 1),
                chernoff_hi=np.ones((1 << 19) + 1))


def fake_sigc(cbank, common, *, bits=160, kappa=Fraction(10)):
    assert kappa == Fraction(10) and bits == 160 and ctx.prec == 160 and ctx.threads == 1
    return dict(chernoff=np.array([np.zeros(20481), np.ones(20481)]), levels=np.full(5121, 9, dtype=np.int8))


@pytest.fixture
def fast_generators(monkeypatch):
    monkeypatch.setattr(gen, "gain_arrays", fake_gain)
    monkeypatch.setattr(gen, "signal_arrays", fake_signal)
    monkeypatch.setattr(gen, "nakagami_signal_arrays", fake_signal)
    monkeypatch.setattr(ch, "chernoff_arrays", fake_chernoff)
    monkeypatch.setattr(gen, "chernoff_signal_arrays", fake_sigc)


def test_model_domain_and_pure_construction(monkeypatch):
    monkeypatch.setattr(_banks, "files", forbidden)
    monkeypatch.setattr(_banks, "cache_dir", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    for N in range(8, 65):
        assert co.Model(N=N).N == N
    for N in (7, 65, True, 8.0, "8"):
        with pytest.raises(ValueError, match=r"\[8, 64\].*prepare"):
            co.Model(N=N)


@pytest.mark.parametrize("m,gain", [(1, "exact"), (2, "exact"), (1, "chernoff")])
@pytest.mark.parametrize("query", ["outage", "floor", "required", "compare", "largest"])
def test_missing_banks_refuse_before_any_calculation(monkeypatch, m, gain, query):
    for module, names in ((gen, ("gain_arrays", "signal_arrays", "nakagami_signal_arrays", "chernoff_signal_arrays")),
                          (ch, ("chernoff_arrays",)), (rt, ("environment_arrays", "environment", "signal", "thermal"))):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    monkeypatch.setattr(prep, "prepare", forbidden)
    model = co.Model(N=21, m=m, lam="0.123")
    calls = dict(outage=lambda: co.outage_enclosure(model, 1, 0, gain=gain),
                 floor=lambda: co.floor(model, 1, gain=gain),
                 required=lambda: co.required_snr(model, 1, "0.002", gain=gain),
                 compare=lambda: co.compare_approximations(model, 1, "0.002"),
                 largest=lambda: co.largest_interferer_bound(model, 1))
    start = perf_counter()
    with pytest.raises(co.BankNotAvailable) as error:
        calls[query]()
    assert perf_counter() - start < 1
    requested_gain = "exact" if query in ("compare", "largest") else gain
    assert f'certoutage.prepare(Model(N=21, m={m}), gain="{requested_gain}")' in str(error.value)
    assert "SIG" in str(error.value) and "one CPU core" in str(error.value)
    assert not _banks.cache_dir().exists()


def test_dry_run_is_an_immutable_ordered_plan(monkeypatch):
    monkeypatch.setattr(gen, "gain_arrays", forbidden)
    monkeypatch.setattr(_banks, "_atomic_write", forbidden)
    plan = co.prepare(co.Model(N=21), gain="chernoff", dry_run=True)
    assert [r.logical for r in plan] == ["m1_N21.npz", "SIG_21.npz", "C_N21.npz", "SIG_C_21.npz"]
    assert all(r.origin == "missing" and r.sha256 is None and r.bytes is None for r in plan)
    assert [r.estimated_seconds for r in plan] == [(24., 24.), (370., 950.), (3., 11.), (130., 260.)]
    assert plan[0].stored_name and plan[1].stored_name is None
    with pytest.raises(FrozenInstanceError):
        plan[0].origin = "generated"
    assert not _banks.cache_dir().exists()


@pytest.mark.parametrize("m,gain", [(1, "exact"), (2, "eq3"), (3, "exact"), (1, "chernoff")])
def test_prepare_verified_idempotent_and_usable(fast_generators, monkeypatch, m, gain):
    model = co.Model(N=21, m=m)
    result = co.prepare(model, gain=gain)
    assert all(row.origin == "generated" and row.seconds > 0 for row in result)
    names = [row.logical for row in result]
    assert names[:2] == [f"m{m}_N21.npz", "SIG_21.npz" if m == 1 else f"SIG_m{m}_N21.npz"]
    for row in result:
        meta = prep._metadata(row.logical)
        assert (meta["sha256"], meta["bytes"], meta["name"]) == (row.sha256, row.bytes, row.stored_name)
        assert meta["schema"] == 1 and meta["generator"]["version"] == gen.GENERATION_VERSION
        assert meta["generator"]["code_sha256"] == prep._code_sha256()
        assert all(meta[k] for k in ("certoutage_version", "python_flint_version", "numpy_version"))
        arrays = _banks.arrays(row.logical)
        assert all(not array.flags.writeable for array in arrays.values())
        if meta["family"] in ("SIG", "SIGC"):
            p = meta["parameters"]
            assert p["thermal_ratio"] == "10"
            assert p["common_sha256"] == _banks.manifest()["commun.npz"]["sha256"]
            key, dependency = ("gain_sha256", names[0]) if meta["family"] == "SIG" else ("chernoff_sha256", "C_N21.npz")
            assert p[key] == prep._metadata(dependency)["sha256"]
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in (_banks.cache_dir() / "generated").iterdir()}
    for module, name in ((gen, "gain_arrays"), (gen, "signal_arrays"), (gen, "nakagami_signal_arrays"),
                         (gen, "chernoff_signal_arrays"), (ch, "chernoff_arrays")):
        monkeypatch.setattr(module, name, forbidden)
    repeated = co.prepare(model, gain=gain)
    assert all(row.origin == "cached" for row in repeated)
    assert {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in (_banks.cache_dir() / "generated").iterdir()} == before
    result = co.outage_enclosure(model, 1, 0, gain=gain)
    assert 0 <= result.lower <= result.upper <= 1
    assert any(name.startswith("SIG_") for name, _ in result.contract.banks)
    assert 0 <= co.largest_interferer_bound(model, 1).lower <= 1
    assert {p.parent for p in _banks.cache_dir().rglob("*") if p.is_file()} == {_banks.cache_dir() / "generated"}


@pytest.mark.parametrize("N,expected", [(8, ["SIG_C_8.npz"]), (12, ["C_N12.npz", "SIG_C_12.npz"])])
def test_embedded_inputs_take_priority(fast_generators, N, expected):
    rows = co.prepare(co.Model(N=N), gain="chernoff")
    assert [r.logical for r in rows if r.origin == "generated"] == expected
    meta = prep._metadata(f"SIG_C_{N}.npz")
    assert meta["parameters"]["chernoff_sha256"] == prep._metadata(f"C_N{N}.npz")["sha256"]
    if N == 8:
        assert meta["parameters"]["chernoff_sha256"] == _banks.manifest()["C_N8.npz"]["sha256"]


def test_embedded_prepare_never_consults_cache(monkeypatch):
    monkeypatch.setattr(_banks, "cache_dir", forbidden)
    monkeypatch.setattr(gen, "gain_arrays", forbidden)
    rows = co.prepare(co.Model(N=24))
    assert [r.logical for r in rows] == ["SIG_24.npz"]
    assert rows[0].origin == "embedded"


def test_thermal_identity_is_canonical_and_depends_on_inputs(fast_generators, monkeypatch, tmp_path):
    co.prepare(co.Model(N=21, m=2))
    def name(ratio):
        return _banks._generated_name(*prep._identity("SIG_m2_N21.npz", thermal_ratio=ratio))
    initial = name(Fraction(10))
    assert initial == name(Fraction(20, 2)) != name(Fraction(7, 3))
    metadata = prep._metadata
    def changed(logical):
        value = metadata(logical)
        return dict(value, sha256="f" * 64) if logical == "m2_N21.npz" else value
    monkeypatch.setattr(prep, "_metadata", changed)
    assert name(Fraction(10)) != initial
    monkeypatch.setattr(prep, "_metadata", metadata)
    copied = tmp_path / "second"
    import shutil
    shutil.copytree(_banks.cache_dir(), copied)
    monkeypatch.setenv("CERTOUTAGE_CACHE_DIR", str(copied))
    assert name(Fraction(10)) == initial


def test_certifying_source_digest_is_pinned():
    assert gen.GENERATION_VERSION == "1"
    assert prep._code_sha256() == "ac37fc23817e3a505eac30c8a564e5401df6bcf4043cb74fbcd8fe620c080b3d"


def _rewrite(row, transform):
    bank = _banks.cache_dir() / "generated" / row.stored_name
    data = {key: value.copy() for key, value in _banks.arrays(row.logical).items()}
    transform(data)
    content = _banks._serialize_arrays(data)
    bank.write_bytes(content)
    descriptor = bank.with_suffix(".json")
    meta = json.loads(descriptor.read_text())
    meta.update(sha256=sha256(content).hexdigest(), bytes=len(content))
    descriptor.write_text(json.dumps(meta))


@pytest.mark.parametrize("damage", ["bytes", "shape", "key", "dtype", "bounds", "descriptor"])
def test_corrupt_signal_is_never_regenerated(fast_generators, monkeypatch, damage):
    model = co.Model(N=21, m=2)
    row = co.prepare(model)[-1]
    path = _banks.cache_dir() / "generated" / row.stored_name
    if damage == "bytes":
        path.write_bytes(b"broken")
    elif damage == "descriptor":
        path.with_suffix(".json").unlink()
    else:
        changes = dict(shape=lambda d: d.update(exact=d["exact"][:, :-1]),
                       key=lambda d: d.pop("gauss"), dtype=lambda d: d.update(exact=d["exact"].astype(np.float32)),
                       bounds=lambda d: d["exact"].__setitem__((0, 0), 2))
        _rewrite(row, changes[damage])
    monkeypatch.setattr(gen, "nakagami_signal_arrays", forbidden)
    co.clear_cache()
    with pytest.raises(co.BankNotAvailable if damage == "descriptor" else co.IntegrityError):
        co.outage_enclosure(model, 1, 0)


@pytest.mark.parametrize("key", ["N", "m", "B"])
def test_gain_identity_scalars_are_checked(fast_generators, key):
    row = co.prepare(co.Model(N=21, m=2))[0]
    _rewrite(row, lambda d: d.update({key: np.array(22, dtype=np.int64)}))
    with pytest.raises(co.IntegrityError, match="structure"):
        _banks.arrays(row.logical)


def test_lost_input_makes_signal_unready_then_reuses_it(fast_generators, monkeypatch):
    model = co.Model(N=21, m=2)
    rows = co.prepare(model)
    (_banks.cache_dir() / "generated" / rows[0].stored_name).unlink()
    co.clear_cache()
    with pytest.raises(co.BankNotAvailable, match="SIG_m2_N21"):
        co.floor(model, 1)
    monkeypatch.setattr(gen, "nakagami_signal_arrays", forbidden)
    restored = co.prepare(model)
    assert [(r.logical, r.origin) for r in restored] == [(rows[0].logical, "generated"), (rows[1].logical, "cached")]
    assert restored[1].stored_name == rows[1].stored_name


def test_routing_is_independent_of_cached_gain(fast_generators, monkeypatch):
    model = co.Model(N=21, m=2, lam=0)
    co.prepare(model)
    monkeypatch.setattr(rt, "thermal", forbidden)
    assert co.outage_enclosure(model, 1, 0).upper == 1
    assert not prep._direct(model)
    assert prep._direct(co.Model(N=8, lam=0))


def test_embedded_direct_answers_ignore_generated_store(fast_generators):
    model = co.Model(N=8, lam=0)
    before = co.outage_enclosure(model, 1, 20)
    assert (before.lower.hex(), before.upper.hex()) == ("0x1.0a75f368179c6p-32", "0x1.0c3f5223f1d80p-32")
    co.prepare(co.Model(N=21, m=2))
    co.clear_cache()
    after = co.outage_enclosure(model, 1, 20)
    assert (before.lower.hex(), before.upper.hex()) == (after.lower.hex(), after.upper.hex())
    assert before.contract == after.contract


@pytest.mark.parametrize("fail", [False, True])
def test_arithmetic_context_restored(fast_generators, monkeypatch, fail):
    prec, threads = ctx.prec, ctx.threads
    try:
        ctx.prec, ctx.threads = 91, 2
        if fail:
            monkeypatch.setattr(gen, "gain_arrays", forbidden)
            with pytest.raises(AssertionError):
                co.prepare(co.Model(N=21, m=2))
        else:
            co.prepare(co.Model(N=21, m=2))
        assert (ctx.prec, ctx.threads) == (91, 2)
    finally:
        ctx.prec, ctx.threads = prec, threads


def test_validation_matches_scope():
    for m in (2, 3):
        with pytest.raises(ValueError) as scope:
            gen.generation_scope("chernoff", m, 21)
        for call in (lambda: co.prepare(co.Model(N=21, m=m), gain="chernoff"),
                     lambda: co.floor(co.Model(N=21, m=m), 1, gain="chernoff")):
            with pytest.raises(ValueError) as error:
                call()
            assert str(error.value) == str(scope.value)
    for N in range(8, 65):
        assert co.prepare(co.Model(N=N), gain="chernoff", dry_run=True)


@pytest.mark.skipif(os.environ.get("CERTOUTAGE_SLOW_TESTS") != "1", reason="explicit slow generation control")
def test_forced_generation_reproduces_embedded_bank_and_answers():
    model = co.Model(N=8, m=3, lam=0)
    logical = "SIG_m3_N8.npz"
    expected = _banks.arrays(logical)
    before = [co.outage_enclosure(model, user, db) for user in (1, 2) for db in (-10, 0, 10, 20, 30)]
    with prep._force_generation("m3_N8.npz", logical):
        rows = co.prepare(model)
        assert [r.origin for r in rows[:2]] == ["generated", "generated"]
        actual = _banks.arrays(logical)
        assert expected.keys() == actual.keys()
        for key in expected:
            assert expected[key].dtype == actual[key].dtype
            assert expected[key].shape == actual[key].shape
            assert expected[key].tobytes() == actual[key].tobytes()
        after = [co.outage_enclosure(model, user, db) for user in (1, 2) for db in (-10, 0, 10, 20, 30)]
    assert [(r.lower.hex(), r.upper.hex()) for r in before] == [(r.lower.hex(), r.upper.hex()) for r in after]


@pytest.mark.parametrize("m,gain", [(1, "exact"), (2, "eq3"), (1, "chernoff")])
def test_generated_contract_provenance(fast_generators, monkeypatch, m, gain):
    rows = co.prepare(co.Model(N=21, m=m), gain=gain)
    # A generated PPP environment must not hide useful-gain provenance.
    monkeypatch.setattr(rt, "environment_arrays", lambda *args: _banks.arrays("PPP_l0p1_e4.npz"))
    model = co.Model(N=21, m=m, lam="0.123")
    point = co.outage_enclosure(model, 1, 0, gain=gain)
    bound = co.largest_interferer_bound(model, 1)
    for result in (point, bound):
        assert result.contract.source == "generated-banks"
        local = [row for row in rows if row.stored_name in dict(result.contract.banks)]
        assert local and all((row.stored_name, row.sha256) in result.contract.banks for row in local)
        for row in local:
            meta = prep._metadata(row.logical)
            note = next(n for n in result.contract.notes if row.logical in n)
            assert f"N=21, m={m}, thermal ratio 10, 160 bits, GENERATION_VERSION=1" in note
            assert all(meta[k] in note for k in ("certoutage_version", "python_flint_version", "numpy_version"))
        assert "thermal_ratio" not in dict(result.contract.parameters)
    if gain == "chernoff":
        assert any("machine" in n and "noncertifying" in n for n in point.contract.notes)


def test_new_size_example_with_fast_generators(fast_generators, monkeypatch, capsys):
    import runpy
    import sys
    monkeypatch.setattr(rt, "environment_arrays", lambda *args: _banks.arrays("PPP_l0p1_e4.npz"))
    monkeypatch.setattr(sys, "argv", ["new_size.py", "--json"])
    runpy.run_path(str(Path(__file__).resolve().parents[2] / "examples/new_size.py"), run_name="__main__")
    result = json.loads(capsys.readouterr().out)
    assert not result["plan_only"] and result["target"] == "0.002"
    assert [r["origin"] for r in result["prepared"]] == ["generated", "generated"]
    assert len(result["cases"]) == 2
    for case in result["cases"]:
        assert case["model"]["N"] == 21 and case["model"]["m"] == 2
        assert case["decision"]["evaluation_contract"]["source"] == "generated-banks"
        if case["model"]["convention"] == "C-TX":
            assert case["floor"]["contract"]["source"] == "generated-banks"
            assert case["largest_interferer"]["contract"]["source"] == "generated-banks"


def test_identity_reads_only_input_metadata(fast_generators, monkeypatch):
    co.prepare(co.Model(N=21, m=2))
    expected = prep._stored_name("SIG_m2_N21.npz")
    read = Path.read_bytes
    def metadata_only(path):
        if path.suffix == ".npz":
            raise AssertionError("Identity read an input bank instead of its descriptor")
        return read(path)
    monkeypatch.setattr(Path, "read_bytes", metadata_only)
    monkeypatch.setattr(_banks, "arrays", forbidden)
    assert prep._stored_name("SIG_m2_N21.npz") == expected


@pytest.mark.parametrize("logical,change", [
    ("SIG_21.npz", lambda d: d.update(levels=np.zeros(20481, dtype=np.int8))),
    ("SIG_C_21.npz", lambda d: d.update(levels=np.ones(20481, dtype=np.int8))),
    ("SIG_C_21.npz", lambda d: d.update(chernoff=d["chernoff"][:, ::2])),
    ("C_N21.npz", lambda d: d.update(stride=np.array(4, dtype=np.int64))),
])
def test_all_generated_families_check_structure(fast_generators, logical, change):
    rows = co.prepare(co.Model(N=21), gain="chernoff")
    row = next(r for r in rows if r.logical == logical)
    _rewrite(row, change)
    with pytest.raises(co.IntegrityError, match="structure"):
        _banks.arrays(logical)


def test_cached_prepare_checks_integrity_without_recomputation(fast_generators, monkeypatch):
    model = co.Model(N=21, m=2)
    row = co.prepare(model)[-1]
    (_banks.cache_dir() / "generated" / row.stored_name).write_bytes(b"truncated")
    monkeypatch.setattr(gen, "nakagami_signal_arrays", forbidden)
    with pytest.raises(co.IntegrityError, match="SHA-256"):
        co.prepare(model)


def test_malformed_thermal_identity_is_an_integrity_error(fast_generators):
    row = co.prepare(co.Model(N=21, m=2))[-1]
    meta = prep._metadata(row.logical)
    parameters = dict(meta["parameters"], thermal_ratio="1/0")
    name = _banks._store_generated(meta["family"], parameters, meta["generator"], _banks.arrays(row.logical))
    with pytest.raises(co.IntegrityError, match="structure"):
        _banks.arrays(name)
