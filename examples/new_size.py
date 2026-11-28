"""Prepare a new size, then certify the target 0.002 under both conventions.

The default m=2 plan takes about 75 seconds on one CPU core; local machines
can take 1.3--1.7 times longer. --plan does no calculation and writes nothing.
The thermal ratio remains fixed at 10. Full results include every contract.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from time import perf_counter

from certoutage import Model, prepare, floor, required_snr, largest_interferer_bound


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--N", type=int, default=21)
    parser.add_argument("--m", type=int, default=2)
    parser.add_argument("--gain", choices=("exact", "eq3", "chernoff"), default="exact")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    start = perf_counter()
    model = Model(N=args.N, m=args.m, lam="0.2", eta=3)
    plan = prepare(model, gain=args.gain, dry_run=True)
    estimate = [sum(row.estimated_seconds[i] for row in plan) for i in (0, 1)]
    cost = (f"Estimated preparation: {estimate[0]:g}--{estimate[1]:g} seconds on one CPU core; "
            "local machines can take 1.3--1.7 times longer.")
    if not args.json:
        print(cost, flush=True)
    result = dict(expected_cost=cost, estimated_seconds=estimate, plan_only=args.plan,
                  gain=args.gain, target="0.002", plan=[asdict(row) for row in plan])
    if args.plan:
        result["prepared"] = []
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for row in plan:
                print(f"  {row.logical}: {row.origin}, {row.estimated_seconds} seconds")
        return
    prepared = prepare(model, gain=args.gain)
    result["prepared"] = [asdict(row) for row in prepared]
    cases = []
    for convention in ("C-INR", "C-TX"):
        current = Model(N=args.N, m=args.m, lam="0.2", eta=3, convention=convention)
        before = perf_counter()
        base = floor(current, 1, gain=args.gain)
        decision = required_snr(current, 1, "0.002", gain=args.gain)
        bound = largest_interferer_bound(current, 1)
        cases.append(dict(model=asdict(current), floor=asdict(base),
                          decision=asdict(decision), largest_interferer=asdict(bound),
                          seconds=perf_counter() - before))
        if not args.json:
            print(f"{convention}: floor {base.format()}, decision {decision.status}, "
                  f"threshold [{decision.lower_db}, {decision.upper_db}] dB, "
                  f"J_max {bound.format()}")
            for label, contract in (("floor", base.contract), ("decision", decision.contract),
                                    ("J_max", bound.contract)):
                print(f"  {label}: source={contract.source}, banks={contract.banks}")
    result.update(cases=cases, wall_seconds=perf_counter() - start)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Total time: {result['wall_seconds']:.3f} s.")


if __name__ == "__main__":
    main()
