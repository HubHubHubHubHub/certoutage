"""Adapters with no chdir, no access to the archive and no permanent global change."""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
import threading

import numpy as np
from flint import arb, arb_mat, ctx

from . import _banks
from .models import Model, Numerics
from ._vendor.commun import out, moment
from ._vendor.oracles import Signal as OriginalSignal, Environment as OriginalEnvironment
from ._vendor.ppp import envelopes
from ._vendor.nak_thermal import Thermal as OriginalThermal
from ._vendor.nak_grouped import Grouped
from ._generate import environment_arrays

_LOCK = threading.RLock()


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


class Environment(OriginalEnvironment):
    def __init__(self, model: Model, kind: str, numerics: Numerics):
        self.lam, self.eta, self.kind = model.lam, model.eta, kind
        self.names: list[str] = []
        self.generated = False
        if kind in ("mean", "none") or arb(model.lam).is_zero():
            mean = arb(0) if kind == "none" else moment(model.lam, model.eta, 1, 1)
            a, b = (0.0, 0.0) if mean.is_zero() else out(mean)
            self.xlo, self.xhi = np.array([a]), np.array([b])
            wl = wh = [arb(1)]
            self.tail = arb(0)
        else:
            name = f"{kind}_l{str(float(model.lam)).replace('.', 'p')}_e{model.eta}.npz"
            # Only exact decimal equality with the two archived intensities
            # permits reuse; a rounded binary64 filename must never select a bank.
            from decimal import Decimal
            use_bank = Decimal(model.lam) in (Decimal("0.1"), Decimal(1))
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


@lru_cache(maxsize=12)
def environment(model: Model, kind: str, numerics: Numerics) -> Environment:
    return Environment(model, kind, numerics)


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


def clear() -> None:
    signal.cache_clear()
    environment.cache_clear()
    thermal.cache_clear()
