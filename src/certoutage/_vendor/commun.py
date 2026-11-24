"""Numerical routines for certified Poisson-interference calculations."""
from pathlib import Path
import json, csv, hashlib, time, os, math
from fractions import Fraction
import numpy as np
from flint import arb, acb, arb_mat, ctx
ROOT = Path(__file__).resolve().parents[1]

def out(x):
    if not x.is_finite():
        raise ArithmeticError(f"Boule Arb non finie : {x}")
    lo = x.lower()
    hi = x.upper()
    a = np.nextafter(float(lo), -np.inf)
    b = np.nextafter(float(hi), np.inf)
    if not (arb(float(a)) <= lo and arb(float(b)) >= hi):
        raise ArithmeticError(f"Transport binaire64 non extérieur : {x}, {a}, {b}")
    return (a, b)

def hull(a, b):
    return arb(float(a)).union(arb(float(b)))

def csvwrite(path, rows):
    if not rows:
        return
    with Path(path).open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)

def jswrite(name, value):
    Path(name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def constant_L():
    C = arb(0)
    for j, a in enumerate([1030, 603, 1090, 304, 30, 1]):
        term = arb(1) if j == 0 else arb(j).sqrt() ** j * (-arb(j) / 2).exp()
        C += a * term
    return C / (4 * (2 * arb.pi()).sqrt())

def moment(lam, eta, R, j):
    return 2 * arb.pi() * arb(str(lam)) * arb.fac_ui(j) * arb(R) ** (2 - j * eta) / (j * eta - 2)

def tail_near(w, lam, eta, R):
    w = arb(w)
    if w.is_zero():
        return arb.pi() * arb(str(lam)) * (R * R - 1)
    alpha = arb(2) / eta
    return 2 * arb.pi() * arb(str(lam)) / eta * w ** (-alpha) * (w.gamma_upper(alpha) - (w * R ** eta).gamma_upper(alpha))

def poisson_tail(kappa, nmax):
    n = arb(nmax + 1)
    if not n > kappa:
        raise ArithmeticError(f"Queue de Poisson : n doit dépasser kappa ({n}, {kappa})")
    return (-kappa + n - n * (n / kappa).log()).exp()

def env_name(lam, eta, p):
    return 'l' + str(lam).replace('.', 'p') + '_e' + str(eta) + '_p' + str(int(round(-math.log10(p))))
