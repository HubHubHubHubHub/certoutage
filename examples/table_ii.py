"""Reproduces Table II through the public API and prints the two mean rows."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from fractions import Fraction
import json
import math
from time import perf_counter

from certoutage import Model, compare_approximations


def _outward(value: float, scale: Fraction, places: int, up: bool) -> str:
    """value/scale rounded outward to `places` decimals, in exact rationals (no decimal context)."""
    units = Fraction(value) / scale * 10**places
    n = math.ceil(units) if up else math.floor(units)
    sign, n = ("-" if n < 0 else ""), abs(n)
    if places == 0:
        return f"{sign}{n}"
    return f"{sign}{n // 10**places}.{n % 10**places:0{places}d}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    start = perf_counter()
    model = Model(N=24, lam="0.1", eta=4, convention="C-TX")
    rows = compare_approximations(model, 1, "1e-5")
    rendered = []
    for index, row in enumerate(rows):
        if index == 5:
            value = f"< {_outward(row.floor.upper, Fraction(1, 10**5), 4, up=True)}"
        elif index in (0, 1, 2):
            value = row.floor.format(scale="1e-5", places=3 if index == 2 else 4)
        else:
            value = repr(row.floor.as_dict()) + " (raw probability)"
        rendered.append(dict(label=row.label, display=value,
                             decision=row.diagnostic if row.diagnostic == "falsely feasible" else row.decision.status,
                             diagnostic=row.diagnostic, result=asdict(row)))
    result = dict(model=asdict(model), target="1e-5", units="1e-5",
                  rows=rendered, wall_seconds=perf_counter() - start)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print("Table II — C-TX, N=24, λ=0.1, η=4, user 1, target 1e-5")
    print("The four Table II values are in units of 1e-5.")
    for i in (0, 1, 2, 5, 3, 4):
        row = rendered[i]
        print(f"{row['label']}: {row['display']}; {row['decision']}"
              + ("; masked" if row["diagnostic"] == "masked" else ""))
    gamma = rows[1].decision
    if gamma.status == "feasible" and all(
            x is not None and math.isfinite(x) for x in (gamma.lower_db, gamma.upper_db)):
        print(f"{rows[1].label}: required SNR (threshold) "
              f"[{_outward(gamma.lower_db, Fraction(1), 2, up=False)}, "
              f"{_outward(gamma.upper_db, Fraction(1), 2, up=True)}] dB.")
    else:
        print(f"{rows[1].label}: {gamma.status}, no finite threshold.")
    print("The certificates of the Gamma/mean comparators do not bound the PPP.")
    print(f"Time: {result['wall_seconds']:.3f} s.")


if __name__ == "__main__":
    main()
