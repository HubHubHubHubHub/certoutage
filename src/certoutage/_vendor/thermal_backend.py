"""Numerical routines for certified Poisson-interference calculations."""
"""Backend Arb : fonctions spéciales, DFT et produits scalaires rigoureux."""
from pathlib import Path
import math, json, time, hashlib, csv
import numpy as np
from flint import arb, acb, arb_mat, ctx
M = 1 << 19
GAMMA_FALLBACKS = 0

def outward(x):
    if not x.is_finite():
        raise ArithmeticError(f"Boule Arb non finie : {x}")
    lo = x.lower()
    hi = x.upper()
    a = np.nextafter(float(lo), -np.inf)
    b = np.nextafter(float(hi), np.inf)
    if not (arb(float(a)) <= lo and arb(float(b)) >= hi):
        raise ArithmeticError(f"Transport binaire64 non extérieur : {x}, {a}, {b}")
    return (a, b)

def hull(lo, hi):
    return arb(float(lo)).union(arb(float(hi)))

def L(s):
    s = acb(s)
    q = s / 2
    d = q * q - 1
    w = d.sqrt()
    return (q * (q + w).log() / w - 1) / d

def normal(x):
    return (-x / arb(2).sqrt()).erfc() / 2

def density(x):
    return (-x * x / 2).exp() / (2 * arb.pi()).sqrt()

def dump_csv(path, rows):
    if not rows:
        return
    with Path(path).open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)

def tighten(lo, hi):
    lo = np.maximum.accumulate(np.clip(lo, 0, 1))
    hi = np.minimum.accumulate(np.clip(hi, 0, 1)[::-1])[::-1]
    if not np.all(lo <= hi):
        raise ArithmeticError("CDF incohérente : borne inférieure au-dessus de la borne supérieure")
    return (lo, hi)

def gamma_cdf(x, k):
    global GAMMA_FALLBACKS
    if x.is_zero():
        return arb(0)
    if x > 2 * k + 100:
        t = (-x / 2 + k * arb(2).log()).exp()
        return arb(1) - arb(0).union(t)
    value = x.gamma_lower(k, regularized=True)
    if value.is_finite():
        return value
    GAMMA_FALLBACKS += 1
    return gamma_series(x, k)

def gamma_series(x, k):
    if not (x > 0 and k > 0):
        raise ArithmeticError(f"Série Gamma : x et k doivent être strictement positifs ({x}, {k})")
    term = total = arb(1)
    for n in range(10000):
        ratio = x / (k + n + 1)
        if ratio < 1:
            remainder = term * ratio / (1 - ratio)
            if remainder < total * arb(2) ** (-150):
                return (k * x.log() - x - (k + 1).lgamma()).exp() * (total + arb(0).union(remainder.upper()))
        term *= ratio
        total += term
    raise ArithmeticError(('Gamma positive series did not close', x, k))

def common():
    start = time.perf_counter()
    Path('banques').mkdir(exist_ok=True)
    Path('resultats').mkdir(exist_ok=True)
    z = np.arange(-12 * 8192, 12 * 8192 + 1, dtype=float) / 8192
    ph = np.array([outward(density(arb(float(x)))) for x in z]).T
    outside = outward(2 * density(arb(12)) / 12)[1]
    np.savez('banques/commun.npz', z=z, phi=ph, outside=outside)
    r = dict(seconds=time.perf_counter() - start, prec=ctx.prec, sha256=hashlib.sha256(Path('banques/commun.npz').read_bytes()).hexdigest())
    Path('resultats/preparation.json').write_text(json.dumps(r, indent=2) + '\n')
    print('Arb commun', r, flush=True)

class Thermal:

    def __init__(self, N):
        self.N = N
        with np.load('banques/N%d.npz' % N) as f:
            self.bank = {k: f[k] for k in f.files}
        self.B = int(self.bank['B'])
        self.dx = self.B / M
        self.common = np.load('banques/commun.npz')
        self.levels = {}
        self.weights = {}
        self.arb_values = {}
        for name in ['exact', 'gauss']:
            self.arb_values[name] = ([arb(float(x)) for x in self.bank[name + '_lo']], [arb(float(x)) for x in self.bank[name + '_hi']])
        for J in range(9, 14):
            step = 1 << 13 - J
            z = self.common['z'][::step]
            ph = self.common['phi'][:, ::step]
            left = np.abs(10 + z[:-1])
            right = np.abs(10 + z[1:])
            tmin = np.minimum(left, right)
            tmax = np.maximum(left, right)
            ml = [(arb(float(x)) / (1 << J)).lower() for x in np.minimum(ph[0, :-1], ph[0, 1:])]
            mh = [(arb(float(x)) / (1 << J)).upper() for x in np.maximum(ph[1, :-1], ph[1, 1:])]
            self.levels[J] = (tmin, tmax, (ml, mh))
            self.weights[J] = (arb_mat([ml]), arb_mat([mh]))

    def amplitude(self, db, user):
        d = arb(str(db))
        ci = arb(10) / 3 if user == 1 else arb(5) / 2
        lam = arb(1) / (8 if user == 1 else 64)
        return outward((101 * ci / ((d * arb(10).log() / 10).exp() * lam)).sqrt())

    def indices(self, aa, J):
        tmin, tmax, _ = self.levels[J]
        al = np.maximum(0, np.nextafter(aa[0] / tmax, -np.inf))
        with np.errstate(divide='ignore'):
            ah = np.nextafter(aa[1] / tmin, np.inf)
        il = np.minimum(M, np.floor(np.maximum(0, np.nextafter(al / self.dx, -np.inf)))).astype(np.int64)
        ih = np.minimum(M, np.ceil(np.maximum(0, np.nextafter(ah / self.dx, np.inf)))).astype(np.int64)
        return (il, ih)

    def point(self, db, user=1, methods=('exact',), goal=0.008):
        aa = self.amplitude(db, user)
        out = {}
        for J in range(9, 14):
            il, ih = self.indices(aa, J)
            wl, wh = self.weights[J]
            length = len(il)
            for name in methods:
                lv, hv = self.arb_values[name]
                lo = (wl * arb_mat(length, 1, [lv[int(i)] for i in il]))[0, 0]
                hi = (wh * arb_mat(length, 1, [hv[int(i)] for i in ih]))[0, 0] + arb(float(self.common['outside']))
                out[name] = (max(0.0, outward(lo)[0]), min(1.0, outward(hi)[1]))
            a, b = out[methods[0]]
            if a > 0 and arb(float(b)) - arb(float(a)) <= arb(str(goal)) * arb(float(a)):
                break
        return (out, J)
