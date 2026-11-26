"""Direct tests for guarantees of docs/GUARANTEES.md that had no test of their own (S02, 26 November 2026)."""
import ast
from dataclasses import replace
from decimal import Inexact, Rounded, localcontext
from io import BytesIO
import json
import math
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

from flint import ctx
import numpy as np
import pytest

import certoutage
from certoutage import (Model, Numerics, Enclosure, IntegrityError, ThresholdDifference, clear_cache,
                        compare_approximations, floor, largest_interferer_bound, outage_enclosure, required_snr,
                        threshold_difference)
from certoutage import _banks, _runtime

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(certoutage.__file__).resolve().parent


def test_object_arrays_are_never_unpickled(monkeypatch):
    buffer = BytesIO()
    np.savez(buffer, a=np.array([{"payload": 1}], dtype=object))
    monkeypatch.setattr(_banks, "verified_bytes", lambda name: buffer.getvalue())
    with pytest.raises(ValueError, match="allow_pickle"):
        _banks.arrays("any.npz")


def test_loaded_bank_arrays_are_read_only():
    arrays = _banks.arrays("SIG_24.npz")
    assert arrays and all(not a.flags.writeable for a in arrays.values())
    with pytest.raises(ValueError):
        arrays["exact"][0, 0] = 0.0


def test_banks_are_not_read_again_until_clear_cache(monkeypatch):
    clear_cache()
    first = outage_enclosure(Model(), 1, 0).as_dict()
    reads = []
    original = _banks.verified_bytes
    monkeypatch.setattr(_banks, "verified_bytes", lambda name: reads.append(name) or original(name))
    assert outage_enclosure(Model(), 1, 0).as_dict() == first
    assert reads == []
    clear_cache()
    assert outage_enclosure(Model(), 1, 0).as_dict() == first
    assert reads, "clear_cache() must force the banks to be read and verified again"
    clear_cache()


def _query_everything():
    outage_enclosure(Model(), 1, 0)
    floor(Model(N=20, lam=1), 2)
    outage_enclosure(Model(lam="0.2", eta=3), 1, 10, numerics=Numerics(ppp_dft_power=12))
    outage_enclosure(Model(N=8, lam=0), 1, 20, gain="eq3")
    required_snr(Model(), 1, "1e-4")
    compare_approximations(Model(), 1, "1e-5")
    largest_interferer_bound(Model(), 1)
    largest_interferer_bound(Model(N=20, lam=1), 1)


def test_queries_make_no_network_access(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted")

    clear_cache()
    for name in ("socket", "create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, refuse)
    _query_everything()
    clear_cache()


def test_queries_write_no_file(monkeypatch, tmp_path):
    import builtins
    original_open = builtins.open
    attempts = []

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "wax+"):
            attempts.append(str(file))
            raise AssertionError(f"write attempted: {file}")
        return original_open(file, mode, *args, **kwargs)

    def refuse(*args, **kwargs):
        raise AssertionError("write attempted")

    clear_cache()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(builtins, "open", guarded_open)
    for name in ("save", "savez", "savez_compressed"):
        monkeypatch.setattr(np, name, refuse)
    monkeypatch.setattr(Path, "write_bytes", refuse)
    monkeypatch.setattr(Path, "write_text", refuse)
    _query_everything()
    monkeypatch.undo()
    assert attempts == [] and list(tmp_path.iterdir()) == []
    clear_cache()


def test_enclosures_are_valid_probability_intervals():
    contract = floor(Model(), 1).contract
    for lower, upper in [(0.5, 0.4), (-0.1, 0.2), (0.2, 1.1), (math.nan, 0.5), (0.1, math.inf)]:
        with pytest.raises(ArithmeticError, match="invalid probability enclosure"):
            Enclosure(lower, upper, contract)


def test_contract_records_the_verified_digests_of_the_banks_read():
    contract = outage_enclosure(Model(), 1, 0).contract
    assert contract.banks
    assert all(digest == _banks.manifest()[name]["sha256"] for name, digest in contract.banks)
    assert floor(Model(convention="C-INR"), 2).contract.source == "analytic"


def test_display_of_threshold_differences_ignores_decimal_traps():
    with localcontext() as context:
        context.traps[Inexact] = context.traps[Rounded] = True
        assert ThresholdDifference(1 / 3, 2 / 3).format() == "[0.3333, 0.6667]"
        assert ThresholdDifference(-1 / 128, 1 / 128).format(2) == "[-0.01, 0.01]"


@pytest.mark.parametrize("model", [Model(convention="C-INR", lam="0.1"), Model(convention="C-INR", lam=0, m=2),
                                   Model(convention="C-INR", lam=0, eta=3)])
def test_threshold_difference_refuses_other_physical_parameters(model):
    first = required_snr(Model(convention="C-INR", lam=0), 1, "1e-5")
    second = required_snr(model, 1, "1e-5")
    assert first.status == second.status == "feasible"
    with pytest.raises(ValueError, match="same parameter"):
        threshold_difference(first, second)


def test_threshold_difference_refuses_missing_target_or_parameters():
    first = required_snr(Model(convention="C-INR", lam=0), 1, "1e-5")
    with pytest.raises(ValueError):
        threshold_difference(first, replace(first, target=None))
    stripped = replace(first, evaluation_contract=replace(first.contract, parameters=()))
    with pytest.raises(ValueError, match="missing"):
        threshold_difference(first, stripped)


@pytest.mark.parametrize("kwargs", [dict(lam="inf"), dict(lam=math.inf), dict(R0=math.inf), dict(eta="nan")])
def test_infinite_or_nan_parameters_are_rejected(kwargs):
    with pytest.raises(ValueError):
        Model(**kwargs)


@pytest.mark.parametrize("snr", [-1001, True, "inf", -math.inf])
def test_out_of_range_or_non_numeric_snr_is_rejected(snr):
    with pytest.raises(ValueError):
        outage_enclosure(Model(), 1, snr)


@pytest.mark.parametrize("kwargs", [dict(precision_bits=1025), dict(precision_bits=True),
                                    dict(ppp_dft_power=21), dict(ppp_dft_power=12.0)])
def test_numerics_upper_bounds_and_types(kwargs):
    with pytest.raises(ValueError):
        Numerics(**kwargs)


def test_arb_context_is_restored_after_an_exception(monkeypatch):
    seen = []

    def failing(name):
        seen.append(ctx.prec)
        raise IntegrityError("injected failure")

    old = ctx.prec, ctx.threads
    clear_cache()
    monkeypatch.setattr(_banks, "verified_bytes", failing)
    try:
        ctx.prec, ctx.threads = 80, 3
        with pytest.raises(IntegrityError, match="injected"):
            outage_enclosure(Model(), 1, 0, numerics=Numerics(precision_bits=192))
        # The failure happened inside the managed context, and the caller's context came back.
        assert seen and seen[0] == 192
        assert (ctx.prec, ctx.threads) == (80, 3)
    finally:
        ctx.prec, ctx.threads = old
        monkeypatch.undo()
        clear_cache()


def test_calls_are_serialized_by_one_lock():
    outage_enclosure(Model(), 1, 0)
    start = time.perf_counter()
    outage_enclosure(Model(), 1, 0)
    # Wait far longer than one cached call takes, so that a missing lock cannot pass by timing.
    wait = max(1.0, 50 * (time.perf_counter() - start))
    done = threading.Event()

    def call():
        outage_enclosure(Model(), 1, 0)
        done.set()

    with _runtime._LOCK:
        worker = threading.Thread(target=call)
        worker.start()
        assert not done.wait(wait), "a call ran while another caller held the lock"
    worker.join(60)
    assert done.is_set()


GUARDS_UNDER_O = r'''
import json, sys
import numpy as np
from flint import arb
from certoutage import Model, _generate, _runtime
from certoutage._vendor import commun, ppp, thermal_backend

def inward(convert):
    original = np.nextafter
    np.nextafter = lambda value, direction: original(value, -direction)
    try:
        convert(arb(1))
    finally:
        np.nextafter = original

def negative_masses():
    original = ppp.arb
    ppp.arb = lambda value: -original(value)
    try:
        ppp.envelopes(np.array([0., .5]), np.array([0., .5]), None, None)
    finally:
        ppp.arb = original

def laplace():
    original = _generate.transform
    _generate.transform = lambda s, lam, eta: arb(2) if isinstance(s, arb) else original(s, lam, eta)
    try:
        with _runtime.arithmetic(160):
            _generate.environment_arrays("0.1", 4, 12, "PPP")
    finally:
        _generate.transform = original

cases = {
    "commun.out finite": lambda: commun.out(arb("nan")),
    "commun.out outward": lambda: inward(commun.out),
    "commun.poisson_tail": lambda: commun.poisson_tail(arb(2), 0),
    "ppp.envelopes CDF": lambda: ppp.envelopes(np.array([0., .8]), np.array([0., .2]), None, None),
    "ppp.envelopes masses": negative_masses,
    "thermal_backend.tighten": lambda: thermal_backend.tighten(np.array([.8]), np.array([.2])),
    "thermal_backend.outward finite": lambda: thermal_backend.outward(arb("nan")),
    "thermal_backend.outward outward": lambda: inward(thermal_backend.outward),
    "thermal_backend.gamma_series": lambda: thermal_backend.gamma_series(arb(-1), arb(1)),
    "Laplace check": laplace,
    "Model validation": lambda: Model(N=0),
}
results = {}
for name, case in cases.items():
    try:
        case()
        results[name] = "no error"
    except Exception as error:
        results[name] = type(error).__name__
asserts_stripped = True
try:
    assert False
except AssertionError:
    asserts_stripped = False
print(json.dumps(dict(optimize=sys.flags.optimize, asserts_stripped=asserts_stripped, results=results)))
'''


def test_guards_hold_under_python_optimization():
    run = subprocess.run([sys.executable, "-O", "-c", GUARDS_UNDER_O], capture_output=True, text=True,
                         timeout=300, check=True)
    report = json.loads(run.stdout.strip().splitlines()[-1])
    assert report["optimize"] == 1 and report["asserts_stripped"]
    expected = {name: "ArithmeticError" for name in report["results"]}
    expected["Model validation"] = "ValueError"
    assert report["results"] == expected
    assert len(expected) == 11


def _asserts_by_function(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in tree.body:
        scopes = ([(f"{node.name}.{item.name}", item) for item in node.body
                   if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
                  if isinstance(node, ast.ClassDef) else [(getattr(node, "name", "<module>"), node)])
        for name, scope in scopes:
            if any(isinstance(sub, ast.Assert) for sub in ast.walk(scope)):
                found.add(name)
    return found


def test_no_assert_is_reachable_from_the_public_api():
    from certoutage._vendor import oracles
    found = {(path.relative_to(PACKAGE).as_posix(), name)
             for path in PACKAGE.rglob("*.py") for name in _asserts_by_function(path)}
    # The only two left are in archive code that the package never runs.
    assert found == {("_vendor/oracles.py", "Signal.__init__"), ("_vendor/oracles.py", "calibration")}
    assert _runtime.Signal.__init__ is not oracles.Signal.__init__
    # The subclass never delegates to the archive constructor, and nothing calls `calibration`.
    sources = {path: path.read_text(encoding="utf-8") for path in PACKAGE.rglob("*.py")}
    assert not any("super(" in text or "OriginalSignal.__init__" in text for text in sources.values())
    assert sum(text.count("calibration") for text in sources.values()) == 1
    assert "def calibration" in sources[PACKAGE / "_vendor" / "oracles.py"]


def test_regeneration_tools_refuse_unsafe_outputs(tmp_path):
    existing = tmp_path / "existing.npz"
    existing.write_bytes(b"keep me")
    run = subprocess.run([sys.executable, str(ROOT / "tools" / "regenerate_ppp.py"), "--output", str(existing)],
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 2 and "already exists" in run.stderr
    assert existing.read_bytes() == b"keep me"
    run = subprocess.run([sys.executable, str(ROOT / "tools" / "regenerate_from_archive.py"),
                          "--archive", str(tmp_path), "--output", str(tmp_path / "inside"), "--kind", "signal"],
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 2 and "inside the archive" in run.stderr
    assert not (tmp_path / "inside").exists()
    archive, output = tmp_path / "archive", tmp_path / "existing_output"
    archive.mkdir()
    output.mkdir()
    (output / "keep.txt").write_text("keep me", encoding="utf-8")
    run = subprocess.run([sys.executable, str(ROOT / "tools" / "regenerate_from_archive.py"),
                          "--archive", str(archive), "--output", str(output), "--kind", "signal"],
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 2 and "must be new" in run.stderr
    assert [p.name for p in output.iterdir()] == ["keep.txt"]


def _count_environment_builds(monkeypatch):
    builds = []
    original = _runtime.environment_arrays
    monkeypatch.setattr(_runtime, "environment_arrays", lambda *args: builds.append(args) or original(*args))
    return builds


def test_environment_is_shared_across_n_m_convention_user_and_gain(monkeypatch):
    # S03: one Laplace inversion per (lam, eta, kind, M, precision, policy), and sharing changes no result.
    fast = Numerics(ppp_dft_power=12)
    cases = [(24, 1, "C-TX", 1, "exact"), (20, 1, "C-TX", 1, "exact"), (24, 1, "C-INR", 1, "exact"),
             (24, 2, "C-TX", 1, "exact"), (24, 1, "C-TX", 2, "exact"), (24, 1, "C-TX", 1, "eq3"),
             (24, 1, "C-TX", 1, "chernoff")]

    def query(N, m, convention, user, gain):
        return outage_enclosure(Model(N=N, m=m, lam="0.3", convention=convention), user, 10,
                                gain=gain, numerics=fast).as_dict()

    clear_cache()
    builds = _count_environment_builds(monkeypatch)
    shared = [query(*case) for case in cases]
    assert builds == [("0.3", 4, 12, "PPP")]
    for case, result in zip(cases, shared):
        clear_cache()
        assert query(*case) == result
    clear_cache()


def test_environment_is_rebuilt_when_its_key_changes(monkeypatch):
    clear_cache()
    builds = _count_environment_builds(monkeypatch)
    fast = Numerics(ppp_dft_power=12)
    cases = [(Model(lam="0.3"), "PPP", fast), (Model(lam="0.4"), "PPP", fast), (Model(lam="0.3", eta=3), "PPP", fast),
             (Model(lam="0.3"), "Gamma", fast), (Model(lam="0.3"), "PPP", Numerics(ppp_dft_power=13)),
             (Model(lam="0.3"), "PPP", Numerics(precision_bits=192, ppp_dft_power=12)),
             (Model(lam="0.1"), "PPP", fast), (Model(lam="0.1"), "PPP", replace(fast, bank_policy="fresh"))]
    for model, interference, numerics in cases:
        result = outage_enclosure(model, 1, 10, interference=interference, numerics=numerics)
        assert result.contract.precision_bits == numerics.precision_bits
    # Seven builds: the archived lam=0.1 under "auto" reads its bank instead.
    assert len(builds) == 7
    with _runtime.arithmetic(160), pytest.raises(ArithmeticError, match="precision of its cache key"):
        _runtime._environment("0.35", 4, "PPP", 192, 12, "auto")   # a key not yet cached
    clear_cache()
