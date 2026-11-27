"""Certified Rayleigh Chernoff comparator with a noncertifying float guess."""
from __future__ import annotations

import math
import numpy as np
from numpy.polynomial.polynomial import polyval, polyder
from flint import arb

from ._nakagami import integrals, mu
from ._generate_gain import _integer, gain_period
from ._vendor.commun import out
from ._vendor.thermal_backend import tighten


def M2():
    """Historical moment coefficients, built at the caller's precision."""
    values = [arb(1) / 3]
    for r in range(100):
        values.append(values[-1] * (r + 2)**2 / (4 * (arb(r) + arb('2.5'))))
    return values


def moments(t):
    """Enclose the first three tilted moments, including the t=2 series."""
    t = arb(t)
    if abs(t - 2) < arb('.8'):
        h = t - 2
        answer = []
        coefficients = M2()
        for j in range(3):
            term = total = coefficients[j]
            for n in range(1, 65):
                term *= (-h) * (n + j + 1)**2 / (4 * (arb(n + j) + arb('1.5')) * n)
                total += term
            nex = abs(term * h * arb(66 + j)**2 / (4 * (arb(65 + j) + arb('1.5')) * 65))
            # For n>=65, j<=2, |h|<.8, subsequent ratios are <.3.
            answer.append(total + arb(0, (nex / arb('.7')).upper()))
        return answer
    return [4*x.real for x in integrals(t, 1, 3)[1:4]]


# These binary64 coefficients and the root search are NOT certifying.
# Only the Arb moment signs below authorize the returned enclosure.
_nomcoeff = np.array([4*np.sqrt(np.pi)*np.exp(
    2*math.lgamma(j+2)-(j+2)*np.log(4)-math.lgamma(j+2.5)-math.lgamma(j+1))*(-1)**j
    for j in range(35)])
_nomder = polyder(_nomcoeff)


def nominal_mean(t):
    if abs(t-2) < .8:
        return -polyval(t-2, _nomder)/polyval(t-2, _nomcoeff)
    q = t/2
    d = q*q-1
    j0 = (np.arccosh(q)/np.sqrt(d) if q>1 else np.arccos(q)/np.sqrt(-d))/2
    l0 = (2*q*j0-1)/d
    return -(4*j0-3*t*l0)/((t*t-4)*l0)


def _bisect_guess(target, N, a):
    low, high = 0., max(4., 4*N/a)
    for _ in range(160):
        mid = (low+high)/2
        if high-low <= 1e-12 or mid == low or mid == high:
            return mid
        if nominal_mean(mid) > target:
            low = mid
        else:
            high = mid
    raise ArithmeticError("The noncertifying Chernoff root search did not terminate")


def chernoff_value(a, N, *, _guess=None):
    """Return (Arb comparator enclosure, certified root bracket or None).

    Uses the caller's arithmetic context. ``_guess(target,N,a)`` is a private
    control hook for replaying a historical floating-point initial guess;
    it cannot bypass the certified sign checks. Bounds concern the Chernoff
    comparator, not two-sided bounds on the physical outage.
    """
    N = _integer(N, "N", 8, 64)
    a = arb(a)
    if not a.is_finite() or not a >= 0:
        raise ValueError("a must be finite and nonnegative")
    mean = N * mu(1)
    if a.is_zero():
        return arb(0), None
    if a >= mean:
        return arb(1), None
    if not a < mean:
        raise ArithmeticError("Cannot decide which side of the mean contains a")
    guess = float((_bisect_guess if _guess is None else _guess)(float(a/N), N, float(a)))
    if not math.isfinite(guess) or guess < 0:
        raise ArithmeticError("Invalid noncertifying Chernoff initial guess")
    radius = 1e-10*(1+guess)
    for _ in range(9):
        tl = max(0., np.nextafter(guess-radius, -np.inf))
        th = np.nextafter(guess+radius, np.inf)
        ml, mh = moments(float(tl)), moments(float(th))
        if ml[1]/ml[0] > a/N and mh[1]/mh[0] < a/N:
            break
        radius *= 10
    else:
        raise ArithmeticError(f"Chernoff root signs could not be certified for N={N}, a={a}")
    lower = (arb(float(tl))*a + N*mh[0].log()).exp().lower()
    upper = (arb(float(th))*a + N*ml[0].log()).exp().upper()
    return lower.union(upper).min(1), dict(s_lower=float(tl), s_upper=float(th))


class _ChernoffBank(dict):
    """Bank arrays only in mapping keys; separate root-count diagnostics."""

    def __init__(self, arrays, diagnostics):
        dict.__init__(self, arrays)
        self.diagnostics = diagnostics


def chernoff_arrays(N, *, stride=8, power=19, bits=160, _guess=None) -> dict:
    """Return five bank arrays; root statistics are in ``.diagnostics``.

    ``power`` is a private reduced-grid test parameter. Production and tests
    use stride 8. No diagnostic is serialized as a bank array.
    """
    N = _integer(N, "N", 8, 64)
    stride = _integer(stride, "stride", 8, 8)
    power = _integer(power, "power", 10, 19)
    from ._runtime import arithmetic
    with arithmetic(bits):
        M = 1 << power
        B = gain_period(N)
        K = M//stride
        values = np.empty((2, K+1))
        roots, max_s_interval = 0, 0.
        for j in range(K+1):
            value, root = chernoff_value(arb(j)*B/K, N, _guess=_guess)
            values[:, j] = out(value)
            if root:
                roots += 1
                max_s_interval = max(max_s_interval, root['s_upper']-root['s_lower'])
        values[:, 0] = 0
        values[0], values[1] = tighten(*values)
        il = np.arange(M+1)//stride
        ih = (np.arange(M+1)+stride-1)//stride
        arrays = dict(chernoff_lo=values[0, il], chernoff_hi=values[1, ih],
                      B=np.array(B, dtype=np.int64), N=np.array(N, dtype=np.int64),
                      stride=np.array(stride, dtype=np.int64))
        return _ChernoffBank(arrays, dict(roots=roots, max_s_interval=max_s_interval))
