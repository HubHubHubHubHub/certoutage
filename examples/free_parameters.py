"""A case with free parameters (since 0.3.0): link, gain and real eta.

Powers p1=0.25, p2=0.75 with two decoding thresholds, useful path gains
1/10 and 1/50, interference gain g=1/2, lambda=0.5 and eta=3.7, N=24
Rayleigh elements. For both power conventions and both users, the script
prints the derived link coefficients, the certified floor, the dimensioning
decision for a target outage of 10^-3, and whether (lambda, eta, M) lies in
the informative domain D_M, with the PPP inversion on M = 2^18 points. The
bounds are certified for this model, conditionally on docs/CONTRACT.md and
on the provisional proofs of docs/PROOFS.md.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from time import perf_counter

from certoutage import Model, Numerics, floor, required_snr

LINK = dict(p1="0.25", p2="0.75", theta1="1.5", theta2=2, ell1="1/10", ell2="1/50")
TARGET = "0.001"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    start = perf_counter()
    numerics = Numerics(ppp_dft_power=18)
    rows = []
    for convention in ("C-INR", "C-TX"):
        model = Model.from_link(**LINK, N=24, m=1, lam="0.5", eta="3.7", g="1/2",
                                convention=convention)
        for user in (1, 2):
            base = floor(model, user, numerics=numerics)
            decision = required_snr(model, user, TARGET, numerics=numerics)
            notes = decision.contract.notes if decision.contract else base.contract.notes
            rows.append(dict(convention=convention, user=user, d1=model.d1, d2=model.d2,
                             floor=[base.lower, base.upper], status=decision.status,
                             threshold_db=[decision.lower_db, decision.upper_db],
                             domain=[n for n in notes if "D_M" in n],
                             decision=asdict(decision)))
    result = dict(model=dict(LINK, N=24, m=1, lam="0.5", eta="3.7", g="1/2"), target=TARGET,
                  rows=rows, wall_seconds=perf_counter() - start)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return
    print(__doc__)
    first = rows[0]
    print(f"Link coefficients: d1={first['d1']}, d2={first['d2']}")
    for row in rows:
        print(f"{row['convention']}, user {row['user']}: floor {row['floor']}, "
              f"{row['status']}, threshold {row['threshold_db']} dB")
        for note in row["domain"]:
            print(f"  {note}")
    print(f"Total time: {result['wall_seconds']:.1f} s.")


if __name__ == "__main__":
    main()
