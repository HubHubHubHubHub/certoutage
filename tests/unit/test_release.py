"""Release metadata agreement and fail-closed bank integrity at the public API."""
from pathlib import Path
import json
import re

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10, declared in the test extra.
    import tomli as tomllib

import pytest

import certoutage
from certoutage import (IntegrityError, Model, clear_cache, floor,
                       outage_enclosure, required_snr, largest_interferer_bound,
                       compare_approximations)
from certoutage import _banks


ROOT = Path(__file__).resolve().parents[2]


def test_release_versions_and_dates_agree():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    citation = (ROOT / "CITATION.cff").read_text()
    changelog = (ROOT / "CHANGELOG.md").read_text()
    cff_version = re.search(r"^version: (\S+)$", citation, re.M).group(1)
    latest_release = re.search(r"^## (\d+\.\d+\.\d+) — (\d{4}-\d{2}-\d{2})$",
                               changelog, re.M)
    assert project["version"] == certoutage.__version__ == cff_version == latest_release[1]
    cff_date = re.search(r"^date-released: (\S+)$", citation, re.M).group(1)
    assert cff_date == latest_release[2]
    codemeta = json.loads((ROOT / "codemeta.json").read_text())
    assert codemeta["version"] == codemeta["softwareVersion"] == project["version"]
    assert codemeta["dateModified"] == cff_date
    assert codemeta["license"] == project["license"]
    assert set(codemeta["keywords"]) == set(project["keywords"])


@pytest.mark.parametrize("corrupt_name", ["MANIFEST.json", "SIG_24.npz", "PPP_l0p1_e4.npz"])
@pytest.mark.parametrize("calculation", [
    lambda: outage_enclosure(Model(), 1, 5),
    lambda: floor(Model(), 1),
    lambda: required_snr(Model(), 1, "1e-5"),
    lambda: compare_approximations(Model(), 1, "1e-5"),
], ids=["outage", "floor", "required-snr", "comparators"])
def test_hash_mismatch_stops_certified_calculations(tmp_path, monkeypatch,
                                                   corrupt_name, calculation):
    """A changed bank/manifest must never produce a result or a decision."""
    real_root = _banks.files("certoutage")
    corrupted = tmp_path / corrupt_name
    original = real_root.joinpath("data", corrupt_name).read_bytes()
    # A one-byte change is enough, even if the original was a valid NPZ/JSON.
    corrupted.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))

    class Resources:
        def joinpath(self, *parts):
            relative = Path(*parts)
            if relative.name == corrupt_name:
                return corrupted
            return real_root.joinpath(*parts)

    clear_cache()
    monkeypatch.setattr(_banks, "files", lambda _: Resources())
    try:
        with pytest.raises(IntegrityError, match=rf"SHA-256.*{re.escape(corrupt_name)}"):
            calculation()
    finally:
        clear_cache()


def test_corrupted_final_certificate_is_rejected_before_json_loading(tmp_path, monkeypatch):
    real_root = _banks.files("certoutage")
    corrupted = tmp_path / "MINORANTS_N24.json"
    # Still valid JSON: rejection must depend on the digest, not the parser.
    corrupted.write_bytes(b'{"made_up_certificate": 0}')

    class Resources:
        def joinpath(self, *parts):
            if Path(*parts).name == corrupted.name:
                return corrupted
            return real_root.joinpath(*parts)

    clear_cache()
    monkeypatch.setattr(_banks, "files", lambda _: Resources())
    try:
        with pytest.raises(IntegrityError, match="SHA-256.*MINORANTS_N24.json"):
            largest_interferer_bound(Model(), 1)
    finally:
        clear_cache()
