"""Regenerate a PPP/Gamma bank into a NEW local file, without network access."""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from certoutage import Model, Numerics
from certoutage._generate import environment_arrays
from certoutage._runtime import arithmetic


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lam', default='0.1')
    parser.add_argument('--eta', type=int, choices=[3, 4], default=4)
    parser.add_argument('--kind', choices=['PPP', 'GAMMA'], default='PPP')
    parser.add_argument('--power', type=int, default=20, help='M=2**power; archive: 20')
    parser.add_argument('--bits', type=int, default=160)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    model = Model(lam=args.lam, eta=args.eta)
    if float(model.lam) <= 0:
        parser.error('lam must be strictly positive for PPP/Gamma generation')
    numerics = Numerics(precision_bits=args.bits, ppp_dft_power=args.power)
    if args.output.exists():
        parser.error('the output file already exists; choose a new path')
    start = perf_counter()
    with arithmetic(numerics.precision_bits):
        data = environment_arrays(model.lam, model.eta, args.power, args.kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # File handle prevents implicit .npz extension and refuses overwrite.
    with args.output.open('xb') as stream:
        np.savez_compressed(stream, **data)
    print(json.dumps(dict(output=str(args.output), lam=model.lam, eta=model.eta,
                          kind=args.kind, M=1 << args.power, bits=args.bits,
                          sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
                          array_sha256={k: hashlib.sha256(v.tobytes()).hexdigest() for k, v in data.items()},
                          seconds=perf_counter()-start), indent=2))


if __name__ == '__main__':
    main()
