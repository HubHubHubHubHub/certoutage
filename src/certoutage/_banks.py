"""Chargement sans écriture et sans réseau, vérification avant désérialisation."""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
from io import BytesIO
import json

import numpy as np

MANIFEST_SHA256 = "0397d274f08924027840943648ca0816a4403832bace47a79642dee7cc7c5c18"


class IntegrityError(RuntimeError):
    """Une banque fournie ou son manifeste ne correspond pas à son empreinte."""


@lru_cache(maxsize=1)
def manifest() -> dict:
    content = files("certoutage").joinpath("data/MANIFEST.json").read_bytes()
    if sha256(content).hexdigest() != MANIFEST_SHA256:
        raise IntegrityError("Empreinte SHA-256 incorrecte : MANIFEST.json")
    return json.loads(content)


def verified_bytes(name: str) -> bytes:
    if name not in manifest():
        raise ValueError(f"Banque non fournie : {name}")
    content = files("certoutage").joinpath("data", name).read_bytes()
    if sha256(content).hexdigest() != manifest()[name]["sha256"]:
        raise IntegrityError(f"Empreinte SHA-256 incorrecte : {name}")
    return content


def arrays(name: str) -> dict[str, np.ndarray]:
    with np.load(BytesIO(verified_bytes(name)), allow_pickle=False) as data:
        result = {key: data[key] for key in data.files}
    for arr in result.values():
        arr.flags.writeable = False
    return result


def receipt(*names: str) -> tuple[tuple[str, str], ...]:
    return tuple((name, manifest()[name]["sha256"]) for name in names)
