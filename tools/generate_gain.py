#!/usr/bin/env python3
"""Generate Rayleigh gain and optional signal banks in a new or empty directory."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import resource
import sys
import time

import flint
import numpy as np

from certoutage import _banks
from certoutage._generate_gain import gain_arrays, signal_arrays, signal_points, finish_signal


def _write(path, arrays, seconds):
    np.savez(path, **arrays)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    metadata = dict(
        seconds=seconds, peak_rss_bytes=int(rss if sys.platform == "darwin" else rss * 1024),
        peak_rss_scope="process lifetime", python=platform.python_version(),
        python_flint=flint.__version__, numpy=np.__version__,
        sha256=sha256(path.read_bytes()).hexdigest(),
        arrays={name: dict(dtype=str(a.dtype), shape=list(a.shape), sha256=sha256(a.tobytes()).hexdigest())
                for name, a in arrays.items()})
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(path.name, json.dumps(metadata), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--N", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--signal", action="store_true", help="also generate the complete signal bank")
    mode.add_argument("--points", metavar="A:B", help="generate a raw signal part, stop index excluded")
    mode.add_argument("--merge", nargs="+", type=Path, metavar="PART", help="merge raw parts into a signal bank")
    args = parser.parse_args()
    if not 8 <= args.N <= 64:
        parser.error("N must be in [8, 64]")
    indices = None
    if args.points is not None:
        try:
            start, stop = map(int, args.points.split(":"))
            if not 0 <= start < stop <= 20481:
                raise ValueError
        except ValueError:
            parser.error("points must be A:B with 0 <= A < B <= 20481")
        indices = range(start, stop)
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
        parser.error("output directory must be new or empty")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.merge:
        started = time.perf_counter()
        parts = []
        for path in args.merge:
            with np.load(path, allow_pickle=False) as data:
                if int(data["N"]) != args.N:
                    parser.error("all parts must have the requested N")
                parts.append({name: data[name] for name in ("indices", "exact", "gauss", "levels")})
        signal = finish_signal(parts)
        _write(args.output / f"SIG_{args.N}.npz", signal, time.perf_counter() - started)
        return
    started = time.perf_counter()
    gain = gain_arrays(args.N)
    _write(args.output / f"N{args.N}.npz", gain, time.perf_counter() - started)
    if args.signal or indices is not None:
        started = time.perf_counter()
        common = _banks.arrays("commun.npz")
        if indices is None:
            signal = signal_arrays(gain, common)
            filename = f"SIG_{args.N}.npz"
        else:
            signal = dict(N=np.array(args.N, dtype=np.int64), **signal_points(gain, common, indices))
            filename = f"SIG_{args.N}_points_{start}_{stop}.npz"
        _write(args.output / filename, signal, time.perf_counter() - started)


if __name__ == "__main__":
    main()
