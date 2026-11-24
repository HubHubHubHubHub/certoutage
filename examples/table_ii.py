"""Reproduit la Table II par l'API publique et affiche les lignes moyenne."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal, ROUND_CEILING
import json
from time import perf_counter

from certoutage import Model, compare_approximations


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
            upper = (Decimal.from_float(row.floor.upper) / Decimal("1e-5")).quantize(Decimal("0.0001"), rounding=ROUND_CEILING)
            value = f"< {upper}"
        elif index in (0, 1, 2):
            value = row.floor.format(scale="1e-5", places=3 if index == 2 else 4)
        else:
            value = repr(row.floor.as_dict()) + " (probabilité brute)"
        rendered.append(dict(label=row.label, display=value,
                             decision=row.diagnostic if row.diagnostic == "falsely feasible" else row.decision.status,
                             diagnostic=row.diagnostic, result=asdict(row)))
    result = dict(model=asdict(model), target="1e-5", units="1e-5",
                  rows=rendered, wall_seconds=perf_counter() - start)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print("Table II — C-TX, N=24, λ=0.1, η=4, usager 1, cible 1e-5")
    print("Les quatre valeurs de la Table II sont en unités de 1e-5.")
    for i in (0, 1, 2, 5, 3, 4):
        row = rendered[i]
        print(f"{row['label']}: {row['display']}; {row['decision']}"
              + ("; masked" if row["diagnostic"] == "masked" else ""))
    print("Exact gain + Gamma : required SNR (threshold) [4.50, 4.75] dB.")
    print("Les certificats des comparateurs Gamma/moyenne ne bornent pas le PPP.")
    print(f"Temps : {result['wall_seconds']:.3f} s.")


if __name__ == "__main__":
    main()
