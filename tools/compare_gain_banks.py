#!/usr/bin/env python3
"""Compare gain/signal banks with the lossless v7 array and file digests.

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


def compare(archive, generated, *, packaged=None):
    references = {Path(e["file"]).name: e for e in json.loads(
        (archive / "campaigns/t23/COMPRESSION_LOSSLESS.json").read_text(encoding="utf-8"))}
    rows = {}
    for path in sorted(generated.glob("*.npz")):
        match = re.fullmatch(r"(N|SIG_)(\d+)\.npz", path.name)
        if not match:
            continue
        if path.name not in references:
            raise ValueError(f"No archived reference for {path.name}")
        ref = references[path.name]
        keys = GAIN_KEYS if match[1] == "N" else SIGNAL_KEYS
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
        six_only = match[1] == "N" and int(match[2]) in (8, 16, 32, 64) and set(actual_keys) == set(GAIN_KEYS)
        original_equal = digest == ref["original_sha256"]
        compressed_equal = digest == ref.get("compressed_sha256")
        reference_itself = path.resolve() == (archive / "campaigns/t23" / ref["file"]).resolve()
        row = dict(arrays=arrays, sha256=digest,
                   original_file="identical" if original_equal else "different",
                   expected_original_file="different" if six_only else "identical",
                   compressed_reference=compressed_equal,
                   file_ok=(not original_equal if six_only else original_equal or (reference_itself and compressed_equal)))
        if packaged is not None and match[1] == "SIG_":
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--json", type=Path, help="JSON destination (default: generated/comparison.json)")
    parser.add_argument("--packaged", type=Path, help="also compare signal arrays with a package data directory")
    args = parser.parse_args()
    result = compare(args.archive, args.generated, packaged=args.packaged)
    for name, row in result["banks"].items():
        print(name, " ".join(f"{key}={value['status']}" for key, value in row["arrays"].items()),
              f"file={row['original_file']} expected={row['expected_original_file']}")
    (args.json or args.generated / "comparison.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
