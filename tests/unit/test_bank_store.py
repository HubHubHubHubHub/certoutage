"""Offline bank-store guarantees, isolated from the real user cache."""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import multiprocessing
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from types import SimpleNamespace
import zipfile

import flint
import numpy as np
import pytest

import certoutage
from certoutage import Model, clear_cache, outage_enclosure, required_snr
from certoutage import _banks


GENERATOR = {"name": "test-fake", "version": "0"}
PARAMETERS = {"N": 24, "gain": "exact", "enabled": True, "scale": "0.1"}


def _fake_arrays():
    return {"signal": np.array([[0.125, 0.5], [0.25, 0.75]], dtype=np.float64),
            "levels": np.array([-1, 0, 1], dtype=np.int8)}


def _expected_name(family="TEST", parameters=None, generator=None):
    generator = GENERATOR if generator is None else generator
    identity = {"family": family, "parameters": PARAMETERS if parameters is None else parameters,
                "generator": {key: generator[key] for key in ("name", "version")}}
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False).encode("ascii")
    return f"{family}_{sha256(canonical).hexdigest()[:16]}.npz"


def _store(**kwargs):
    options = dict(family="TEST", parameters=PARAMETERS, generator=GENERATOR, arrays=_fake_arrays())
    options.update(kwargs)
    return _banks._store_generated(**options)


def _paths(name):
    bank = _banks.cache_dir() / "generated" / name
    return bank, bank.with_suffix(".json")


def _read_descriptor(name):
    return json.loads(_paths(name)[1].read_text(encoding="utf-8"))


def _write_descriptor(name, descriptor):
    _paths(name)[1].write_text(json.dumps(descriptor), encoding="utf-8")


def _refuse_network(*args, **kwargs):
    raise AssertionError("Bank store attempted network access")


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setenv("CERTOUTAGE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(socket, "socket", _refuse_network)
    monkeypatch.setattr(socket, "create_connection", _refuse_network)
    clear_cache()
    yield
    clear_cache()


def test_generated_round_trip_and_descriptor():
    name = _store()
    assert name == _expected_name()
    bank, descriptor_path = _paths(name)
    content, origin = _banks._resolve(name)
    assert origin == "generated"
    assert content == bank.read_bytes() == _banks.verified_bytes(name)
    descriptor = _read_descriptor(name)
    assert set(descriptor) == {
        "schema", "name", "sha256", "bytes", "origin", "family", "parameters", "generator",
        "certoutage_version", "python_flint_version", "numpy_version", "created_utc",
    }
    assert descriptor_path.name == name[:-4] + ".json"
    assert descriptor["schema"] == 1 and type(descriptor["schema"]) is int
    assert descriptor["name"] == name and descriptor["origin"] == "generated"
    assert descriptor["family"] == "TEST" and descriptor["parameters"] == PARAMETERS
    assert descriptor["generator"] == GENERATOR
    assert descriptor["sha256"] == sha256(content).hexdigest()
    assert descriptor["bytes"] == len(content)
    assert descriptor["certoutage_version"] == certoutage.__version__
    assert descriptor["python_flint_version"] == flint.__version__
    assert descriptor["numpy_version"] == np.__version__
    assert descriptor["created_utc"].endswith("Z")
    assert datetime.fromisoformat(descriptor["created_utc"][:-1] + "+00:00") <= datetime.now(timezone.utc)
    loaded = _banks.arrays(name)
    assert loaded.keys() == _fake_arrays().keys()
    for key, expected in _fake_arrays().items():
        assert loaded[key].dtype == expected.dtype
        np.testing.assert_array_equal(loaded[key], expected)
        assert not loaded[key].flags.writeable
        with pytest.raises(ValueError):
            loaded[key].flat[0] = 0
    assert not (_banks.cache_dir() / "fetched").exists()


def test_generated_identity_is_canonical_and_versioned():
    parameters = dict(PARAMETERS, label="é", hex_value=(0.1).hex())
    first = _store(parameters=parameters)
    assert first == _expected_name(parameters=parameters)
    assert _store(parameters=dict(reversed(list(parameters.items()))),
                  generator=dict(reversed(list(GENERATOR.items())))) == first
    names = {first, _store(parameters=dict(parameters, N=25)),
             _store(parameters=parameters, generator=dict(GENERATOR, version="1")),
             _store(parameters=parameters, generator=dict(GENERATOR, name="another")),
             _store(family="OTHER", parameters=parameters)}
    assert len(names) == 5


def test_optional_generator_digest_is_metadata():
    generator = dict(GENERATOR, code_sha256="a" * 64)
    name = _store(generator=generator)
    assert name == _expected_name()
    assert _read_descriptor(name)["generator"] == generator
    assert _banks._resolve(name)[1] == "generated"


@pytest.mark.parametrize("parameters", [
    {"real": 0.1}, {"real": float("nan")}, {"real": float("inf")},
    {"nested": {}}, {"nested": [1]}, {"null": None}, {1: "wrong key"}, [1],
])
def test_inexact_or_nested_parameters_are_rejected(parameters):
    with pytest.raises(TypeError, match="flat dictionary"):
        _store(parameters=parameters)
    assert not _banks.cache_dir().exists()


@pytest.mark.parametrize("family", ["test", "", "A" * 17, "A_B", "../A", "A/B", "A\\B", 1])
def test_invalid_families_are_rejected(family):
    with pytest.raises(ValueError, match="family"):
        _store(family=family)
    assert not _banks.cache_dir().exists()


@pytest.mark.parametrize("generator", [
    {}, {"name": "test-fake"}, {"name": "test-fake", "version": 0},
    dict(GENERATOR, name=""), dict(GENERATOR, unexpected=True),
    dict(GENERATOR, code_sha256="bad"), dict(GENERATOR, code_sha256=1),
])
def test_invalid_generators_are_rejected(generator):
    with pytest.raises((TypeError, ValueError), match="generator"):
        _store(generator=generator)
    assert not _banks.cache_dir().exists()


@pytest.mark.parametrize("name", [
    "TEST_0123456789ABCDEF.npz", "TEST_0123456789abcde.npz", "TEST_0123456789abcdef0.npz",
    "test_0123456789abcdef.npz", "A_B_0123456789abcdef.npz", "A" * 17 + "_0123456789abcdef.npz",
    "../TEST_0123456789abcdef.npz", "a/TEST_0123456789abcdef.npz",
    "a\\TEST_0123456789abcdef.npz", "TEST_0123456789abcdef.npz\n", "unknown.npz",
])
def test_unknown_names_keep_the_original_error(name):
    with pytest.raises(ValueError) as error:
        _banks.verified_bytes(name)
    assert str(error.value) == f"Bank not provided: {name}"
    assert not _banks.cache_dir().exists()


def test_generated_names_are_disjoint_from_all_embedded_names():
    pattern = re.compile(r"^[A-Z][A-Z0-9]{0,15}_[0-9a-f]{16}\.npz$")
    names = _banks.manifest()
    assert len(names) == 43
    assert not any(pattern.fullmatch(name) for name in names)
    assert pattern.fullmatch(_store())
    assert _banks.ORIGINS == ("embedded", "generated", "fetched")
    assert certoutage.BankNotAvailable is _banks.BankNotAvailable
    assert "BankNotAvailable" in certoutage.__all__


@pytest.mark.parametrize("damage", ["one-byte", "truncated"])
def test_generated_corruption_is_rejected_before_loading(monkeypatch, damage):
    name = _store()
    bank, _ = _paths(name)
    content = bank.read_bytes()
    bank.write_bytes(content[:-1] + bytes([content[-1] ^ 1]) if damage == "one-byte" else content[:32])

    def must_not_load(*args, **kwargs):
        pytest.fail("Deserialization ran before integrity verification")

    monkeypatch.setattr(np, "load", must_not_load)
    with pytest.raises(_banks.IntegrityError, match=re.escape(name)):
        _banks.arrays(name)


@pytest.mark.parametrize("field,value", [
    ("schema", 2), ("schema", True), ("name", "TEST_0000000000000000.npz"), ("name", 1),
    ("sha256", "0" * 64), ("sha256", "A" * 64), ("sha256", 1),
    ("bytes", 1), ("bytes", True), ("bytes", -1), ("bytes", "10"),
    ("origin", "embedded"), ("origin", None), ("family", "OTHER"), ("family", 1),
    ("parameters", dict(PARAMETERS, N=25)), ("parameters", {"real": 0.1}),
    ("parameters", {"nested": {}}), ("parameters", []),
    ("generator", dict(GENERATOR, version="1")), ("generator", dict(GENERATOR, name="changed")),
    ("generator", dict(GENERATOR, version=1)), ("generator", dict(GENERATOR, code_sha256="bad")),
    ("generator", dict(GENERATOR, extra="bad")), ("generator", []),
    ("certoutage_version", 1), ("python_flint_version", None), ("numpy_version", ""),
    ("created_utc", 1), ("created_utc", "2026-11-26T00:00:00+00:00"),
    ("created_utc", "2026-02-30T00:00:00Z"), ("created_utc", "invalid"),
])
def test_descriptor_tampering_is_rejected(field, value):
    name = _store()
    descriptor = _read_descriptor(name)
    descriptor[field] = value
    _write_descriptor(name, descriptor)
    with pytest.raises(_banks.IntegrityError, match=re.escape(name[:-4])):
        _banks.verified_bytes(name)


@pytest.mark.parametrize("field", [
    "schema", "name", "sha256", "bytes", "origin", "family", "parameters", "generator",
    "certoutage_version", "python_flint_version", "numpy_version", "created_utc", "extra",
])
def test_descriptor_fields_are_exact(field):
    name = _store()
    descriptor = _read_descriptor(name)
    if field == "extra":
        descriptor[field] = 0
    else:
        descriptor.pop(field)
    _write_descriptor(name, descriptor)
    with pytest.raises(_banks.IntegrityError, match=re.escape(name[:-4] + ".json")):
        _banks.verified_bytes(name)


@pytest.mark.parametrize("content", [b"{", b"\xff", b"[]", b"null", b'{"schema":1,"schema":1}'])
def test_unreadable_descriptors_are_integrity_errors(content):
    name = _store()
    _paths(name)[1].write_bytes(content)
    with pytest.raises(_banks.IntegrityError, match=re.escape(name[:-4] + ".json")):
        _banks.verified_bytes(name)


@pytest.mark.parametrize("remaining", ["neither", "bank", "descriptor"])
def test_absent_generated_bank_never_falls_back(monkeypatch, remaining):
    name = _expected_name()
    if remaining != "neither":
        assert _store() == name
        bank, descriptor = _paths(name)
        (descriptor if remaining == "bank" else bank).unlink()

    def forbidden(*args, **kwargs):
        pytest.fail("A missing bank triggered preparation or a fetched fallback")

    monkeypatch.setattr(_banks, "_read_fetched", forbidden)
    monkeypatch.setattr(_banks, "_store_generated", forbidden)
    with pytest.raises(_banks.BankNotAvailable) as error:
        _banks.arrays(name)
    assert isinstance(error.value, LookupError)
    assert name in str(error.value)
    assert str(_banks.cache_dir() / "generated") in str(error.value)
    assert "call certoutage.prepare(model, gain=...) first" in str(error.value)


def test_absence_and_descriptor_reads_are_not_cached():
    name = _expected_name()
    with pytest.raises(_banks.BankNotAvailable):
        _banks.verified_bytes(name)
    assert _store() == name
    assert _banks.verified_bytes(name)
    descriptor = _read_descriptor(name)
    descriptor["parameters"] = dict(PARAMETERS, N=100)
    _write_descriptor(name, descriptor)
    with pytest.raises(_banks.IntegrityError):
        _banks.verified_bytes(name)


def test_cache_never_shadows_embedded_banks():
    embedded = _banks.files("certoutage").joinpath("data", "SIG_24.npz").read_bytes()
    model = Model(N=24, convention="C-INR")
    before = outage_enclosure(model, 1, 0, gain="eq3", interference="mean")
    name = _store()
    descriptor = _read_descriptor(name)
    corrupted = embedded[:-1] + bytes([embedded[-1] ^ 1])
    descriptor.update(name="SIG_24.npz", family="SIG", parameters={"N": 24},
                      sha256=sha256(corrupted).hexdigest(), bytes=len(corrupted))
    for directory in (_banks.cache_dir(), _banks.cache_dir() / "generated"):
        (directory / "SIG_24.npz").write_bytes(corrupted)
        (directory / "SIG_24.json").write_text(json.dumps(descriptor), encoding="utf-8")
    clear_cache()
    assert _banks.verified_bytes("SIG_24.npz") == embedded
    assert _banks._resolve("SIG_24.npz") == (embedded, "embedded")
    after = outage_enclosure(model, 1, 0, gain="eq3", interference="mean")
    assert (after.lower.hex(), after.upper.hex()) == (before.lower.hex(), before.upper.hex())
    assert after.contract == before.contract


def test_embedded_resolution_does_not_even_consult_cache(monkeypatch):
    expected = _banks.verified_bytes("SIG_24.npz")

    def forbidden():
        pytest.fail("Embedded resolution consulted the user cache")

    monkeypatch.setattr(_banks, "cache_dir", forbidden)
    assert _banks.verified_bytes("SIG_24.npz") == expected


@pytest.mark.parametrize("query", ["outage", "decision"])
def test_generated_integrity_error_is_not_transformed(monkeypatch, query):
    name = _store()
    bank, _ = _paths(name)
    content = bank.read_bytes()
    bank.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
    original = _banks.verified_bytes
    monkeypatch.setattr(_banks, "verified_bytes",
                        lambda requested: original(name if requested == "SIG_24.npz" else requested))
    with pytest.raises(_banks.IntegrityError, match=re.escape(name)):
        if query == "outage":
            outage_enclosure(Model(), 1, 0)
        else:
            required_snr(Model(), 1, "1e-5")


@pytest.mark.parametrize("explicit,xdg", [
    ("override", "absolute"), (None, "absolute"), ("", "absolute"),
    (None, None), (None, ""), (None, "relative"), ("", "relative"),
])
def test_cache_location_and_reads_create_no_directories(monkeypatch, tmp_path, explicit, xdg):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CERTOUTAGE_CACHE_DIR", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    if explicit is not None:
        monkeypatch.setenv("CERTOUTAGE_CACHE_DIR", str(tmp_path / explicit) if explicit else "")
    if xdg is not None:
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg") if xdg == "absolute" else xdg)
    expected = (tmp_path / "override" if explicit else tmp_path / "xdg/certoutage"
                if xdg == "absolute" else home / ".cache/certoutage")
    assert _banks.cache_dir() == expected
    with pytest.raises(_banks.BankNotAvailable):
        _banks.verified_bytes(_expected_name())
    assert _banks.verified_bytes("SIG_24.npz")
    assert not expected.exists()
    assert not home.exists()
    assert list(tmp_path.iterdir()) == []


def test_cache_environment_is_read_on_every_call(monkeypatch, tmp_path):
    name = _store()
    first = _banks.cache_dir()
    monkeypatch.setenv("CERTOUTAGE_CACHE_DIR", str(tmp_path / "second"))
    assert _banks.cache_dir() != first
    with pytest.raises(_banks.BankNotAvailable):
        _banks.verified_bytes(name)
    assert not _banks.cache_dir().exists()
    assert _store() == name
    monkeypatch.setenv("CERTOUTAGE_CACHE_DIR", str(first))
    assert _banks.verified_bytes(name)


def test_import_creates_no_cache():
    code = '''
import socket
def refuse(*args, **kwargs):
    raise RuntimeError("Network access during import")
socket.socket = socket.create_connection = refuse
import certoutage
from certoutage import _banks
if _banks.cache_dir().exists():
    raise RuntimeError("Import created the bank cache")
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not _banks.cache_dir().exists()


def test_serialization_is_deterministic_across_zip_timestamps():
    first = _banks._serialize_arrays(_fake_arrays())
    time.sleep(2.1)
    second = _banks._serialize_arrays(dict(reversed(list(_fake_arrays().items()))))
    assert first == second
    with zipfile.ZipFile(BytesIO(first)) as archive:
        assert archive.namelist() == ["levels.npy", "signal.npy"]
        assert all(entry.date_time == (1980, 1, 1, 0, 0, 0)
                   and entry.compress_type == zipfile.ZIP_STORED for entry in archive.infolist())
    with np.load(BytesIO(second), allow_pickle=False) as loaded:
        for key, expected in _fake_arrays().items():
            np.testing.assert_array_equal(loaded[key], expected)


@pytest.mark.parametrize("array", [np.array([{}], dtype=object),
                                   np.array([(1, {})], dtype=[("number", "i4"), ("object", object)])])
def test_object_dtype_is_refused_before_any_write(array):
    with pytest.raises(TypeError, match="Object dtype"):
        _store(arrays={"bad": array})
    assert not _banks.cache_dir().exists()


def test_verified_existing_bank_is_not_rewritten(monkeypatch):
    name = _store()
    paths = _paths(name)
    before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths]

    def forbidden(*args, **kwargs):
        pytest.fail("An idempotent store attempted a write")

    monkeypatch.setattr(_banks, "_atomic_write", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    assert _store() == name
    assert [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths] == before


def test_corrupt_existing_bank_is_not_silently_replaced():
    name = _store()
    bank, _ = _paths(name)
    bank.write_bytes(b"broken")
    with pytest.raises(_banks.IntegrityError, match=re.escape(name)):
        _store()
    assert bank.read_bytes() == b"broken"


@pytest.mark.skipif(os.name == "nt" or getattr(os, "geteuid", lambda: -1)() == 0,
                    reason="POSIX directory permissions are not enforced the same way on Windows or for root")
def test_read_only_cache_can_be_read_but_not_written():
    name = _store()
    cache = _banks.cache_dir()
    directory = cache / "generated"
    before = sorted(path.name for path in directory.iterdir())
    cache.chmod(0o555)
    directory.chmod(0o555)
    try:
        np.testing.assert_array_equal(_banks.arrays(name)["signal"], _fake_arrays()["signal"])
        with pytest.raises(PermissionError):
            _store(parameters=dict(PARAMETERS, N=25))
        assert sorted(path.name for path in directory.iterdir()) == before
    finally:
        cache.chmod(0o755)
        directory.chmod(0o755)


@pytest.mark.parametrize("failure_suffix", [".npz", ".json"])
def test_failed_replace_cleans_temporary_and_preserves_exception(monkeypatch, failure_suffix):
    original = _banks.os.replace
    failure = OSError("injected replacement failure")
    replaced = []

    def replace(source, destination):
        assert Path(source).parent == Path(destination).parent
        if Path(destination).suffix == failure_suffix:
            raise failure
        replaced.append(Path(destination).suffix)
        original(source, destination)

    monkeypatch.setattr(_banks.os, "replace", replace)
    with pytest.raises(OSError) as error:
        _store()
    assert error.value is failure
    directory = _banks.cache_dir() / "generated"
    assert sorted(path.name for path in directory.iterdir()) == (
        [_expected_name()] if failure_suffix == ".json" else [])
    assert replaced == ([".npz"] if failure_suffix == ".json" else [])
    with pytest.raises(_banks.BankNotAvailable):
        _banks.verified_bytes(_expected_name())


def test_failed_flush_cleans_temporary(monkeypatch):
    failure = OSError("injected disk flush failure")

    def fail(*args):
        raise failure

    monkeypatch.setattr(_banks.os, "fsync", fail)
    with pytest.raises(OSError) as error:
        _store()
    assert error.value is failure
    assert list((_banks.cache_dir() / "generated").iterdir()) == []


def test_bank_is_committed_before_its_descriptor(monkeypatch):
    original = _banks.os.replace
    suffixes = []

    def replace(source, destination):
        suffixes.append(Path(destination).suffix)
        if Path(destination).suffix == ".json":
            with pytest.raises(_banks.BankNotAvailable):
                _banks.verified_bytes(_expected_name())
        original(source, destination)

    monkeypatch.setattr(_banks.os, "replace", replace)
    _store()
    assert suffixes == [".npz", ".json"]
    assert _banks.verified_bytes(_expected_name())


@pytest.mark.parametrize("platform,failures,exception_type", [
    ("nt", 2, PermissionError), ("nt", 21, PermissionError),
    ("posix", 1, PermissionError), ("nt", 1, OSError),
])
def test_replace_retry_is_bounded_and_windows_only(monkeypatch, tmp_path, platform, failures, exception_type):
    calls, sleeps = [], []
    failure = exception_type("injected open destination")

    def replace(source, destination):
        calls.append((source, destination))
        if len(calls) <= failures:
            raise failure

    monkeypatch.setattr(_banks, "os", SimpleNamespace(name=platform, replace=replace))
    monkeypatch.setattr(_banks.time, "sleep", sleeps.append)
    if platform == "nt" and failures < 21 and exception_type is PermissionError:
        _banks._replace_with_retry(tmp_path / "source", tmp_path / "destination")
        assert len(calls) == 3 and sleeps == [0.05, 0.05]
    else:
        with pytest.raises(exception_type) as error:
            _banks._replace_with_retry(tmp_path / "source", tmp_path / "destination")
        assert error.value is failure
        assert len(calls) == (21 if failures == 21 else 1)
        assert sleeps == ([0.05] * 20 if failures == 21 else [])


def _concurrent_writer(cache, barrier):
    """Spawn target: block networking and make all four writers reach the commit."""
    os.environ["CERTOUTAGE_CACHE_DIR"] = cache
    socket.socket = socket.create_connection = _refuse_network
    original = _banks._atomic_write

    def synchronized_write(destination, content):
        if destination.suffix == ".npz":
            barrier.wait(timeout=30)
        original(destination, content)

    _banks._atomic_write = synchronized_write
    name = _store()
    loaded = _banks.arrays(name)
    for key, expected in _fake_arrays().items():
        if not np.array_equal(loaded[key], expected):
            raise RuntimeError("Concurrent writer read inconsistent bank data")


def test_four_spawn_writers_leave_one_verified_pair():
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(4)
    processes = [context.Process(target=_concurrent_writer, args=(str(_banks.cache_dir()), barrier))
                 for _ in range(4)]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=45)
        assert [process.exitcode for process in processes] == [0, 0, 0, 0]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            if process.pid is not None:
                process.join(timeout=5)
                process.close()
    name = _expected_name()
    assert _banks._resolve(name)[1] == "generated"
    assert sorted(path.name for path in (_banks.cache_dir() / "generated").iterdir()) == sorted(
        [name, name[:-4] + ".json"])


def test_fetched_origin_is_explicitly_reserved():
    with pytest.raises(NotImplementedError, match="fetched banks are planned for version 0.4.0"):
        _banks._read_fetched("future.npz")
    assert not _banks.cache_dir().exists()


@pytest.mark.parametrize("generator", [GENERATOR, dict(GENERATOR, code_sha256="b" * 64)])
def test_writer_refuses_different_arrays_under_the_same_identity(generator):
    name = _store(generator=dict(GENERATOR, code_sha256="a" * 64))
    paths = _paths(name)
    before = [path.read_bytes() for path in paths]
    changed = dict(_fake_arrays(), levels=np.array([-1, 0, 2], dtype=np.int8))
    for arrays in (changed, {"signal": _fake_arrays()["signal"]},
                   dict(_fake_arrays(), levels=_fake_arrays()["levels"].view(np.uint8)),
                   dict(_fake_arrays(), signal=_fake_arrays()["signal"].reshape(4))):
        with pytest.raises(_banks.IntegrityError, match="different arrays"):
            _store(generator=generator, arrays=arrays)
    assert [path.read_bytes() for path in paths] == before


def test_writer_accepts_equal_arrays_in_another_memory_layout():
    name = _store()
    before = [path.read_bytes() for path in _paths(name)]
    fortran = {key: np.asfortranarray(value) for key, value in _fake_arrays().items()}
    assert _store(arrays=fortran) == name
    assert [path.read_bytes() for path in _paths(name)] == before


@pytest.mark.parametrize("key", ["a\x00b", "", "a/b", "a\\b", ".", "..", "a.b", "é", "x" * 65, 1])
def test_array_keys_are_restricted_before_any_write(key):
    with pytest.raises(TypeError, match="keys matching"):
        _store(arrays={key: np.arange(2)})
    assert not _banks.cache_dir().exists()


def test_serialized_bytes_must_reproduce_their_arrays(monkeypatch):
    other = _banks._serialize_arrays({"signal": np.arange(3)})
    monkeypatch.setattr(_banks, "_serialize_arrays", lambda arrays: other)
    with pytest.raises(_banks.IntegrityError, match="does not reproduce"):
        _store()
    assert not _banks.cache_dir().exists()


def test_cache_that_is_a_file_means_absent_bank():
    _banks.cache_dir().mkdir(parents=True)
    (_banks.cache_dir() / "generated").write_bytes(b"not a directory")
    with pytest.raises(_banks.BankNotAvailable):
        _banks.verified_bytes(_expected_name())


@pytest.mark.skipif(os.name == "nt", reason="Windows reports reading a directory as PermissionError")
@pytest.mark.parametrize("which", [0, 1])
def test_directory_in_place_of_bank_or_descriptor_is_an_integrity_error(which):
    name = _store()
    path = _paths(name)[which]
    path.unlink()
    path.mkdir()
    with pytest.raises(_banks.IntegrityError, match="is a directory"):
        _banks.verified_bytes(name)
    with pytest.raises(_banks.IntegrityError, match="is a directory"):
        _store()


def test_no_public_path_reaches_the_generated_store(monkeypatch):
    # Embedded queries still never consult the generated store. The explicit
    # preparation entry point now exposes that store for missing logical banks.
    assert callable(certoutage.prepare)
    assert "prepare" in certoutage.__all__
    assert certoutage.BankNotAvailable is _banks.BankNotAvailable

    def forbidden(*args, **kwargs):
        pytest.fail("A public query reached the generated-bank store")

    resolved = []
    original = _banks._resolve

    def recording(name):
        resolved.append(name)
        return original(name)

    for attribute in ("_read_generated", "_store_generated", "cache_dir"):
        monkeypatch.setattr(_banks, attribute, forbidden)
    monkeypatch.setattr(_banks, "_resolve", recording)
    clear_cache()
    results = [outage_enclosure(Model(), 1, 0),
               outage_enclosure(Model(N=24, convention="C-INR"), 1, 0, gain="eq3", interference="mean"),
               outage_enclosure(Model(), 1, 0, interference="Gamma"),
               required_snr(Model(), 1, "1e-5")]
    assert resolved and set(resolved) <= set(_banks.manifest())
    assert all(result.contract.source != "generated-banks" for result in results)
