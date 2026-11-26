"""Loading with no writes and no network access; verification before deserialization."""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
from io import BytesIO
import json

import numpy as np

MANIFEST_SHA256 = "0397d274f08924027840943648ca0816a4403832bace47a79642dee7cc7c5c18"


class IntegrityError(RuntimeError):
    """A provided bank or its manifest does not match its digest."""


@lru_cache(maxsize=1)
def manifest() -> dict:
    content = files("certoutage").joinpath("data/MANIFEST.json").read_bytes()
    if sha256(content).hexdigest() != MANIFEST_SHA256:
        raise IntegrityError("SHA-256 digest mismatch: MANIFEST.json")
    return json.loads(content)


def verified_bytes(name: str) -> bytes:
    if name not in manifest():
        raise ValueError(f"Bank not provided: {name}")
    content = files("certoutage").joinpath("data", name).read_bytes()
    if sha256(content).hexdigest() != manifest()[name]["sha256"]:
        raise IntegrityError(f"SHA-256 digest mismatch: {name}")
    return content


def arrays(name: str) -> dict[str, np.ndarray]:
    with np.load(BytesIO(verified_bytes(name)), allow_pickle=False) as data:
        result = {key: data[key] for key in data.files}
    for arr in result.values():
        arr.flags.writeable = False
    return result


def receipt(*names: str) -> tuple[tuple[str, str], ...]:
    return tuple((name, manifest()[name]["sha256"]) for name in names)
