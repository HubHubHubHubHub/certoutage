"""Verified bank reads with no writes or network access.

Embedded digests are pinned through the manifest. Generated descriptors detect
corruption, truncation, interrupted writes, process races and a changed
generator name or version; the writer also refuses to keep a stored bank whose
arrays differ from the ones it was asked to store. A generator whose code
changes under the same name and version is not detected at read time; the
optional code_sha256 is recorded in the descriptor, not checked.
They do not defend against a local adversary rewriting both bank and descriptor.
The reserved fetched origin will use digests pinned in code in version 0.4.0.
Only an explicit call to the internal writer creates directories or files.
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
from io import BytesIO
import json
import os
from pathlib import Path
import re
import tempfile
import time
import zipfile

import numpy as np

MANIFEST_SHA256 = "0397d274f08924027840943648ca0816a4403832bace47a79642dee7cc7c5c18"
ORIGINS = ("embedded", "generated", "fetched")
_FORCED = ContextVar("certoutage_audit_forced_banks", default=frozenset())
_GENERATED_NAME = re.compile(r"^[A-Z][A-Z0-9]{0,15}_[0-9a-f]{16}\.npz$")
_FAMILY = re.compile(r"[A-Z][A-Z0-9]{0,15}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ARRAY_KEY = re.compile(r"[A-Za-z0-9_]{1,64}")
_DESCRIPTOR_FIELDS = {
    "schema", "name", "sha256", "bytes", "origin", "family", "parameters",
    "generator", "certoutage_version", "python_flint_version", "numpy_version",
    "created_utc",
}


class IntegrityError(RuntimeError):
    """A bank, its manifest or its descriptor failed verification."""


class BankNotAvailable(LookupError):
    """A generated bank or its committing descriptor is absent."""


@lru_cache(maxsize=1)
def manifest() -> dict:
    content = files("certoutage").joinpath("data/MANIFEST.json").read_bytes()
    if sha256(content).hexdigest() != MANIFEST_SHA256:
        raise IntegrityError("SHA-256 digest mismatch: MANIFEST.json")
    return json.loads(content)


def cache_dir() -> Path:
    """Resolve the current environment without creating a directory."""
    explicit = os.environ.get("CERTOUTAGE_CACHE_DIR")
    if explicit:
        return Path(explicit)
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg and Path(xdg).is_absolute():
        return Path(xdg) / "certoutage"
    return Path(os.path.expanduser("~")) / ".cache" / "certoutage"


def _canonical_json(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _generated_name(family: str, parameters: dict, generator: dict) -> str:
    """Validate the identity and hash exact parameters and generator version."""
    if not isinstance(family, str) or not _FAMILY.fullmatch(family):
        raise ValueError("Bank family must match [A-Z][A-Z0-9]{0,15}")
    if not isinstance(parameters, dict) or any(
        type(key) is not str or type(value) not in (str, int, bool)
        for key, value in parameters.items()
    ):
        raise TypeError("Bank parameters must be a flat dictionary of str keys and "
                        "str, int or bool values; encode reals as exact decimal or float.hex strings")
    if (not isinstance(generator, dict)
            or not {"name", "version"} <= generator.keys()
            or generator.keys() - {"name", "version", "code_sha256"}
            or any(type(generator[key]) is not str or not generator[key]
                   for key in ("name", "version"))):
        raise TypeError("Bank generator must contain nonempty name and version strings "
                        "and only an optional code_sha256")
    if "code_sha256" in generator and (
        type(generator["code_sha256"]) is not str
        or not _SHA256.fullmatch(generator["code_sha256"])
    ):
        raise ValueError("Bank generator code_sha256 must be a lowercase SHA-256 digest")
    identity = {"family": family, "parameters": parameters,
                "generator": {key: generator[key] for key in ("name", "version")}}
    return f"{family}_{sha256(_canonical_json(identity)).hexdigest()[:16]}.npz"


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate descriptor field: {key}")
        result[key] = value
    return result


def _validate_descriptor(descriptor: dict, name: str) -> None:
    if not isinstance(descriptor, dict) or descriptor.keys() != _DESCRIPTOR_FIELDS:
        raise ValueError("Unexpected descriptor fields")
    if type(descriptor["schema"]) is not int or descriptor["schema"] != 1:
        raise ValueError("Unsupported descriptor schema")
    if descriptor["origin"] != "generated" or descriptor["name"] != name:
        raise ValueError("Descriptor origin or name mismatch")
    if type(descriptor["bytes"]) is not int or descriptor["bytes"] < 0:
        raise ValueError("Descriptor bytes must be a nonnegative integer")
    if type(descriptor["sha256"]) is not str or not _SHA256.fullmatch(descriptor["sha256"]):
        raise ValueError("Invalid descriptor SHA-256 digest")
    for key in ("certoutage_version", "python_flint_version", "numpy_version", "created_utc"):
        if type(descriptor[key]) is not str or not descriptor[key]:
            raise ValueError(f"Descriptor {key} must be a nonempty string")
    timestamp = descriptor["created_utc"]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", timestamp):
        raise ValueError("Descriptor created_utc must be an ISO 8601 UTC timestamp ending in Z")
    datetime.fromisoformat(timestamp[:-1] + "+00:00")
    expected = _generated_name(descriptor["family"], descriptor["parameters"], descriptor["generator"])
    if expected != name:
        raise ValueError("Descriptor parameters or generator do not match the bank name")


def _generated_descriptor(name: str) -> dict:
    """Read identity metadata only; input-bank arrays are never loaded here."""
    directory = cache_dir() / "generated"
    bank_path = directory / name
    descriptor_path = bank_path.with_suffix(".json")
    try:
        raw_descriptor = descriptor_path.read_bytes()
        if bank_path.is_dir():
            raise IsADirectoryError(21, "Bank is a directory", str(bank_path))
        bank_path.stat()
    except (FileNotFoundError, NotADirectoryError) as error:
        raise BankNotAvailable(
            f"Bank {name} is not available in {directory}; "
            "call certoutage.prepare(model, gain=...) first"
        ) from error
    except IsADirectoryError as error:
        raise IntegrityError(f"Bank or descriptor is a directory: {error.filename}") from error
    try:
        descriptor = json.loads(raw_descriptor, object_pairs_hook=_unique_object)
        _validate_descriptor(descriptor, name)
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise IntegrityError(f"Invalid bank descriptor: {descriptor_path}: {error}") from error
    return descriptor


def _read_generated(name: str) -> bytes:
    descriptor = _generated_descriptor(name)
    bank_path = cache_dir() / "generated" / name
    try:
        content = bank_path.read_bytes()
    except (FileNotFoundError, NotADirectoryError) as error:
        raise BankNotAvailable(f"Bank {name} disappeared; call certoutage.prepare(model, gain=...) first") from error
    if sha256(content).hexdigest() != descriptor["sha256"]:
        raise IntegrityError(f"SHA-256 digest mismatch: {bank_path}")
    if len(content) != descriptor["bytes"]:
        raise IntegrityError(f"Byte count mismatch: {bank_path}")
    return content


def _is_embedded(name: str) -> bool:
    return name in manifest() and name not in _FORCED.get()


def _read_fetched(name: str) -> bytes:
    raise NotImplementedError("Verified fetched banks are planned for version 0.4.0: " + name)


def _resolve(name: str) -> tuple[bytes, str]:
    if _is_embedded(name):
        content = files("certoutage").joinpath("data", name).read_bytes()
        if sha256(content).hexdigest() != manifest()[name]["sha256"]:
            raise IntegrityError(f"SHA-256 digest mismatch: {name}")
        return content, "embedded"
    if _GENERATED_NAME.fullmatch(name):
        return _read_generated(name), "generated"
    from ._prepare import _stored_name
    return _read_generated(_stored_name(name)), "generated"


def verified_bytes(name: str) -> bytes:
    return _resolve(name)[0]


def arrays(name: str) -> dict[str, np.ndarray]:
    content = verified_bytes(name)
    try:
        with np.load(BytesIO(content), allow_pickle=False) as data:
            result = {key: data[key] for key in data.files}
        if not _is_embedded(name):
            from ._prepare import _metadata
            _validate_structure(result, _metadata(name))
    except (ValueError, KeyError, TypeError, ZeroDivisionError, OverflowError,
            OSError, EOFError, zipfile.BadZipFile) as error:
        from ._prepare import _LOGICAL
        if not (_GENERATED_NAME.fullmatch(name) or
                (_LOGICAL.fullmatch(name) and not _is_embedded(name))):
            raise
        raise IntegrityError(f"Invalid bank structure: {name}: {error}") from error
    for arr in result.values():
        arr.flags.writeable = False
    return result


def _validate_structure(data: dict[str, np.ndarray], descriptor: dict) -> None:
    """Validate production families, including identity scalars and grids.

    The generic S09 store also accepts other families for internal controls;
    they do not participate in public logical-name resolution.
    """
    family, p = descriptor["family"], descriptor["parameters"]
    if family not in ("GAIN", "SIG", "CHERNOFF", "SIGC"):
        return
    from ._prepare import _spec
    from ._generate_gain import gain_period
    spec, N, m = _spec(p["logical"])
    if (family != spec["family"] or type(p["N"]) is not int or p["N"] != N
            or type(p["m"]) is not int or p["m"] != m
            or type(p["bits"]) is not int or p["bits"] != 160):
        raise ValueError("N, m, bits or family inconsistent with logical identity")
    expected_parameters = {"logical", "N", "m", "bits"}
    if family in ("GAIN", "CHERNOFF"):
        expected_parameters.add("power")
        if type(p["power"]) is not int or p["power"] != 19:
            raise ValueError("Production gain power must be 19")
    if family == "CHERNOFF":
        expected_parameters.add("stride")
        if type(p["stride"]) is not int or p["stride"] != 8:
            raise ValueError("Production Chernoff stride must be 8")
    if family in ("SIG", "SIGC"):
        from fractions import Fraction
        key = "gain_sha256" if family == "SIG" else "chernoff_sha256"
        expected_parameters.update(("thermal_ratio", key, "common_sha256"))
        ratio = p["thermal_ratio"]
        if type(ratio) is not str or str(Fraction(ratio)) != ratio or Fraction(ratio) < 0:
            raise ValueError("Noncanonical thermal ratio")
        for name in (key, "common_sha256"):
            if type(p[name]) is not str or not _SHA256.fullmatch(p[name]):
                raise ValueError("Invalid input digest")
    if p.keys() != expected_parameters:
        raise ValueError("Unexpected identity parameters")
    shapes = {}
    scalars = {}
    if family in ("GAIN", "CHERNOFF"):
        scalars = dict(N=N, B=gain_period(N))
        if family == "GAIN" and m != 1:
            scalars["m"] = m
        if family == "CHERNOFF":
            scalars["stride"] = 8
        methods = ("exact", "gauss") if family == "GAIN" else ("chernoff",)
        shapes = {method + side: ((1 << 19) + 1,) for method in methods for side in ("_lo", "_hi")}
    else:
        methods = ("exact", "gauss") if family == "SIG" else ("chernoff",)
        size = 1025 if m != 1 else 20481
        shapes = {method: (2, size) for method in methods}
        if m == 1:
            shapes["levels"] = (5121 if family == "SIGC" else 20481,)
        else:
            shapes["units128"] = (1025,)
    if data.keys() != shapes.keys() | scalars.keys():
        raise ValueError("Unexpected array keys")
    for key, value in scalars.items():
        arr = data[key]
        if arr.dtype != np.int64 or arr.shape != () or arr.item() != value:
            raise ValueError(f"Inconsistent identity scalar {key}")
    for key, shape in shapes.items():
        arr = data[key]
        dtype = np.int8 if key == "levels" else np.int64 if key == "units128" else np.float64
        if arr.dtype != dtype or arr.shape != shape or not np.all(np.isfinite(arr)):
            raise ValueError(f"Invalid dtype, shape or finite values for {key}")
        if key == "levels" and not np.all((9 <= arr) & (arr <= 13)):
            raise ValueError("Thermal levels must lie in [9, 13]")
        if key == "units128" and not np.array_equal(arr, np.arange(-4096, 4097, 8, dtype=np.int64)):
            raise ValueError("Invalid Nakagami signal grid")
    for method in methods:
        lo, hi = (data[method + "_lo"], data[method + "_hi"]) if scalars else data[method]
        if not np.all((0 <= lo) & (lo <= hi) & (hi <= 1)):
            raise ValueError(f"Invalid probability bounds for {method}")


def receipt(*names: str) -> tuple[tuple[str, str], ...]:
    from ._prepare import _metadata
    return tuple((meta["name"], meta["sha256"]) for meta in map(_metadata, names))


def _serialize_arrays(arrays: dict[str, np.ndarray]) -> bytes:
    """Write sorted NPY entries with fixed ZIP metadata and no pickle."""
    if not isinstance(arrays, dict) or any(
        not isinstance(key, str) or not _ARRAY_KEY.fullmatch(key) for key in arrays
    ):
        raise TypeError("Bank arrays must be a dictionary with keys matching [A-Za-z0-9_]{1,64}")
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for key in sorted(arrays):
            array = np.asarray(arrays[key])
            if array.dtype.hasobject:
                raise TypeError(f"Object dtype is not allowed in bank array: {key}")
            entry = BytesIO()
            np.lib.format.write_array(entry, array, allow_pickle=False)
            info = zipfile.ZipInfo(f"{key}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o600 << 16
            info.internal_attr = 0
            archive.writestr(info, entry.getvalue())
    return output.getvalue()


def _same_arrays(content: bytes, expected: dict[str, np.ndarray]) -> bool:
    """Compare decoded NPZ arrays with expected ones: keys, dtype, shape and bytes.

    Undecodable content compares unequal; the caller raises IntegrityError.
    """
    try:
        with np.load(BytesIO(content), allow_pickle=False) as data:
            if sorted(data.files) != sorted(expected):
                return False
            for key in data.files:
                stored, wanted = data[key], np.asarray(expected[key])
                if (stored.dtype != wanted.dtype or stored.shape != wanted.shape
                        or stored.tobytes() != wanted.tobytes()):
                    return False
    except (ValueError, OSError, EOFError, zipfile.BadZipFile):
        return False
    return True


def _replace_with_retry(source: Path, destination: Path) -> None:
    for attempt in range(21):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if os.name != "nt" or attempt == 20:
                raise
            time.sleep(0.05)


def _atomic_write(destination: Path, content: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=destination.parent,
                                         prefix=f".{destination.name}.", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        _replace_with_retry(temporary, destination)
    except BaseException as error:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as cleanup_error:
                raise error from cleanup_error
        raise


def _store_generated(family: str, parameters: dict, generator: dict,
                     arrays: dict[str, np.ndarray]) -> str:
    """Explicit internal writer; the descriptor commits the bank, without a lock.

    The serialized bytes must decode to the requested arrays. A verified
    existing bank is left untouched if its arrays equal the requested ones;
    otherwise, or if the existing pair is invalid, IntegrityError is raised.
    A missing half can be replaced by a complete new pair. Deterministic
    generators let concurrent writers commit identical bank bytes; inconsistent
    generator outputs are detected at the next verified read.
    """
    import flint  # only the writer records the binding version; reads do not need it

    from . import __version__

    name = _generated_name(family, parameters, generator)
    content = _serialize_arrays(arrays)
    if not _same_arrays(content, arrays):
        raise IntegrityError(f"Serialized bank does not reproduce its arrays: {name}")
    try:
        existing = _read_generated(name)
    except BankNotAvailable:
        pass
    else:
        if not _same_arrays(existing, arrays):
            raise IntegrityError(
                f"Stored bank {name} holds different arrays for the same family, parameters "
                "and generator name/version; the generator changed without a new version"
            )
        return name
    descriptor = {
        "schema": 1, "name": name, "sha256": sha256(content).hexdigest(),
        "bytes": len(content), "origin": "generated", "family": family,
        "parameters": parameters, "generator": generator,
        "certoutage_version": __version__, "python_flint_version": flint.__version__,
        "numpy_version": np.__version__,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    directory = cache_dir() / "generated"
    directory.mkdir(parents=True, exist_ok=True)
    _atomic_write(directory / name, content)
    _atomic_write((directory / name).with_suffix(".json"), _canonical_json(descriptor))
    return name
