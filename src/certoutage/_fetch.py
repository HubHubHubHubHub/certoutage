"""Explicit retrieval of pinned banks; transport never decides what is trusted."""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from importlib.resources import files
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from time import perf_counter
import warnings

from . import _banks
from ._banks import BankNotAvailable, IntegrityError
from ._prepare import PreparedBank, prepare
from .models import Model

BANK_SET_SHA256 = "9be6b78b5e63ac2a422a05f8ec90505a26912a55bda688a43a503f46b45d2a61"
MIRRORS: tuple[str, ...] = ()
_MEMBER = re.compile(r"generated/[A-Z][A-Z0-9]{0,15}_[0-9a-f]{16}\.(?:npz|json)")
_LARGE_BANKS = ("m1_N8.npz", "m1_N64.npz", "m2_N8.npz", "m3_N8.npz", "commun.npz")


class BankDownloadError(BankNotAvailable):
    """An explicit retrieval failed before verified content was available."""


def bank_set() -> dict:
    """Read the package's byte-pinned index, never a remote manifest."""
    content = files("certoutage").joinpath("data/BANK_SET.json").read_bytes()
    if sha256(content).hexdigest() != BANK_SET_SHA256:
        raise IntegrityError("SHA-256 digest mismatch: BANK_SET.json")
    return json.loads(content)


def _large_names(N: int) -> tuple[str, ...]:
    return (("commun.npz",) +
            (("m1_N8.npz", "m2_N8.npz", "m3_N8.npz") if N == 8 else
             ("m1_N64.npz",) if N == 64 else ()))


def _download_bytes(N: int) -> int:
    """Pinned transfer estimate for a refusal message; no network or writes."""
    index = bank_set()
    return (sum(row["bytes"] for row in index["archives"] if row["N"] == N) +
            sum(_banks.manifest()[name]["bytes"] for name in _large_names(N)
                if not _banks._package_available(name)))


def _check_url(url: str) -> None:
    from urllib.parse import urlsplit
    try:
        parts = urlsplit(url)
        if (parts.scheme == "https" and parts.hostname or
                parts.scheme == "http" and parts.hostname in ("127.0.0.1", "::1", "localhost")):
            return
        raise ValueError("HTTPS is required, except for HTTP on a loopback host")
    except ValueError as error:
        raise BankDownloadError(f"Cannot fetch {url}: {error}") from error


def _opener():
    # Lazy imports also allow package import when socket creation is blocked.
    import ssl
    import urllib.request

    class Redirects(urllib.request.HTTPRedirectHandler):
        max_repeats = 5
        max_redirections = 5

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            _check_url(newurl)
            count = getattr(req, "_bank_redirects", 0) + 1
            if count > 5:
                error = ValueError("more than five redirects")
                raise BankDownloadError(f"Cannot fetch {req.full_url}: {error}") from error
            redirected = urllib.request.HTTPRedirectHandler.redirect_request(
                self, req, fp, code, msg, headers, newurl)
            if redirected is not None:
                redirected._bank_redirects = count
            return redirected

    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}), Redirects(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()))


def _transport_error(location: str, error: Exception) -> BankDownloadError:
    reason = getattr(error, "reason", error)
    help_text = ""
    ssl = sys.modules.get("ssl")
    if ssl is not None and isinstance(reason, ssl.SSLCertVerificationError):
        help_text = (" Set SSL_CERT_FILE to a trusted CA bundle (for example from the certifi "
                     "package), or download the files manually and use directory=.")
    return BankDownloadError(f"Cannot fetch {location}: {error}.{help_text}")


def _copy_stream(source, target, pin: dict, location: str, declared: int | None) -> None:
    if declared is not None and declared > pin["bytes"]:
        raise IntegrityError(f"Content-Length exceeds pinned size: {location}")
    digest, count = sha256(), 0
    while count <= pin["bytes"]:
        chunk = source.read(min(1024 * 1024, pin["bytes"] + 1 - count))
        if not chunk:
            break
        target.write(chunk)
        digest.update(chunk)
        count += len(chunk)
    if count > pin["bytes"]:
        raise IntegrityError(f"Byte count exceeds pinned size: {location}")
    if declared is not None and count < declared:
        from http.client import IncompleteRead
        raise IncompleteRead(b"", declared - count)
    if count != pin["bytes"] or digest.hexdigest() != pin["sha256"]:
        raise IntegrityError(f"SHA-256 or byte count mismatch: {location}")


@contextmanager
def _verified_file(pin: dict, locations: tuple[str, ...], directory: Path | None,
                   timeout: float):
    """Yield a verified temporary file, deleting it on every exit path."""
    from . import __version__

    if directory is None and not locations:
        raise BankDownloadError(
            "No published bank location is registered in this development version. "
            "Supply url= or CERTOUTAGE_BANKS_URL, or use directory= for a local deposit.")
    candidates = ((str(directory / pin["file"]),) if directory is not None else
                  tuple(base.replace("{file}", pin["file"]) if "{file}" in base else
                        base.rstrip("/") + "/" + pin["file"] for base in locations))
    failures = []
    last = None
    for location in candidates:
        temporary = None
        transport_errors = (BankDownloadError, OSError, ValueError)
        try:
            if directory is None:
                _check_url(location)
                from http.client import HTTPException
                from urllib.request import Request
                transport_errors += (HTTPException,)
                request = Request(location, headers={"User-Agent": f"certoutage/{__version__}"})
                source = _opener().open(request, timeout=timeout)
            else:
                source = Path(location).open("rb")
            with source:
                declared = source.headers.get("Content-Length") if directory is None else None
                if declared is not None:
                    try:
                        declared = int(declared)
                    except ValueError as error:
                        raise IntegrityError(f"Invalid Content-Length: {location}") from error
                    if declared < 0:
                        raise IntegrityError(f"Invalid Content-Length: {location}")
                destination = _banks.cache_dir() / "fetched"
                destination.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode="wb", dir=destination,
                                                 prefix=".", suffix=".part", delete=False) as out:
                    temporary = Path(out.name)
                    _copy_stream(source, out, pin, location, declared)
            # Yield outside the transport handler: installation errors must not
            # turn into retries against another mirror.
        except transport_errors as error:
            last = _transport_error(location, error)
            last.__cause__ = error
            failures.append(str(last))
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            continue
        except BaseException:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise
        try:
            yield temporary
        finally:
            temporary.unlink(missing_ok=True)
        return
    raise BankDownloadError("All bank locations failed: " + "; ".join(failures)) from last


def _members(archive: dict) -> dict[str, dict]:
    expected = {}
    for bank in archive["banks"]:
        name = "generated/" + bank["stored_name"]
        expected[name] = {"bytes": bank["bytes"], "sha256": bank["sha256"]}
        expected[name[:-4] + ".json"] = {
            "bytes": bank["descriptor_bytes"], "sha256": bank["descriptor_sha256"]}
    return expected


def _validated_archive(path: Path, pin: dict) -> dict[str, bytes]:
    try:
        import lzma
    except ImportError as error:
        raise BankDownloadError("Reading bank archives requires Python's lzma module") from error
    import tarfile
    expected = _members(pin)
    try:
        # Bound decompression too. The pinned tar size is at most about 60 MB.
        with lzma.open(path, "rb") as stream:
            raw = stream.read(pin["uncompressed_tar_bytes"] + 1)
        if len(raw) != pin["uncompressed_tar_bytes"]:
            raise IntegrityError(f"Uncompressed archive size mismatch: {pin['file']}")
        with tarfile.open(fileobj=BytesIO(raw), mode="r:") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(expected) or set(names) != set(expected):
                raise IntegrityError(f"Archive member set mismatch: {pin['file']}")
            for member in members:
                if (not member.isreg() or not _MEMBER.fullmatch(member.name)
                        or ".." in member.name or "\\" in member.name
                        or member.name.startswith("/") or member.sparse is not None
                        or member.size != expected[member.name]["bytes"]):
                    raise IntegrityError(f"Invalid archive member: {member.name}")
            contents = {}
            for member in members:
                with archive.extractfile(member) as stream:
                    content = stream.read(member.size + 1)
                if (len(content) != expected[member.name]["bytes"] or
                        sha256(content).hexdigest() != expected[member.name]["sha256"]):
                    raise IntegrityError(f"SHA-256 or byte count mismatch: {member.name}")
                contents[member.name] = content
            # Descriptors commit the pairs, and must describe the pinned bytes.
            for bank in pin["banks"]:
                name = bank["stored_name"]
                descriptor = json.loads(contents["generated/" + name[:-4] + ".json"],
                                        object_pairs_hook=_banks._unique_object)
                _banks._validate_descriptor(descriptor, name)
                if (descriptor["sha256"] != bank["sha256"] or
                        descriptor["bytes"] != bank["bytes"]):
                    raise IntegrityError(f"Descriptor does not match pinned bank: {name}")
            return contents
    except IntegrityError:
        raise
    except (lzma.LZMAError, tarfile.TarError, OSError, EOFError, ValueError, TypeError,
            KeyError, UnicodeError, RecursionError) as error:
        raise IntegrityError(f"Unreadable or invalid archive {pin['file']}: {error}") from error


def _existing(bank: dict) -> dict | None:
    name = bank["stored_name"]
    try:
        # This also validates the structure of a different, locally prepared bank.
        _banks.arrays(name)
        return _banks._generated_descriptor(name)
    except BankNotAvailable:
        return None


def _row(bank: dict, origin: str, started: float, meta: dict | None = None) -> PreparedBank:
    reference = bank if meta is None else meta
    return PreparedBank(bank["logical"], bank["stored_name"], origin,
                        reference["sha256"], reference["bytes"], perf_counter() - started, None)


def _check_ready(sizes: list[int], conflicts: list[str]) -> None:
    missing = []
    for N in sizes:
        for m, gains in ((1, ("exact", "eq3", "chernoff")), (2, ("exact", "eq3")),
                         (3, ("exact", "eq3"))):
            for gain in gains:
                for row in prepare(Model(N=N, m=m), gain=gain, dry_run=True):
                    if row.origin == "missing":
                        missing.append(f"N={N}, m={m}, gain={gain}: {row.logical}")
    if missing:
        reason = (" Existing valid banks were preserved with different pinned bytes: " +
                  ", ".join(conflicts) + "; their input digests can change thermal bank names."
                  if conflicts else " Required banks or their input descriptors are absent.")
        raise BankNotAvailable("Fetch did not make every combination ready: " +
                               "; ".join(missing) + reason)


def fetch_banks(*sizes, url=None, directory=None, timeout=60.0) -> tuple[PreparedBank, ...]:
    """Install pinned banks explicitly, from HTTPS/loopback HTTP or a local deposit.

    Sizes are exact integers in [8, 64] or Model instances. Existing valid
    pairs are preserved, including locally computed Chernoff variants. Every
    requested fading/gain combination must be ready on success. Transport
    errors try the next configured mirror; any integrity error stops at once.
    No public query invokes this function implicitly.
    """
    if not sizes:
        raise ValueError("Supply at least one size; use fetch_banks(*range(8, 65)) for the whole set")
    values = [item.N if isinstance(item, Model) else item for item in sizes]
    if any(type(N) is not int or not 8 <= N <= 64 for N in values):
        raise ValueError("Bank sizes must be exact integers in [8, 64] or Model instances")
    if url is not None and directory is not None:
        raise ValueError("url and directory are mutually exclusive")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a finite positive number of seconds")
    if directory is None and os.environ.get("CERTOUTAGE_OFFLINE", "0") not in ("", "0"):
        raise BankDownloadError("CERTOUTAGE_OFFLINE forbids downloads; use directory= for local files")
    sizes = sorted(set(values))
    index = bank_set()
    locations = ((url,) if url is not None else
                 (os.environ["CERTOUTAGE_BANKS_URL"],) if os.environ.get("CERTOUTAGE_BANKS_URL") else MIRRORS)
    local = None if directory is None else Path(directory)
    archives = [a for a in index["archives"] if a["N"] in sizes]
    names = list(dict.fromkeys(name for N in sizes for name in _large_names(N)))
    result, conflicts = [], []
    # Preflight the complete existing read set before doing any installation.
    existing = {b["stored_name"]: _existing(b) for a in archives for b in a["banks"]}
    available = {}
    for name in names:
        started = perf_counter()
        try:
            _, origin = _banks._resolve(name)
        except BankNotAvailable:
            available[name] = None
        else:
            available[name] = origin
            meta = _banks.manifest()[name]
            result.append(PreparedBank(name, name, "embedded" if origin == "embedded" else "cached",
                                       meta["sha256"], meta["bytes"], perf_counter() - started, None))
    for name in names:
        if available[name] is not None:
            continue
        started = perf_counter()
        pin = dict(_banks.manifest()[name], file=name)
        with _verified_file(pin, locations, local, timeout) as path:
            # A competing installation must be verified, never overwritten.
            try:
                _banks._read_fetched(name)
            except BankNotAvailable:
                _banks._atomic_write(_banks.cache_dir() / "fetched" / name, path.read_bytes())
                origin = "fetched"
            else:
                origin = "cached"
        result.append(PreparedBank(name, name, origin, pin["sha256"], pin["bytes"],
                                   perf_counter() - started, None))
    for archive in archives:
        started = perf_counter()
        contents = None
        if any(existing[b["stored_name"]] is None for b in archive["banks"]):
            with _verified_file(archive, locations, local, timeout) as path:
                contents = _validated_archive(path, archive)
        # Validate every existing pair again before writing any member.
        current = {b["stored_name"]: _existing(b) for b in archive["banks"]}
        for bank in archive["banks"]:
            name = bank["stored_name"]
            meta = current[name]
            if meta is not None:
                if meta["sha256"] != bank["sha256"] or meta["bytes"] != bank["bytes"]:
                    conflicts.append(bank["logical"])
                    warnings.warn(f"Preserving existing valid bank {bank['logical']} ({name}): "
                                  "bytes differ from the pinned set; no replacement", RuntimeWarning, stacklevel=2)
                result.append(_row(bank, "cached", started, meta))
                continue
            if contents is None:
                raise BankNotAvailable(f"Bank {name} disappeared during fetch; retry explicitly")
            destination = _banks.cache_dir() / "generated"
            destination.mkdir(parents=True, exist_ok=True)
            _banks._atomic_write(destination / name, contents["generated/" + name])
            _banks._atomic_write((destination / name).with_suffix(".json"),
                                 contents["generated/" + name[:-4] + ".json"])
            result.append(_row(bank, "fetched", started))
    _check_ready(sizes, conflicts)
    return tuple(result)
