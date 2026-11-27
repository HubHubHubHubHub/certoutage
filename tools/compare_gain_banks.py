#!/usr/bin/env python3
"""Compare gain/signal banks with v7 digests or nodewise Chernoff overlap.

A different gain file is expected for N=8,16,32,64 when only the six common
arrays are present. Compressed reference containers are recognized separately.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

import numpy as np

GAIN_KEYS = ("N", "B", "exact_lo", "exact_hi", "gauss_lo", "gauss_hi")
SIGNAL_KEYS = ("exact", "gauss", "levels")


def compare(archive, generated, *, packaged=None, m=1):
    campaign = "t23" if m == 1 else "t20"
    references = {Path(e["file"]).name: e for e in json.loads(
        (archive / "campaigns" / campaign / "COMPRESSION_LOSSLESS.json").read_text(encoding="utf-8"))}
    rows = {}
    for path in sorted(generated.glob("*.npz")):
        pattern = r"(N|SIG_)(\d+)\.npz" if m == 1 else rf"(m{m}_N|SIG_m{m}_N)(\d+)\.npz"
        match = re.fullmatch(pattern, path.name)
        if not match:
            continue
        if path.name not in references:
            raise ValueError(f"No archived reference for {path.name}")
        ref = references[path.name]
        is_gain = not path.name.startswith("SIG_")
        keys = ((GAIN_KEYS if m == 1 else ("N", "m", *GAIN_KEYS[1:])) if is_gain
                else SIGNAL_KEYS if m == 1 else ("units128", "exact", "gauss"))
        digest = sha256(path.read_bytes()).hexdigest()
        arrays = {}
        with np.load(path, allow_pickle=False) as data:
            actual_keys = data.files
            for name in keys:
                expected = ref["arrays"][name]
                if name not in data:
                    arrays[name] = dict(status="different", reason="missing")
                    continue
                a = data[name]
                actual = dict(dtype=str(a.dtype), shape=list(a.shape), sha256=sha256(a.tobytes()).hexdigest())
                arrays[name] = dict(status="identical" if actual == expected else "different", **actual)
        six_only = m == 1 and match[1] == "N" and int(match[2]) in (8, 16, 32, 64) and set(actual_keys) == set(GAIN_KEYS)
        original_equal = digest == ref["original_sha256"]
        compressed_equal = digest == ref.get("compressed_sha256")
        reference_itself = path.resolve() == (archive / "campaigns" / campaign / ref["file"]).resolve()
        compressed_signal = m != 1 and not is_gain
        row = dict(arrays=arrays, sha256=digest,
                   original_file="identical" if original_equal else "different",
                   expected_original_file=("platform-dependent" if compressed_signal else
                                           "different" if six_only else "identical"),
                   expected_container="original or archived recompression" if compressed_signal else "original",
                   compressed_reference=compressed_equal,
                   file_ok=(original_equal or compressed_equal if compressed_signal else
                            not original_equal if six_only else original_equal or (reference_itself and compressed_equal)))
        if packaged is not None and not is_gain:
            with np.load(packaged / path.name, allow_pickle=False) as data:
                row["packaged_arrays"] = {
                    name: "identical" if (
                        arrays[name].get("sha256") == sha256(data[name].tobytes()).hexdigest()
                        and arrays[name].get("shape") == list(data[name].shape)
                        and arrays[name].get("dtype") == str(data[name].dtype)) else "different"
                    for name in keys}
        row["ok"] = (row["file_ok"] and all(a["status"] == "identical" for a in arrays.values())
                     and all(s == "identical" for s in row.get("packaged_arrays", {}).values()))
        rows[path.name] = row
    if not rows:
        raise ValueError("No gain or signal banks found")
    return dict(ok=all(row["ok"] for row in rows.values()), banks=rows)



def _chernoff_data(path):
    with np.load(path, allow_pickle=False) as stream:
        data = {name: stream[name] for name in stream.files}
    # The central historical generator named these two arrays lower/upper.
    if "lower" in data and "upper" in data:
        data["chernoff_lo"] = data.pop("lower")
        data["chernoff_hi"] = data.pop("upper")
    return data


def compare_chernoff_bank(actual_path, reference_path, *, mode="overlap"):
    """Compare every node, recording bytes and endpoint-relative differences.

    Refinement levels are compared byte for byte but need not agree in overlap
    mode: they describe the chosen quadrature, not the comparator's domain.
    Relative differences exclude endpoints at or below 1e-300.
    """
    if mode not in ("bytes", "overlap"):
        raise ValueError("mode must be bytes or overlap")
    actual, reference = _chernoff_data(actual_path), _chernoff_data(reference_path)
    arrays = {}
    for name, ref in reference.items():
        a = actual.get(name)
        valid = a is not None and a.dtype == ref.dtype and a.shape == ref.shape and np.all(np.isfinite(a))
        arrays[name] = dict(status="identical" if valid and a.tobytes() == ref.tobytes() else "different",
                            compatible=bool(valid))
    compatible = all(row["compatible"] for row in arrays.values())
    overlap = {}
    if compatible:
        pairs = [("chernoff", actual["chernoff"], reference["chernoff"])] if "chernoff" in reference else [
            ("chernoff", np.array([actual["chernoff_lo"], actual["chernoff_hi"]]),
             np.array([reference["chernoff_lo"], reference["chernoff_hi"]]))]
        for method, a, b in pairs:
            valid_bounds = (a.ndim == b.ndim == 2 and a.shape[0] == b.shape[0] == 2
                            and np.all((0 <= a[0]) & (a[0] <= a[1]) & (a[1] <= 1))
                            and np.all((0 <= b[0]) & (b[0] <= b[1]) & (b[1] <= 1)))
            shared = np.maximum(a[0], b[0]) <= np.minimum(a[1], b[1])
            mask = (a > 1e-300) & (b > 1e-300)
            relative = float(np.max(np.abs(a[mask]-b[mask])/np.abs(b[mask]))) if np.any(mask) else 0.
            overlap[method] = dict(nodes=int(a.shape[1]), disjoint=int(np.count_nonzero(~shared)),
                                   overlap=bool(valid_bounds and np.all(shared)),
                                   max_relative_difference=relative)
    equal = all(row["status"] == "identical" for row in arrays.values())
    domain_equal = all(arrays[name]["status"] == "identical" for name in ("N", "B", "stride") if name in arrays)
    ok = compatible and domain_equal and bool(overlap) and all(row["overlap"] for row in overlap.values())
    if mode == "bytes":
        ok = ok and equal
    return dict(ok=bool(ok), arrays_identical=equal, arrays=arrays, overlap=overlap,
                file_identical=sha256(actual_path.read_bytes()).digest() == sha256(reference_path.read_bytes()).digest())


def compare_chernoff(generated, references, *, mode="overlap"):
    rows = {}
    for path in sorted(generated.glob("*.npz")):
        if re.fullmatch(r"(?:C_N|SIG_C_)\d+\.npz", path.name) and (references/path.name).is_file():
            rows[path.name] = compare_chernoff_bank(path, references/path.name, mode=mode)
    if not rows:
        raise ValueError("No matching Chernoff references; no overlap claim can be made")
    return dict(ok=all(row["ok"] for row in rows.values()), banks=rows)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chernoff", action="store_true")
    parser.add_argument("--mode", choices=("bytes", "overlap"), default="overlap")
    parser.add_argument("--m", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--json", type=Path, help="JSON destination (default: generated/comparison.json)")
    parser.add_argument("--packaged", type=Path, help="also compare signal arrays with a package data directory")
    args = parser.parse_args()
    if args.chernoff:
        if args.packaged is None:
            parser.error("--chernoff requires --packaged as the reference directory")
        result = compare_chernoff(args.generated, args.packaged, mode=args.mode)
    else:
        result = compare(args.archive, args.generated, packaged=args.packaged, m=args.m)
    for name, row in result["banks"].items():
        print(name, " ".join(f"{key}={value['status']}" for key, value in row["arrays"].items()),
              (f"overlap={row['overlap']}" if args.chernoff else
               f"file={row['original_file']} expected={row['expected_original_file']}"))
    (args.json or args.generated / "comparison.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
