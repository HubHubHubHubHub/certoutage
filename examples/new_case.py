"""A case absent from the Letter: λ=0.2, η=3, N=16, target 0.002, both conventions.

Cross-check at 192 bits with a doubled DFT; the useful-gain banks stay at 160 bits.
This comparison of precisions is a cross-check, not an independent proof.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from time import perf_counter

from certoutage import Model, Numerics, required_snr, outage_enclosure


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    start = perf_counter()
    cases = []
    for convention in ["C-INR", "C-TX"]:
        model = Model(N=16, lam="0.2", eta=3, convention=convention)
        calculations = []
        for bits, power in [(160, 18), (192, 19)]:
            before = perf_counter()
            numerics = Numerics(precision_bits=bits, ppp_dft_power=power)
            decision = required_snr(model, 1, "0.002", numerics=numerics)
            point = outage_enclosure(model, 1, "3.3125", numerics=numerics)
            calculations.append(dict(precision_bits=bits, ppp_M=1 << power,
                                     decision=asdict(decision), point_3_3125_db=asdict(point),
                                     seconds=perf_counter() - before))
        a, b = calculations
        point_a, point_b = a["point_3_3125_db"], b["point_3_3125_db"]
        overlap = max(point_a["lower"], point_b["lower"]) <= min(point_a["upper"], point_b["upper"])
        stable = a["decision"]["status"] == b["decision"]["status"]
        assert overlap and stable
        assert a["decision"]["status"] == ("feasible" if convention == "C-INR" else "excluded")
        cases.append(dict(model=asdict(model), target="0.002", calculations=calculations,
                          overlapping_enclosures=overlap, same_decision=stable))
    result = dict(cases=cases, wall_seconds=perf_counter() - start,
                  crosscheck="second precision and doubled DFT; shared 160-bit useful-gain banks; not an independent proof")
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(__doc__)
    for case in cases:
        print(case["model"]["convention"])
        for item in case["calculations"]:
            d = item["decision"]
            print(f"  {item['precision_bits']} bits, M={item['ppp_M']}: {d['status']}, "
                  f"threshold [{d['lower_db']}, {d['upper_db']}] dB, "
                  f"floor [{d['floor']['lower']}, {d['floor']['upper']}], {item['seconds']:.3f} s")
    print(f"Total time: {result['wall_seconds']:.3f} s.")


if __name__ == "__main__":
    main()
