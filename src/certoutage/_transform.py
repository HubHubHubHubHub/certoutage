"""Real-exponent PPP transform and bounds on its analytic inversion error.

Call under the runtime arithmetic context. The historical integer paths are
delegated unchanged. General transforms use C1/C2 and the certified Pfaff
remainder C3 (Johansson, ACM TOMS 45(3), 30, 2019, doi:10.1145/3328732).
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from flint import acb, arb, ctx

from ._vendor import ppp
from ._vendor.commun import out


def eta_value(eta: int | str) -> int | arb:
    """Convert a canonical exponent at current precision; preserve int 3/4."""
    if type(eta) is int and eta in (3, 4):
        return eta
    return arb(eta)


def pfaff_2f1(z, b, *, max_terms: int | None = None) -> acb:
    """Enclose 2F1(1,b;b+1;z) for b>0 and certified |z/(z-1)|<1.

    Sum terms 0,...,N-1 and bound the entire remaining series by
    |T_N|/(1-|q|). A forced term limit returns a wider certified ball.
    Without a limit the stopping target is 2**(-prec) times |sum|.
    """
    z, b = acb(z), arb(b)
    if not b.is_finite() or not b > 0:
        raise ValueError("Pfaff requires a finite b > 0")
    if max_terms is not None and (type(max_terms) is not int or max_terms < 1):
        raise ValueError("max_terms must be a positive integer or None")
    q = z / (z - 1)
    q_bound = q.abs_upper()
    if not q_bound < 1:
        raise ArithmeticError("Pfaff requires a certified |q| < 1")
    total, term = acb(0), acb(1)
    target = arb(2) ** (-ctx.prec)
    n = 0
    while True:
        if ((max_terms is not None and n >= max_terms) or
                term.abs_upper() <= target * total.abs_lower()):
            break
        total += term
        n += 1
        term *= n * q / (b + n)
        if n >= 100000 and max_terms is None:
            raise ArithmeticError("Pfaff series did not reach the requested accuracy")
    remainder = term.abs_upper() / (1 - q_bound)
    error = arb(0, remainder.upper())
    result = (total + acb(error, error)) / (1 - z)
    if not result.is_finite():
        raise ArithmeticError("Non-finite Pfaff enclosure")
    return result


def _hypgeom_2f1(z, b):
    # a+b-c is exactly zero by construction, even for inexact Arb parameters.
    return z.hypgeom_2f1(1, b, 1 + b, abc=True)


def _checked_2f1(z, b, *, allow_fallback: bool) -> acb:
    requested = ctx.prec
    target = arb(2) ** (-arb(requested) / 2)
    for bits in (requested, 2 * requested):
        with ctx.workprec(bits):
            try:
                value = _hypgeom_2f1(z, b)
            except (ValueError, ArithmeticError):
                value = acb("nan")
            if value.is_finite() and value.rad() <= target * value.abs_lower():
                return value
    if not allow_fallback:
        raise ArithmeticError("2F1 failed the finiteness or relative-radius check")
    return pfaff_2f1(z, b)


def J_general(s, ev, *, allow_fallback: bool = True) -> acb:
    """The PPP radial integral on Re(s)>0, using deterministic C1/C2 routing."""
    s, ev = acb(s), arb(ev)
    if not s.is_finite() or not s.real > 0:
        raise ValueError("J_general requires a finite s with Re(s) > 0")
    if not ev.is_finite() or not ev > 2:
        raise ValueError("J_general requires a finite eta > 2")
    alpha = arb(2) / ev
    if float(abs(s).mid()) <= 1:
        result = s / (ev - 2) * _checked_2f1(-s, 1 - alpha, allow_fallback=allow_fallback)
    else:
        hypergeom = _checked_2f1(-1 / s, alpha, allow_fallback=allow_fallback)
        result = arb.pi() * s ** alpha / (ev * (arb.pi() * alpha).sin()) - hypergeom / 2
    if not result.is_finite():
        raise ArithmeticError("Non-finite general PPP radial integral")
    return result


def transform(s, lam, eta: int | str) -> acb:
    """Keep the explicit archive path exactly at canonical int eta=3 or 4."""
    if type(eta) is int and eta in (3, 4):
        return ppp.transform(s, lam, eta)
    result = (-2 * arb.pi() * arb(str(lam)) * J_general(s, eta_value(eta))).exp()
    if not result.is_finite():
        raise ArithmeticError("Non-finite general PPP Laplace transform")
    return result


def _real(value) -> arb:
    return value if isinstance(value, arb) else arb(str(value))


def remainders(lam, eta, power: int) -> tuple[arb, arb]:
    """Return Fourier R and tail tau, before multiplication of R by exp(cx).

    These are the generator's formulas, with B=128 and M=2**power. At
    lambda=0 the Fourier bound is infinite (the runtime uses a zero atom).
    """
    if type(power) is not int or not 6 <= power <= 20:
        raise ValueError("power must be an integer between 6 and 20")
    lv, ev = _real(lam), _real(eta)
    if not lv.is_finite() or not lv >= 0 or not ev.is_finite() or not ev > 2:
        raise ValueError("remainders requires finite lambda >= 0 and eta > 2")
    M, B = 1 << power, 128
    alpha = arb(2) / ev
    beta = arb.pi() ** 2 * lv * alpha / (2 * (arb.pi() * alpha / 2).sin())
    zeta = beta * (arb.pi() * M / B) ** alpha
    freq = (arb("inf") if lv.is_zero() else
            (arb.pi() * lv - zeta).exp() / arb.pi() * (arb(1) / M + 1 / (alpha * zeta)))
    tail = (-arb(B) / 2 + 2 * arb.pi() * lv / (ev - 2)).exp()
    return freq, tail


def informative(lam, eta, power: int, eps_R=1e-7, eps_tau=1e-10) -> bool:
    """Prove the two analytic-width criteria; uncertainty returns False."""
    er, et = _real(eps_R), _real(eps_tau)
    if not er.is_finite() or not et.is_finite() or not er > 0 or not et > 0:
        raise ValueError("informative tolerances must be finite and positive")
    freq, tail = remainders(lam, eta, power)
    return bool(arb(20).exp() * freq <= er and tail <= et)


@dataclass(frozen=True)
class LambdaWindow:
    """Outward binary64 brackets of both boundaries; empty is certified.

    Boundaries are mathematical, before intersection with Model's [0,10].
    None for lambda_R means the tail constraint alone makes the window empty.
    """
    lambda_R: tuple[float, float] | None
    lambda_tau: tuple[float, float]
    empty: bool


def lambda_window(eta, power: int, eps_R=1e-7, eps_tau=1e-10) -> LambdaWindow:
    """Certified monotone bisection for E5, with no binary64 sign decisions."""
    # Raising precision also makes this helper usable from the default context.
    with ctx.workprec(max(160, ctx.prec)):
        ev, er, et = _real(eta), _real(eps_R), _real(eps_tau)
        informative(1, ev, power, er, et)  # Validate all inputs.
        C_tau = arb(64) + et.log()
        tau_bracket = tuple(float(x) for x in out(C_tau * (ev - 2) / (2 * arb.pi())))
        if C_tau <= 0:
            return LambdaWindow(None, tau_bracket, True)
        if not C_tau > 0:
            raise ArithmeticError("Cannot determine the sign of the tail window")

        def sign(value):
            for bits in (ctx.prec, ctx.prec * 2, ctx.prec * 4):
                with ctx.workprec(bits):
                    freq, _ = remainders(arb(value), eta, power)
                    target = _real(eps_R) * (-arb(20)).exp()
                    if freq > target:
                        return 1
                    if freq < target:
                        return -1
            raise ArithmeticError("Cannot certify a bisection sign for lambda_R")

        low, high = 0.0, 1.0
        while sign(high) > 0:
            low, high = high, 2 * high
            if not math.isfinite(high):
                raise ArithmeticError("lambda_R is outside the binary64 range")
        for _ in range(80):
            middle = low + (high - low) / 2
            if middle == low or middle == high:
                break
            if sign(middle) > 0:
                low = middle
            else:
                high = middle
        if low > tau_bracket[1]:
            empty = True
        elif high <= tau_bracket[0]:
            empty = False
        else:
            raise ArithmeticError("Cannot separate the two lambda window boundaries")
        return LambdaWindow((low, high), tau_bracket, empty)
