"""Adapters with no chdir, no access to the archive and no permanent global change."""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from fractions import Fraction
import threading

import numpy as np
from flint import arb, arb_mat, ctx

from . import _banks
from .models import Model, Numerics
from ._vendor.commun import out, moment
from ._vendor.oracles import Signal as OriginalSignal, Environment as OriginalEnvironment
from ._vendor.oracles import down, up
from ._vendor.ppp import envelopes
from ._vendor.nak_thermal import Thermal as OriginalThermal
from ._vendor.nak_grouped import Grouped
from ._vendor.thermal_backend import outward
from ._generate import environment_arrays
from ._transform import eta_value

_LOCK = threading.RLock()


def scale_outward(yl: np.ndarray, yh: np.ndarray,
                  factor: Fraction) -> tuple[np.ndarray, np.ndarray]:
    """Enclose nonnegative binary64 arguments times an exact rational factor.

    The identity returns the original arrays. Exactly representable factors
    retain the historical down(yl*f), up(yh*f) operations, including f=6.
    """
    if factor == 1:
        return yl, yh
    if factor == 0:
        return np.zeros_like(yl), np.zeros_like(yh)
    f = float(factor)
    represented = Fraction(f)
    flo = np.nextafter(f, -np.inf) if represented > factor else f
    fhi = np.nextafter(f, np.inf) if represented < factor else f
    with np.errstate(over="ignore", under="ignore"):
        return down(yl * flo), up(yh * fhi)


def scale_grid_outward(grid: np.ndarray, factor: Fraction) -> tuple[np.ndarray, np.ndarray]:
    """Keep exact grid products unchanged; otherwise transport outward."""
    if factor == 1:
        return grid, grid
    with np.errstate(over="ignore", under="ignore"):
        products = grid * float(factor)
    if all(np.isfinite(product) and Fraction(float(product)) == Fraction(float(x)) * factor
           for x, product in zip(grid, products)):
        return products, products
    return scale_outward(grid, grid, factor)


@contextmanager
def arithmetic(bits: int):
    # Arb has process-global settings. Our calls serialize and restore them.
    # Other code changing ctx concurrently must use separate processes.
    with _LOCK:
        prec, threads = ctx.prec, ctx.threads
        ctx.prec, ctx.threads = bits, 1
        try:
            yield
        finally:
            ctx.prec, ctx.threads = prec, threads


class Signal(OriginalSignal):
    def __init__(self, N: int, m: int, chernoff: bool = False):
        self.N = N
        name = f"SIG_{N}.npz" if m == 1 else f"SIG_m{m}_N{N}.npz"
        z = _banks.arrays(name)
        self.names = [name]
        data = {key: z[key] for key in ["exact", "gauss"]}
        if chernoff:
            extra = f"SIG_C_{N}.npz"
            data["chernoff"] = _banks.arrays(extra)["chernoff"]
            self.names.append(extra)
        self.values = {method: (
            [arb(float(x)) for x in np.maximum.accumulate(a[0, ::-1])],
            [arb(float(x)) for x in np.minimum.accumulate(a[1])[::-1]])
            for method, a in data.items()}
        units = z["units128"] if m != 1 else np.arange(-64 * 128, 96 * 128 + 1)
        thresholds = [out((-arb(int(j)) * arb(10).log() / 1280).exp()) for j in units[::-1]]
        self.tlo = np.array([a for a, b in thresholds])
        self.thi = np.array([b for a, b in thresholds])
        self.size = len(units)
        if not all(len(v[0]) == self.size for v in self.values.values()):
            raise ArithmeticError("Inconsistent dimensions in the signal bank")


@lru_cache(maxsize=12)
def signal(N: int, m: int, chernoff: bool, bits: int) -> Signal:
    return Signal(N, m, chernoff)


def environment_name(lam: str, eta: int | str, kind: str) -> str:
    """A bank filename from normalized model fields, never a manifest addition."""
    return f"{kind}_l{str(float(lam)).replace('.', 'p')}_e{str(eta).replace('.', 'p')}.npz"


class Environment(OriginalEnvironment):
    def __init__(self, model: Model, kind: str, numerics: Numerics):
        self.lam, self.eta, self.kind = model.lam, model.eta, kind
        self.names: list[str] = []
        self.generated = False
        if kind in ("mean", "none") or arb(model.lam).is_zero():
            # moment returns a cumulant of J (ENONCES (f)); R stays 1.
            # The interference gain g is applied only in point(), never here.
            mean = arb(0) if kind == "none" else moment(model.lam, eta_value(model.eta), 1, 1)
            a, b = (0.0, 0.0) if mean.is_zero() else out(mean)
            self.xlo, self.xhi = np.array([a]), np.array([b])
            wl = wh = [arb(1)]
            self.tail = arb(0)
        else:
            name = environment_name(model.lam, model.eta, kind)
            # Only exact decimal equality with the two archived intensities
            # permits reuse; a rounded binary64 filename must never select a bank.
            from decimal import Decimal
            use_bank = (type(model.eta) is int and model.eta in (3, 4)
                        and Decimal(model.lam) in (Decimal("0.1"), Decimal(1)))
            if use_bank and name in _banks.manifest() and numerics.bank_policy == "auto":
                data = _banks.arrays(name)
                self.names = [name]
            else:
                data = environment_arrays(model.lam, model.eta, numerics.ppp_dft_power, kind)
                self.generated = True
            self.xlo, self.xhi = data["xlo"], data["xhi"]
            wl, wh, self.tail = envelopes(data["clo"], data["chi"], self.xlo, self.xhi)
        self.wl, self.wh = arb_mat([wl]), arb_mat([wh])
        self.length = len(wl)

    def point(self, signal, units, convention, d: Fraction, g: Fraction, method="exact"):
        """Compose J with the signal CDF, scaling g and d exactly once."""
        if units is None:
            if convention == "C-INR":
                return dict(lower=0.0, upper=0.0)
            nlo = nhi = 0.0
        else:
            nlo, nhi = out((-arb(units) * arb(10).log() / 1280).exp())
        xlo, xhi = scale_outward(self.xlo, self.xhi, g)
        if convention == "C-INR":
            yl = down(down(xlo + 1) * nlo)
            yh = up(up(xhi + 1) * nhi)
        else:
            yl = down(xlo + nlo)
            yh = up(xhi + nhi)
        yl, yh = scale_outward(yl, yh, 3 * d / 80)
        il, ih = signal.indices(yl, yh)
        low, high = signal.lookup(il, ih, method)
        lo = (self.wl * arb_mat(self.length, 1, low))[0, 0]
        hi = (self.wh * arb_mat(self.length, 1, high))[0, 0] + self.tail
        return dict(lower=max(0.0, out(lo)[0]), upper=min(1.0, out(hi)[1]))


def environment(model: Model, kind: str, numerics: Numerics) -> Environment:
    # The arrays depend only on (lam, eta, kind, M, precision, bank policy);
    # N, m, the convention, the user and the gain are applied in point().
    # The precision is part of the key: the environment is built in Arb under
    # rt.arithmetic(numerics.precision_bits), set by the caller.
    return _environment(model.lam, model.eta, kind, numerics.precision_bits,
                        numerics.ppp_dft_power, numerics.bank_policy)


@lru_cache(maxsize=12)
def _environment(lam: str, eta: int | str, kind: str, bits: int, power: int,
                 policy: str) -> Environment:
    # Environment reads model.lam and model.eta only; the other fields keep
    # their validated defaults and play no part.
    if ctx.prec != bits:
        raise ArithmeticError("The PPP environment must be built at the precision of its cache key")
    return Environment(Model(lam=lam, eta=eta), kind, Numerics(bits, power, policy))


class Thermal(OriginalThermal):
    """Same rectangles as Table I; integrity-checked arrays replace cwd-based files."""
    def __init__(self, N: int, m: int, chernoff: bool):
        self.N = N
        name = f"m{m}_N{N}.npz"
        self.names = [name, "commun.npz"]
        self.bank = _banks.arrays(name)
        self.B = int(self.bank["B"])
        self.dx = self.B / (1 << 19)
        self.common = _banks.arrays("commun.npz")
        self.levels, self.weights, self.arb_values = {}, {}, {}
        if chernoff:
            name = f"C_N{N}.npz"
            self.bank.update(_banks.arrays(name))
            self.names.append(name)
        for method in (["exact", "gauss", "chernoff"] if chernoff else ["exact", "gauss"]):
            self.arb_values[method] = ([arb(float(x)) for x in self.bank[method + "_lo"]],
                                       [arb(float(x)) for x in self.bank[method + "_hi"]])
        for J in range(9, 14):
            step = 1 << (13 - J)
            z, ph = self.common["z"][::step], self.common["phi"][:, ::step]
            left, right = np.abs(10 + z[:-1]), np.abs(10 + z[1:])
            ml = [(arb(float(x)) / (1 << J)).lower() for x in np.minimum(ph[0, :-1], ph[0, 1:])]
            mh = [(arb(float(x)) / (1 << J)).upper() for x in np.maximum(ph[1, :-1], ph[1, 1:])]
            self.levels[J] = (np.minimum(left, right), np.maximum(left, right), (ml, mh))
            self.weights[J] = arb_mat([ml]), arb_mat([mh])


@lru_cache(maxsize=1)
def thermal(N: int, m: int, chernoff: bool, bits: int) -> Grouped:
    return Grouped(Thermal(N, m, chernoff))


def thermal_point(calc: Grouped, db: str, d: Fraction, methods=None, goal=.008):
    """Grouped thermal rectangles with a per-call, outward link amplitude."""
    rho = (arb(db) * arb(10).log() / 10).exp()
    aa = outward((101 * (arb(d.numerator) / d.denominator) / rho).sqrt())
    return _thermal_point_amplitude(calc, aa, methods, goal)


def _thermal_point_amplitude(grouped: Grouped, aa, methods, goal):
    """The Grouped.point loop, with an amplitude passed instead of cached."""
    calc = grouped.calc
    for J in range(9, 14):
        il, ih = calc.indices(aa, J)
        outcome = {}
        for method, (lv, hv) in calc.arb_values.items():
            if methods is not None and method not in methods:
                continue
            lo = grouped.dot(il, lv, grouped.prefix[J][0])
            hi = grouped.dot(ih, hv, grouped.prefix[J][1]) + arb(float(calc.common["outside"]))
            outcome[method] = (max(0., out(lo)[0]), min(1., out(hi)[1]))
        if all(arb(float(b)) - arb(float(a)) <= arb(str(goal)) * arb(float(a))
               for a, b in outcome.values()):
            break
    return outcome, J


def clear() -> None:
    signal.cache_clear()
    _environment.cache_clear()
    thermal.cache_clear()
