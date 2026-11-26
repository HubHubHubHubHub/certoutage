# Corrected public runtime: explicit domain guard; see CORRECTIONS.md.
"""Numerical routines for certified Poisson-interference calculations."""
from .commun import *

def require_eta(eta):
    if eta not in (3, 4):
        raise ValueError("Implemented path-loss exponents are eta=3 or eta=4")
    return eta

def J(s, eta):
    require_eta(eta)
    s = acb(s)
    if eta == 4:
        rt = s.sqrt()
        return rt / 2 * rt.atan()
    t = 1 / s ** (arb(1) / 3)
    rt3 = arb(3).sqrt()
    return s ** (arb(2) / 3) * (arb.pi() / (2 * rt3) + (t + 1).log() / 3 - (t * t - t + 1).log() / 6 - ((2 * t - 1) / rt3).atan() / rt3)

def transform(s, lam, eta):
    return (-2 * arb.pi() * arb(str(lam)) * J(s, eta)).exp()

def envelopes(cdf_lo, cdf_hi, xlo, xhi):
    """Two genuine discrete stochastic envelopes, not independent mass bounds."""
    L = np.maximum.accumulate(np.clip(cdf_lo, 0, 1))
    U = np.minimum.accumulate(np.clip(cdf_hi, 0, 1)[::-1])[::-1]
    if not (np.all(L <= U) and L[0] == 0 and U[0] == 0):
        raise ArithmeticError("Inconsistent CDFs: crossed envelopes or nonzero origin")
    wl = [arb(float(b)) - arb(float(a)) for a, b in zip(np.r_[0.0, U[1:]], np.r_[U[1:], 1.0])]
    wh = [arb(float(b)) - arb(float(a)) for a, b in zip(np.r_[0.0, L[:-1]], L)]
    if not all(v >= 0 for v in wl + wh):
        raise ArithmeticError("Envelope masses must be nonnegative")
    return (wl, wh, arb(1) - arb(float(L[-1])))
