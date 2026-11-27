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
from certoutage._generate_gain import (gain_arrays, signal_arrays, signal_points, finish_signal,
    nakagami_signal_arrays, nakagami_signal_points, nakagami_finish_signal,
    chernoff_signal_arrays, chernoff_signal_points, chernoff_finish_signal)
from certoutage._chernoff import chernoff_arrays


def _write(path, arrays, seconds, *, compressed=False, extra=None):
    (np.savez_compressed if compressed else np.savez)(path, **arrays)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    metadata = dict(
        seconds=seconds, peak_rss_bytes=int(rss if sys.platform == "darwin" else rss * 1024),
        peak_rss_scope="process lifetime", python=platform.python_version(),
        python_flint=flint.__version__, numpy=np.__version__,
        sha256=sha256(path.read_bytes()).hexdigest(),
        arrays={name: dict(dtype=str(a.dtype), shape=list(a.shape), sha256=sha256(a.tobytes()).hexdigest())
                for name, a in arrays.items()})
    if extra:
        metadata.update(extra)
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(path.name, json.dumps(metadata), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--N", type=int, required=True)
    parser.add_argument("--chernoff", action="store_true", help="generate the Rayleigh Chernoff comparator")
    parser.add_argument("--m", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--signal", action="store_true", help="also generate the complete signal bank")
    mode.add_argument("--points", metavar="A:B", help="generate a raw signal part, stop index excluded")
    mode.add_argument("--merge", nargs="+", type=Path, metavar="PART", help="merge raw parts into a signal bank")
    args = parser.parse_args()
    if not 8 <= args.N <= 64:
        parser.error("N must be in [8, 64]")
    size = 20481 if args.m == 1 else 1025
    stem = f"SIG_{args.N}" if args.m == 1 else f"SIG_m{args.m}_N{args.N}"
    points_fn = signal_points if args.m == 1 else nakagami_signal_points
    arrays_fn = signal_arrays if args.m == 1 else nakagami_signal_arrays
    finish_fn = finish_signal if args.m == 1 else nakagami_finish_signal
    if args.chernoff:
        if args.m != 1:
            parser.error("Chernoff is defined only for Rayleigh m=1")
        size, stem = 5121, f"SIG_C_{args.N}"
        points_fn, arrays_fn, finish_fn = chernoff_signal_points, chernoff_signal_arrays, chernoff_finish_signal
    methods = ("chernoff",) if args.chernoff else ("exact", "gauss")
    indices = None
    if args.points is not None:
        try:
            start, stop = map(int, args.points.split(":"))
            if not 0 <= start < stop <= size:
                raise ValueError
        except ValueError:
            parser.error(f"points must be A:B with 0 <= A < B <= {size}")
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
                if args.m != 1 and ("m" not in data or int(data["m"]) != args.m):
                    parser.error("all parts must have the requested m")
                parts.append({name: data[name] for name in ("indices", *methods, "levels")})
        signal = finish_fn(parts)
        _write(args.output / (stem + ".npz"), signal, time.perf_counter() - started, compressed=args.m != 1)
        return
    started = time.perf_counter()
    gain = (chernoff_arrays(args.N) if args.chernoff else
            gain_arrays(args.N) if args.m == 1 else gain_arrays(args.N, m=args.m))
    gain_name = f"N{args.N}.npz" if args.m == 1 else f"m{args.m}_N{args.N}.npz"
    if args.chernoff:
        gain_name = f"C_N{args.N}.npz"
    _write(args.output / gain_name, gain, time.perf_counter() - started,
           extra=getattr(gain, "diagnostics", None))
    if args.signal or indices is not None:
        started = time.perf_counter()
        common = _banks.arrays("commun.npz")
        if indices is None:
            signal = arrays_fn(gain, common)
            filename = stem + ".npz"
        else:
            signal = dict(N=np.array(args.N, dtype=np.int64), **points_fn(gain, common, indices))
            if args.m != 1:
                signal = dict(m=np.array(args.m, dtype=np.int64), **signal)
            filename = f"{stem}_points_{start}_{stop}.npz"
        _write(args.output / filename, signal, time.perf_counter() - started, compressed=args.m != 1)


if __name__ == "__main__":
    main()
