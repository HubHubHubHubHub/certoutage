"""Explicit preparation and logical identities for useful-gain banks."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from decimal import Decimal
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
from importlib import import_module
from importlib.resources import files
import re
from time import perf_counter
from typing import Literal

from . import _banks
from ._generate_gain import GENERATION_VERSION, generation_scope
from .models import Model, Gain

# Measured wall seconds on one cluster CPU core. Local machines can take
# 1.3--1.7 times longer. These intervals are estimates, never a deadline.
_COSTS = {"GAIN1": (24., 24.), "GAIN": (25., 25.),
          "SIG1": (370., 950.), "SIG": (50., 50.),
          "CHERNOFF": (3., 11.), "SIGC": (130., 260.)}
# Digest encoding: concatenate, in this order, UTF-8 relative filename, NUL,
# the exact file bytes, then NUL. This covers the certifying generator sources.
_SOURCE_FILES = ("_generate_gain.py", "_nakagami.py", "_chernoff.py",
                 "_vendor/thermal_backend.py", "_vendor/nak_grouped.py",
                 "_vendor/commun.py")
_LOGICAL = re.compile(r"(?:m([123])_N(\d+)|SIG_(\d+)|SIG_m([23])_N(\d+)|C_N(\d+)|SIG_C_(\d+))\.npz")


@dataclass(frozen=True)
class PreparedBank:
    """One verified bank, or a dry-run entry, in dependency order.

    ``seconds`` is measured elapsed time. ``estimated_seconds`` is a lower /
    upper estimate on one CPU core, nonzero only for a missing bank in a plan.
    Entries returned by fetch_banks have estimated_seconds=None.
    Missing entries have no digest or size; their stored name is unknown until
    their input digests are available. A plan performs no calculation or write.
    """

    logical: str
    stored_name: str | None
    origin: Literal["embedded", "cached", "generated", "fetched", "missing"]
    sha256: str | None
    bytes: int | None
    seconds: float = 0.0
    estimated_seconds: tuple[float, float] | None = (0.0, 0.0)


@lru_cache(maxsize=1)
def _code_sha256() -> str:
    root = files("certoutage")
    digest = sha256()
    for name in _SOURCE_FILES:
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(root.joinpath(name).read_bytes() + b"\0")
    return digest.hexdigest()


def _spec(logical: str) -> tuple[dict, int, int]:
    match = _LOGICAL.fullmatch(logical)
    if match is None:
        raise ValueError(f"Bank not provided: {logical}")
    a, b, c, d, e, f, g = match.groups()
    N, m = int(b or c or e or f or g), int(a or d or 1)
    scope = generation_scope("chernoff" if f or g else "exact", m, N)
    return next(bank for bank in scope["banks"] if bank["name"] == logical), N, m


def _identity(logical: str, *, thermal_ratio: Fraction = Fraction(10)) -> tuple[str, dict, dict]:
    """Compute an identity from manifest/descriptor metadata, never input arrays."""
    bank, N, m = _spec(logical)
    family = bank["family"]
    parameters = dict(logical=logical, N=N, m=m, bits=160)
    if family in ("GAIN", "CHERNOFF"):
        parameters["power"] = 19
    if family == "CHERNOFF":
        parameters["stride"] = 8
    if family in ("SIG", "SIGC"):
        if not isinstance(thermal_ratio, Fraction):
            raise TypeError("thermal_ratio must be an exact Fraction")
        parameters["thermal_ratio"] = str(thermal_ratio)
        for argument, dependency in bank["requires"].items():
            key = "chernoff" if argument == "cbank" else argument
            parameters[key + "_sha256"] = _metadata(dependency)["sha256"]
    generator = dict(name=bank["function"], version=GENERATION_VERSION)
    return family, parameters, generator


def _stored_name(logical: str) -> str:
    return _banks._generated_name(*_identity(logical))


def _metadata(name: str) -> dict:
    if _banks._is_embedded(name):
        origin = "embedded"
        if not _banks._package_available(name):
            _banks._read_fetched(name)
            origin = "fetched"
        return dict(_banks.manifest()[name], name=name, origin=origin)
    stored = name if _banks._GENERATED_NAME.fullmatch(name) else _stored_name(name)
    return _banks._generated_descriptor(stored)


def _direct(model: Model) -> bool:
    """The historical direct route is fixed by N and m, never the cache."""
    return ((model.m == 1 and model.N in (8, 64)) or
            (model.m in (2, 3) and model.N == 8))


def _required_names(model: Model, gain: Gain, interference: str | None = None,
                    *, largest: bool = False) -> list[str]:
    scope = generation_scope(gain, model.m, model.N)
    paths = scope["paths"]
    if largest:
        return paths["largest_interferer"]
    no_interference = Decimal(model.lam) == 0 or model.g == "0" or interference == "none"
    if interference is not None:
        return paths["direct"] + ["commun.npz"] if _direct(model) and no_interference else paths["with_interference"]
    # Union over every public query for this model, including J_max and the
    # explicit interference="none" option. The environment stays on demand.
    result = list(paths["largest_interferer"])
    if _direct(model):
        result += paths["direct"] + ["commun.npz"]
    if not _direct(model) or not no_interference:
        result += paths["with_interference"]
    return list(dict.fromkeys(result))


def _estimate(logical: str) -> tuple[float, float]:
    bank, _, m = _spec(logical)
    family = bank["family"]
    return _COSTS[family + "1" if m == 1 and family in ("GAIN", "SIG") else family]


def _entry(logical: str) -> PreparedBank:
    try:
        meta = _metadata(logical)
    except _banks.BankNotAvailable:
        if _banks._is_embedded(logical):
            return PreparedBank(logical, logical, "missing", None, None)
        try:
            stored = _stored_name(logical)
        except _banks.BankNotAvailable:
            stored = None
        return PreparedBank(logical, stored, "missing", None, None,
                            estimated_seconds=_estimate(logical))
    return PreparedBank(logical, meta["name"],
                        meta["origin"] if meta["origin"] in ("embedded", "fetched") else "cached",
                        meta["sha256"], meta["bytes"])


def _plan(model: Model, gain: Gain) -> tuple[PreparedBank, ...]:
    scope = generation_scope(gain, model.m, model.N)
    specs = {bank["name"]: bank for bank in scope["banks"]}
    required = _required_names(model, gain)
    selected = {}

    def visit(logical, target=False):
        if logical in selected:
            return
        entry = _entry(logical)
        if entry.origin == "missing" and not _banks._is_embedded(logical):
            for dependency in specs[logical]["requires"].values():
                visit(dependency)
        if target or entry.origin == "missing":
            selected[logical] = entry

    for logical in required:
        visit(logical, True)
    order = [bank["name"] for bank in scope["banks"]] + scope["shared_inputs"]
    return tuple(selected[name] for name in order if name in selected)


def _require_ready(model: Model, gain: Gain, interference: str = "PPP", *, largest: bool = False) -> None:
    """Fail before an environment, a thermal object or a search is computed."""
    missing = []
    for logical in _required_names(model, gain, interference, largest=largest):
        try:
            _metadata(logical)
        except _banks.BankNotAvailable:
            missing.append(logical)
    if missing:
        plan = _plan(model, gain)
        lower = sum(row.estimated_seconds[0] for row in plan)
        upper = sum(row.estimated_seconds[1] for row in plan)
        call = f'certoutage.prepare(Model(N={model.N}, m={model.m}), gain="{gain}")'
        from ._fetch import _download_bytes
        megabytes = _download_bytes(model.N) / 1_000_000
        raise _banks.BankNotAvailable(
            f"Banks not ready: {', '.join(missing)}. "
            f"Call certoutage.fetch_banks({model.N}) (about {megabytes:.2f} MB download), "
            f"or {call}. "
            f"Estimated preparation: {lower:g}--{upper:g} seconds on one CPU core; "
            "local machines may take 1.3--1.7 times longer.")


def prepare(model: Model, *, gain: Gain = "exact", dry_run: bool = False,
            fetch: bool = False) -> tuple[PreparedBank, ...]:
    """Explicitly prepare missing useful-gain banks at 160 bits.

    With fetch=True, first call fetch_banks(model.N); dry runs never fetch.

    Reuse verified embedded/cached banks. Return the read set and missing
    dependencies, in generation_scope order. With dry_run=True return an
    immutable plan with one-core estimates, without calculation or writes.
    PPP and Gamma environments are still computed by queries when needed.
    """
    from .api import _validate, DEFAULT_NUMERICS
    from . import _runtime as rt

    _validate(model, 1, gain, "PPP", DEFAULT_NUMERICS)
    if type(dry_run) is not bool:
        raise TypeError("dry_run must be a boolean")
    if type(fetch) is not bool:
        raise TypeError("fetch must be a boolean")
    if fetch and not dry_run:
        from ._fetch import fetch_banks
        fetch_banks(model.N)
    plan = _plan(model, gain)
    if dry_run:
        return plan
    result = []
    with rt.arithmetic(160):
        for planned in plan:
            started = perf_counter()
            entry = _entry(planned.logical)
            if entry.origin == "missing":
                if _banks._is_embedded(entry.logical):
                    _banks._read_fetched(entry.logical)
                bank, _, _ = _spec(entry.logical)
                arguments = dict(bank["parameters"], bits=160)
                arguments.update({key: _banks.arrays(name) for key, name in bank["requires"].items()})
                module, function = bank["function"].rsplit(".", 1)
                arrays = getattr(import_module(module), function)(**arguments)
                family, parameters, generator = _identity(entry.logical)
                generator["code_sha256"] = _code_sha256()
                stored = _banks._store_generated(family, parameters, generator, arrays)
                # Every produced bank goes back through the verified reader.
                _banks.arrays(stored)
                entry = replace(_entry(entry.logical), origin="generated")
            else:
                _banks.arrays(entry.logical)
            result.append(replace(entry, seconds=perf_counter() - started))
        if any(row.origin == "generated" for row in result):
            rt.clear()
    return tuple(result)


def _generated_provenance(names: list[str]) -> tuple[bool, tuple[str, ...]]:
    notes = []
    for name in dict.fromkeys(names):
        meta = _metadata(name)
        if meta["origin"] in ("embedded", "fetched"):
            continue
        p = meta["parameters"]
        notes.append(
            f"Generated bank {p['logical']}: N={p['N']}, m={p['m']}, thermal ratio 10, "
            f"{p['bits']} bits, GENERATION_VERSION={meta['generator']['version']}; "
            f"certoutage {meta['certoutage_version']}, python-flint {meta['python_flint_version']}, "
            f"numpy {meta['numpy_version']}")
        if meta["family"] in ("CHERNOFF", "SIGC"):
            notes.append("Generated Chernoff bank bytes can depend on the machine through the "
                         "noncertifying binary64 initial guess; Arb signs certify the bracket")
    return bool(notes), tuple(notes)


@contextmanager
def _force_generation(*logical_names: str):
    """Private audit hook: ignore embedded entries only for the named banks.

    Used for forced reproduction controls; not a public generation option.
    Runtime routing is unchanged. Clear calculation objects on both sides so
    that the selected banks are actually read under this scoped override.
    """
    from . import _runtime as rt
    for name in logical_names:
        _spec(name)
    with rt.arithmetic(160):
        rt.clear()
        token = _banks._FORCED.set(frozenset(logical_names))
        try:
            yield
        finally:
            _banks._FORCED.reset(token)
            rt.clear()
