"""Pure gain and signal generators, with the archive evaluation order.

Only the callers write banks. ``power`` is a private reduced-grid test parameter;
production gain banks use 19. No new public model sizes are enabled here.
"""
from __future__ import annotations

import math
from fractions import Fraction
from numbers import Integral

import numpy as np
from flint import acb, arb, arb_mat

from ._vendor.commun import out
from ._vendor.thermal_backend import L, normal, outward, tighten
from ._vendor.nak_grouped import Grouped

_SIGNAL_SIZE = 20481


def _integer(value, name, lower, upper=None):
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral)
            or value < lower or (upper is not None and value > upper)):
        domain = f"[{lower}, {upper}]" if upper is not None else f">= {lower}"
        raise ValueError(f"{name} must be an integer in {domain}; booleans are not accepted")
    return int(value)


def gain_period(N):
    """Exact period N + 16 ceil(sqrt(N)) + 40 for every integer N >= 1."""
    N = _integer(N, "N", 1)
    return N + 16 * (math.isqrt(N - 1) + 1) + 40


def _gain_kernel(N, power):
    """Inversion kernel; the caller owns the Arb context."""
    N = _integer(N, "N", 1)
    power = _integer(power, "power", 0)
    M = 1 << power
    if M % 2 != 0:
        raise ValueError("The Fourier remainder requires an even M")
    if M < N:
        raise ValueError("The Fourier remainder requires M >= N")
    B = gain_period(N)
    c = arb(20) / B
    coeff = [None] * M
    for j in range(M // 2 + 1):
        s = acb(c, 2 * arb.pi() * j / B)
        v = L(s) ** N / s
        if j == 0 or j == M // 2:
            coeff[j] = acb(v.real)
        else:
            coeff[j] = v
            coeff[M - j] = v.conjugate()
    ft = acb.dft(coeff, inverse=True)
    del coeff
    tail = (-arb(B)).exp() * L(-1).real ** N
    alias = tail / arb(20).expm1()
    a0 = 1 / arb(20).expm1()
    freq = 2 / (arb.pi() * N) * ((2 * arb.pi() + c) * B / (arb.pi() * M)) ** N
    exact = np.empty((2, M + 1))
    gauss = np.empty_like(exact)
    mu = arb.pi() / 4
    sd = (N * (1 - mu * mu)).sqrt()
    for j in range(M):
        ex = (arb(20) * j / M).exp()
        value = ft[j].real * ex * M / B - a0
        exact[:, j] = out(value + arb(0, (freq * ex).upper()) + arb(0).union(alias))
        x = arb(j) * B / M
        gauss[:, j] = out(normal((x - N * mu) / sd) - normal((-x - N * mu) / sd))
    exact[:, 0] = 0
    exact[:, -1] = (out(1 - tail)[0], 1)
    x = arb(B)
    gauss[:, -1] = out(normal((x - N * mu) / sd) - normal((-x - N * mu) / sd))
    gauss[:, 0] = 0
    for values in (exact, gauss):
        values[0], values[1] = tighten(*values)
    return dict(N=np.array(N, dtype=np.int64), B=np.array(B, dtype=np.int64),
                exact_lo=exact[0], exact_hi=exact[1], gauss_lo=gauss[0], gauss_hi=gauss[1])


def gain_arrays(N, *, m=1, power=19, bits=160) -> dict:
    """Return gain arrays for integer m in {1,2,3}, 8 <= N <= 64.

    ``power`` is private to tests. The m=1 kernel retains its original order;
    m=2,3 use the integer recurrence and include a scalar int64 m.
    """
    m = _nakagami_m(m)
    N = _integer(N, "N", 8, 64)
    power = _integer(power, "power", 10, 19)
    # Local import avoids a cycle with the runtime's thermal adapter.
    from ._runtime import arithmetic
    with arithmetic(bits):
        if m == 1:
            return _gain_kernel(N, power)
        return _nakagami_gain_kernel(N, m, power)


def _check_kappa(kappa):
    if not isinstance(kappa, Fraction) or kappa < 0:
        raise ValueError("kappa must be an exact nonnegative Fraction")
    return kappa


def thermal_levels(z, phi, J, kappa=Fraction(10)):
    """Thermal extrema and unchanged density masses on a selected 2**(-J) grid.

    Input nodes are the common bank subsampled for J. Every endpoint absolute
    value is exact before directed binary64 rounding. A closed cell containing
    -kappa has minimum zero, including when -kappa is itself a grid node.
    The caller owns the Arb context used for the density masses.
    """
    kappa = _check_kappa(kappa)
    J = _integer(J, "J", 9, 13)
    z, phi = np.asarray(z), np.asarray(phi)
    if (z.ndim != 1 or len(z) < 2 or phi.shape != (2, len(z))
            or not np.all(np.isfinite(z)) or not np.all(np.isfinite(phi))):
        raise ValueError("Invalid common thermal grid")
    # On this path every node is n/8192, |n|<=98304. If kappa has a
    # denominator dividing 8192 and the numerator of the sum fits in 53
    # bits, IEEE addition is exact. Multiplication by 8192 is exact here.
    short_dyadic = (8192 % kappa.denominator == 0
                    and abs(kappa.numerator * (8192 // kappa.denominator)) + 98304 <= 2**53)
    if (short_dyadic and np.all(np.abs(z) <= 12)
            and np.all(z * 8192 == np.rint(z * 8192))):
        signed = float(kappa) + z
        lower = upper = np.abs(signed)
        crosses = (signed[:-1] <= 0) & (signed[1:] >= 0)
    else:
        signed = [kappa + Fraction(float(x)) for x in z]
        lower, upper = np.empty(len(z)), np.empty(len(z))
        for i, value in enumerate(signed):
            lower[i], upper[i] = _absolute_outward(abs(value))
        crosses = np.array([a <= 0 <= b for a, b in zip(signed[:-1], signed[1:])])
    tmin = np.minimum(lower[:-1], lower[1:])
    tmax = np.maximum(upper[:-1], upper[1:])
    tmin[crosses] = 0.0
    ml = [(arb(float(x)) / (1 << J)).lower() for x in np.minimum(phi[0, :-1], phi[0, 1:])]
    mh = [(arb(float(x)) / (1 << J)).upper() for x in np.maximum(phi[1, :-1], phi[1, 1:])]
    return tmin, tmax, (ml, mh)


def _absolute_outward(value):
    """Directed conversion of a nonnegative exact rational, keeping exact floats."""
    try:
        rounded = float(value)
    except OverflowError:
        return np.finfo(np.float64).max, np.inf
    represented = Fraction(rounded)
    if represented == value:
        return rounded, rounded
    else:
        lower = np.nextafter(rounded, -np.inf) if represented > value else rounded
        upper = np.nextafter(rounded, np.inf) if represented < value else rounded
        return lower, upper


def _signal_amplitude(db, kappa=Fraction(10)):
    kappa = _check_kappa(kappa)
    square = 1 + kappa * kappa
    normalization = square.numerator if square.denominator == 1 else arb(square.numerator) / square.denominator
    d = arb(str(db))
    ci = arb(10) / 3
    lam = arb(1) / 8
    return outward((normalization * ci / ((d * arb(10).log() / 10).exp() * lam)).sqrt())


class _SignalThermal:
    """In-memory thermal rectangles; never invoke a file-reading constructor."""

    def __init__(self, gain, common, kappa=Fraction(10)):
        self.kappa = _check_kappa(kappa)
        self.M = len(gain["exact_lo"]) - 1
        self.dx = int(gain["B"]) / self.M
        self.common = common
        self.arb_values = {
            name: ([arb(float(x)) for x in gain[name + "_lo"]],
                   [arb(float(x)) for x in gain[name + "_hi"]])
            for name in ("exact", "gauss")}
        self.levels, self.weights = {}, {}
        for J in range(9, 14):
            step = 1 << (13 - J)
            z, ph = common["z"][::step], common["phi"][:, ::step]
            self.levels[J] = thermal_levels(z, ph, J, self.kappa)
            ml, mh = self.levels[J][2]
            self.weights[J] = arb_mat([ml]), arb_mat([mh])

    def indices(self, aa, J):
        tmin, tmax, _ = self.levels[J]
        al = np.maximum(0, np.nextafter(aa[0] / tmax, -np.inf))
        with np.errstate(divide="ignore"):
            ah = np.nextafter(aa[1] / tmin, np.inf)
        il = np.minimum(self.M, np.floor(np.maximum(0, np.nextafter(al / self.dx, -np.inf)))).astype(np.int64)
        ih = np.minimum(self.M, np.ceil(np.maximum(0, np.nextafter(ah / self.dx, np.inf)))).astype(np.int64)
        return il, ih


def _signal_point(calc, grouped, db):
    aa = _signal_amplitude(db, calc.kappa)
    for J in range(9, 14):
        il, ih = calc.indices(aa, J)
        outcome = {}
        for method, (lv, hv) in calc.arb_values.items():
            if db >= 40:
                lo = grouped.dot(il, lv, grouped.prefix[J][0])
                hi = grouped.dot(ih, hv, grouped.prefix[J][1])
            else:
                wl, wh = calc.weights[J]
                length = len(il)
                lo = (wl * arb_mat(length, 1, [lv[int(i)] for i in il]))[0, 0]
                hi = (wh * arb_mat(length, 1, [hv[int(i)] for i in ih]))[0, 0]
            hi = hi + arb(float(calc.common["outside"]))
            outcome[method] = (max(0.0, out(lo)[0]), min(1.0, out(hi)[1]))
        if all(arb(float(b)) - arb(float(a)) <= max(arb('.004') * arb(float(a)), arb('2e-10'))
               for a, b in outcome.values()):
            break
    return outcome, J


def signal_points(gain, common, indices, *, bits=160, kappa=Fraction(10)):
    """Return raw exact/gauss bounds and int8 levels at distinct grid indices.

    A part contains ``indices`` (int64), ``exact``, ``gauss`` (2 by count),
    and ``levels``. Bounds have not undergone the final monotone tightening.
    The caller must merge explicit parts covering the whole grid.
    """
    indices = np.array([_integer(i, "index", 0, _SIGNAL_SIZE - 1) for i in indices], dtype=np.int64)
    if len(np.unique(indices)) != len(indices):
        raise ValueError("Signal indices must be disjoint")
    from ._runtime import arithmetic
    with arithmetic(bits):
        calc = _SignalThermal(gain, common, kappa)
        grouped = Grouped(calc)
        result = dict(indices=indices, exact=np.empty((2, len(indices))),
                      gauss=np.empty((2, len(indices))), levels=np.empty(len(indices), dtype=np.int8))
        for k, j in enumerate(indices):
            values, J = _signal_point(calc, grouped, (int(j) - 8192) / 128)
            for method in ("exact", "gauss"):
                result[method][:, k] = values[method]
            result["levels"][k] = J
        return result


def finish_signal(parts, *, _size=_SIGNAL_SIZE):
    """Merge disjoint full coverage, then tighten; ``_size`` is private to tests."""
    _size = _integer(_size, "size", 1, _SIGNAL_SIZE)
    seen = np.zeros(_size, dtype=bool)
    result = dict(exact=np.empty((2, _size)), gauss=np.empty((2, _size)),
                  levels=np.empty(_size, dtype=np.int8))
    for part in parts:
        indices = np.asarray(part["indices"])
        if (indices.ndim != 1 or indices.dtype.kind not in "iu"
                or np.any(indices < 0) or np.any(indices >= _size)
                or len(np.unique(indices)) != len(indices) or np.any(seen[indices])):
            raise ValueError("Signal parts must have disjoint indices inside the grid")
        for name in ("exact", "gauss", "levels"):
            values = np.asarray(part[name])
            shape = (len(indices),) if name == "levels" else (2, len(indices))
            if values.shape != shape or not np.all(np.isfinite(values)):
                raise ValueError("Invalid signal part dimensions or non-finite values")
            if name == "levels" and (values.dtype != np.int8 or np.any(values < 9) or np.any(values > 13)):
                raise ValueError("Signal levels must be int8 in [9, 13]")
            result[name][..., indices] = values
        seen[indices] = True
    if not np.all(seen):
        raise ValueError("Signal parts must cover the whole grid without holes")
    for name in ("exact", "gauss"):
        a = result[name]
        a[0] = np.maximum.accumulate(a[0, ::-1])[::-1]
        a[1] = np.minimum.accumulate(a[1])
        if not np.all(a[0] <= a[1]):
            raise ArithmeticError("Inconsistent signal bounds: lower bound above upper bound")
    return result


def signal_arrays(gain, common, *, bits=160, kappa=Fraction(10)):
    """Return a complete signal bank, in exact, gauss, levels insertion order."""
    from ._runtime import arithmetic
    with arithmetic(bits):
        return finish_signal([signal_points(gain, common, range(_SIGNAL_SIZE), bits=bits, kappa=kappa)])


def _nakagami_m(m):
    try:
        return _integer(m, "m", 1, 3)
    except ValueError as error:
        raise ValueError("m must be an exact integer in {1, 2, 3}; other m are not supported "
                         "because the transform recurrence uses the integer index 2m-1") from error


def _nakagami_gain_kernel(N, m, power):
    """Inversion kernel; the caller owns the Arb context."""
    from ._nakagami import L, mu, variation
    N = _integer(N, "N", 1)
    power = _integer(power, "power", 0)
    M = 1 << power
    if M % 2 != 0:
        raise ValueError("The Fourier remainder requires an even M")
    if M < N:
        raise ValueError("The Fourier remainder requires M >= N")
    B = gain_period(N)
    c = arb(20) / B
    coeff = [None] * M
    for j in range(M // 2 + 1):
        s = acb(c, 2 * arb.pi() * j / B)
        v = L(s, m) ** N / s
        if j == 0 or j == M // 2:
            coeff[j] = acb(v.real)
        else:
            coeff[j] = v
            coeff[M - j] = v.conjugate()
    ft = acb.dft(coeff, inverse=True)
    del coeff
    tail = (-arb(B)).exp() * L(-1, m).real ** N
    alias = tail / arb(20).expm1()
    a0 = 1 / arb(20).expm1()
    freq = 2 / (arb.pi() * N) * ((variation(m) + c) * B / (arb.pi() * M)) ** N
    exact = np.empty((2, M + 1))
    gauss = np.empty_like(exact)
    mean = N * mu(m)
    sd = (N * (1 - mu(m) ** 2)).sqrt()
    for j in range(M):
        ex = (arb(20) * j / M).exp()
        value = ft[j].real * ex * M / B - a0
        exact[:, j] = out(value + arb(0, (freq * ex).upper()) + arb(0).union(alias))
        x = arb(j) * B / M
        gauss[:, j] = out(normal((x - mean) / sd) - normal((-x - mean) / sd))
    exact[:, 0] = 0
    exact[:, -1] = (out(1 - tail)[0], 1)
    x = arb(B)
    gauss[:, -1] = out(normal((x - mean) / sd) - normal((-x - mean) / sd))
    gauss[:, 0] = 0
    for values in (exact, gauss):
        values[0], values[1] = tighten(*values)
    return dict(N=np.array(N, dtype=np.int64), m=np.array(m, dtype=np.int64),
                B=np.array(B, dtype=np.int64),
                exact_lo=exact[0], exact_hi=exact[1], gauss_lo=gauss[0], gauss_hi=gauss[1])


def _grouped_signal_point(calc, grouped, db, relative, absolute):
    """Always group rectangles; the stopping bounds do not alter the result."""
    aa = _signal_amplitude(db, calc.kappa)
    for J in range(9, 14):
        il, ih = calc.indices(aa, J)
        outcome = {}
        for method, (lv, hv) in calc.arb_values.items():
            lo = grouped.dot(il, lv, grouped.prefix[J][0])
            hi = grouped.dot(ih, hv, grouped.prefix[J][1]) + arb(float(calc.common["outside"]))
            outcome[method] = (max(0., out(lo)[0]), min(1., out(hi)[1]))
        if all(arb(b) - arb(a) <= max(arb(relative) * arb(a), arb(absolute))
               for a, b in outcome.values()):
            break
    return outcome, J


def _part_indices(indices, size):
    result = np.array([_integer(i, "index", 0, size - 1) for i in indices], dtype=np.int64)
    if len(np.unique(result)) != len(result):
        raise ValueError("Signal indices must be disjoint")
    return result


def nakagami_signal_points(gain, common, indices, *, bits=160, kappa=Fraction(10)):
    """Raw bounds on the 1025-node grid (-4096+8*j)/128 dB, with levels."""
    m = _nakagami_m(np.asarray(gain.get("m")).item())
    if m == 1:
        raise ValueError("Nakagami signal generation requires m=2 or 3; use signal_points for m=1")
    _integer(np.asarray(gain["N"]).item(), "N", 8, 64)
    indices = _part_indices(indices, 1025)
    from ._runtime import arithmetic
    with arithmetic(bits):
        calc = _SignalThermal(gain, common, kappa)
        grouped = Grouped(calc)
        result = dict(indices=indices, exact=np.empty((2, len(indices))),
                      gauss=np.empty((2, len(indices))), levels=np.empty(len(indices), dtype=np.int8))
        for k, j in enumerate(indices):
            values, J = _grouped_signal_point(calc, grouped, (-4096 + 8 * int(j)) / 128, '.008', '1e-9')
            for method in ("exact", "gauss"):
                result[method][:, k] = values[method]
            result["levels"][k] = J
        return result


def _merge_signal_parts(parts, size, methods):
    seen = np.zeros(size, dtype=bool)
    result = {name: np.empty((2, size)) for name in methods}
    result["levels"] = np.empty(size, dtype=np.int8)
    for part in parts:
        indices = np.asarray(part["indices"])
        if (indices.ndim != 1 or indices.dtype.kind not in "iu"
                or np.any(indices < 0) or np.any(indices >= size)
                or len(np.unique(indices)) != len(indices) or np.any(seen[indices])):
            raise ValueError("Signal parts must have disjoint indices inside the grid")
        for name in (*methods, "levels"):
            values = np.asarray(part[name])
            shape = (len(indices),) if name == "levels" else (2, len(indices))
            if values.shape != shape or not np.all(np.isfinite(values)):
                raise ValueError("Invalid signal part dimensions or non-finite values")
            if name == "levels" and (values.dtype != np.int8 or np.any(values < 9) or np.any(values > 13)):
                raise ValueError("Signal levels must be int8 in [9, 13]")
            result[name][..., indices] = values
        seen[indices] = True
    if not np.all(seen):
        raise ValueError("Signal parts must cover the whole grid without holes")
    for name in methods:
        lo, hi = result[name]
        if not np.all((0 <= lo) & (lo <= hi) & (hi <= 1)):
            raise ArithmeticError("Inconsistent signal bounds: require 0 <= lower <= upper <= 1")
    return result


def nakagami_finish_signal(parts, *, _size=1025):
    """Merge complete disjoint parts, without final tightening or saved levels."""
    size = _integer(_size, "size", 1, 1025)
    result = _merge_signal_parts(parts, size, ("exact", "gauss"))
    return dict(units128=np.arange(-4096, -4096 + 8 * size, 8, dtype=np.int64),
                exact=np.asfortranarray(result["exact"]), gauss=np.asfortranarray(result["gauss"]))


def nakagami_signal_arrays(gain, common, *, bits=160, kappa=Fraction(10)):
    """Return units128, exact and gauss, in the historical insertion order."""
    return nakagami_finish_signal([nakagami_signal_points(
        gain, common, range(1025), bits=bits, kappa=kappa)])


class _ChernoffThermal(_SignalThermal):
    """In-memory Rayleigh thermal adapter requiring only the Chernoff bank."""

    def __init__(self, cbank, common, kappa=Fraction(10)):
        _integer(np.asarray(cbank["N"]).item(), "N", 8, 64)
        self.kappa = _check_kappa(kappa)
        self.M = len(cbank["chernoff_lo"]) - 1
        self.dx = int(cbank["B"]) / self.M
        self.common = common
        self.arb_values = {"chernoff": (
            [arb(float(x)) for x in cbank["chernoff_lo"]],
            [arb(float(x)) for x in cbank["chernoff_hi"]])}
        self.levels, self.weights = {}, {}
        for J in range(9, 14):
            step = 1 << (13-J)
            z, ph = common["z"][::step], common["phi"][:, ::step]
            self.levels[J] = thermal_levels(z, ph, J, self.kappa)
            ml, mh = self.levels[J][2]
            self.weights[J] = arb_mat([ml]), arb_mat([mh])


def _chernoff_signal_point(calc, grouped, db):
    return _grouped_signal_point(calc, grouped, db, '.004', '2e-10')


def chernoff_signal_points(cbank, common, indices, *, bits=160, kappa=Fraction(10)):
    """Raw comparator bounds at indices 0..5120, on (j-2048)/32 dB."""
    indices = _part_indices(indices, 5121)
    from ._runtime import arithmetic
    with arithmetic(bits):
        calc = _ChernoffThermal(cbank, common, kappa)
        grouped = Grouped(calc)
        result = dict(indices=indices, chernoff=np.empty((2, len(indices))),
                      levels=np.empty(len(indices), dtype=np.int8))
        for k, j in enumerate(indices):
            values, J = _chernoff_signal_point(calc, grouped, (int(j)-2048)/32)
            result["chernoff"][:, k] = values["chernoff"]
            result["levels"][k] = J
        return result


def chernoff_finish_signal(parts, *, _size=5121):
    """Merge complete disjoint parts, tighten, then envelope at 1/128 dB."""
    size = _integer(_size, "size", 1, 5121)
    result = _merge_signal_parts(parts, size, ("chernoff",))
    thermal = result["chernoff"]
    thermal[0] = np.maximum.accumulate(thermal[0, ::-1])[::-1]
    thermal[1] = np.minimum.accumulate(thermal[1])
    if not np.all(thermal[0] <= thermal[1]):
        raise ArithmeticError("Inconsistent Chernoff signal bounds: lower above upper")
    fine = np.arange(4*(size-1)+1)
    envelope = np.array([thermal[0, (fine + 3)//4], thermal[1, fine//4]])
    return dict(chernoff=envelope, levels=result["levels"])


def chernoff_signal_arrays(cbank, common, *, bits=160, kappa=Fraction(10)):
    """Return propagated Chernoff bounds and the 5121 raw refinement levels."""
    return chernoff_finish_signal([chernoff_signal_points(
        cbank, common, range(5121), bits=bits, kappa=kappa)])


def generation_scope(gain, m, N):
    """Describe the complete bank dependency closure, or reject the case.

    This is a generator contract, not an extension of Model or the public API.
    ``banks`` is in dependency order. ``requires`` maps array arguments to
    logical bank names; commun.npz is the existing shared thermal input.

    J_max depends on N and m only through the exact SIG bank. Its distribution
    is computed on demand; the central MINORANTS certificates are reusable
    cached results, not a necessary bank for a new N. Current runtime adapters
    load the ordinary Rayleigh banks alongside Chernoff, so that dependency
    and the exact SIG needed by J_max are included explicitly.
    """
    m = _nakagami_m(m)
    try:
        N = _integer(N, "N", 8, 64)
    except ValueError as error:
        raise ValueError("N must be an integer in [8, 64], without booleans; "
                         "this is the announced generation domain for 0.4.0") from error
    if not isinstance(gain, str) or gain not in ("exact", "eq3", "chernoff"):
        raise ValueError("gain must be exact, eq3 or chernoff; gamma, gg and other names are not ported")
    if gain == "chernoff" and m != 1:
        raise ValueError("Chernoff generation is defined only for Rayleigh m=1, with integer N in [8, 64]")
    amplitude = f"m{m}_N{N}.npz"
    sig = f"SIG_{N}.npz" if m == 1 else f"SIG_m{m}_N{N}.npz"
    signal_function = "signal_arrays" if m == 1 else "nakagami_signal_arrays"
    banks = [dict(name=amplitude, function="certoutage._generate_gain.gain_arrays",
                  parameters=dict(N=N, m=m), requires={}),
             dict(name=sig, function=f"certoutage._generate_gain.{signal_function}",
                  parameters={}, requires=dict(gain=amplitude, common="commun.npz"))]
    direct, interference = [amplitude], [sig]
    if gain == "chernoff":
        cbank, csig = f"C_N{N}.npz", f"SIG_C_{N}.npz"
        banks += [dict(name=cbank, function="certoutage._chernoff.chernoff_arrays",
                       parameters=dict(N=N), requires={}),
                  dict(name=csig, function="certoutage._generate_gain.chernoff_signal_arrays",
                       parameters={}, requires=dict(cbank=cbank, common="commun.npz"))]
        direct.append(cbank)
        interference.append(csig)
    return dict(gain=gain, m=m, N=N, banks=banks, shared_inputs=["commun.npz"],
                paths=dict(direct=direct, with_interference=interference, largest_interferer=[sig]),
                largest_interferer="supported by construction from the exact SIG bank; "
                                   "central certificates are optional cached results")
