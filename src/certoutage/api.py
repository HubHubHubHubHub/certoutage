"""Public API for certification and comparison."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
import json
import math

import numpy as np
from flint import arb, arb_mat

from .models import (Model, Numerics, SNRGrid, Scalar, Gain, Interference, Contract,
                     Enclosure, SNRDecision, ComparisonRow, ThresholdDifference, decimal)
from . import _runtime as rt, _banks
from ._vendor.commun import out
from ._vendor.ppp import envelopes
from ._transform import eta_value, informative

DEFAULT_NUMERICS = Numerics()
DEFAULT_GRID = SNRGrid()
_METHODS = {"exact": "exact", "eq3": "gauss", "chernoff": "chernoff"}
_KINDS = {"PPP": "PPP", "Gamma": "GAMMA", "mean": "mean", "none": "none"}


def _validate(model: Model, user: int, gain: Gain, interference: Interference,
              numerics: Numerics) -> None:
    if not isinstance(model, Model) or not isinstance(numerics, Numerics):
        raise TypeError("model and numerics must be a Model and a Numerics")
    if type(user) is not int or user not in (1, 2):
        raise ValueError("user must be the integer 1 or 2")
    if gain not in _METHODS:
        raise ValueError("gain must be 'exact', 'eq3' or 'chernoff'")
    if interference not in _KINDS:
        raise ValueError("interference must be 'PPP', 'Gamma', 'mean' or 'none'")
    if gain == "chernoff":
        no_ppp = Decimal(model.lam) == 0 or interference == "none" or model.g == "0"
        supported = model.m == 1 and (model.N in (20, 24) or (no_ppp and model.N in (8, 64)))
        if not supported:
            raise ValueError("Chernoff is provided for Rayleigh N=20, 24, and for N=8, 64 without PPP")


def _quantity(gain: Gain, interference: Interference) -> str:
    if gain == "chernoff":
        return f"propagated Chernoff upper bound, interference={interference}"
    return f"outage: gain={'exact' if gain == 'exact' else 'Eq. (3)'}, interference={interference}"


def _assumptions(model: Model) -> tuple[str, ...]:
    assumptions = list(Contract.assumptions)
    if model.g != "1":
        assumptions[3] += f"; interference gain g={model.g}"
    if (model.d1, model.d2) != ("80/3", "160"):
        infeasible = " (infeasible power allocation)" if "inf" in (model.d1, model.d2) else ""
        assumptions[4] = f"d1={model.d1}, d2={model.d2}{infeasible}; perfect CSI and phase alignment"
    return tuple(assumptions)


def _contract(model: Model, gain: Gain, interference: Interference, numerics: Numerics,
              names: list[str], *, generated: bool = False, analytic: bool = False,
              notes: tuple[str, ...] = ()) -> Contract:
    # The transform and D_M notes describe a PPP inversion: they are omitted
    # when no inversion contributes (analytic results, lam=0, g=0).
    ppp_used = not analytic and Decimal(model.lam) != 0 and model.g != "0"
    if interference == "PPP" and type(model.eta) is not int and ppp_used:
        domain = "inside" if informative(model.lam, model.eta, numerics.ppp_dft_power) else "outside"
        notes += (f"eta={model.eta}: Laplace transform by the 2F1 identities (Arb, abc=True)",
                  f"(lam, eta, M) {domain} the informative domain D_M (e^20 R <= 1e-7, "
                  "tau <= 1e-10); outside, the enclosure stays valid but may be wide")
    return Contract(_quantity(gain, interference),
                    "analytic" if analytic else "mixed" if generated else "provided-banks",
                    numerics.precision_bits, _banks.receipt(*names),
                    assumptions=_assumptions(model), notes=notes)


def _evaluate(model: Model, user: int, db: Decimal | None, gain: Gain,
              interference: Interference, numerics: Numerics) -> Enclosure:
    method, kind = _METHODS[gain], _KINDS[interference]
    d = model.d1 if user == 1 else model.d2
    no_ppp = Decimal(model.lam) == 0 or interference == "none" or model.g == "0"
    link_notes = ("g=0: no interference contribution",) if model.g == "0" else ()
    parameters = _parameters(model, user, gain, interference)
    if d == "inf":
        contract = _contract(model, gain, interference, numerics, [], analytic=True,
                             notes=("infeasible power allocation: outage is 1 at every SNR",) + link_notes)
        return Enclosure(1.0, 1.0, replace(contract, parameters=parameters))
    if db is None and (model.convention == "C-INR" or no_ppp):
        return Enclosure(0.0, 0.0, replace(_contract(model, gain, interference, numerics, [],
                                                  analytic=True, notes=link_notes), parameters=parameters))
    direct = no_ppp and ((model.m == 1 and model.N in (8, 64)) or
                        (model.m in (2, 3) and model.N == 8))
    if direct:
        calc = rt.thermal(model.N, model.m, gain == "chernoff", numerics.precision_bits)
        if d == "80/3":
            values, level = calc.point(str(db), methods=[method])
        elif d == "160":
            values, level = calc.calc.point(str(db), user=2, methods=[method])
        else:
            values, level = rt.thermal_point(calc, str(db), Fraction(d), methods=[method])
        lo, hi = values[method]
        contract = _contract(model, gain, interference, numerics, calc.calc.names,
                             notes=(f"thermal rectangles J={level}, goal=0.008; Table I backend",) + link_notes)
    else:
        signal = rt.signal(model.N, model.m, gain == "chernoff", numerics.precision_bits)
        env = rt.environment(model, "none" if model.g == "0" else kind, numerics)
        units = None if db is None else arb(str(db)) * 128
        result = env.point(signal, units, model.convention, Fraction(d), Fraction(model.g), method)
        lo, hi = result["lower"], result["upper"]
        notes = ((f"PPP generated with B=128, cB=20, M={1 << numerics.ppp_dft_power}; explicit Fourier and tail remainders",)
                 if kind == "PPP" else ("Gamma CDF generated using Arb, moment matching; no PPP error bound",)) if env.generated else ()
        contract = _contract(model, gain, interference, numerics, signal.names + env.names,
                             generated=env.generated, notes=notes + link_notes)
    return Enclosure(float(lo), float(hi), replace(contract, parameters=parameters))


def _parameters(model: Model, user: int, gain: str, interference: str) -> tuple[tuple[str, str], ...]:
    return tuple((k, str(v)) for k, v in dict(N=model.N, m=model.m, lam=model.lam,
                 eta=model.eta, R0=model.R0, convention=model.convention, user=user,
                 gain=gain, interference=interference, d1=model.d1, d2=model.d2, g=model.g).items())


def outage_enclosure(model: Model, user: int, snr_db: Scalar, *, gain: Gain = "exact",
                     interference: Interference = "PPP",
                     numerics: Numerics = DEFAULT_NUMERICS) -> Enclosure:
    """Two-sided bounds at a FINITE SNR in dB (10 log10 rho).

    Eq. (3), Gamma and mean certify their comparator models only.
    For Chernoff, the interval encloses the propagated upper bound, not the outage.
    """
    _validate(model, user, gain, interference, numerics)
    db = decimal(snr_db, "snr_db")
    if not -1000 <= db <= 1000:
        raise ValueError("snr_db must lie in [-1000, 1000] dB; use floor for infinite SNR")
    with rt.arithmetic(numerics.precision_bits):
        return _evaluate(model, user, db, gain, interference, numerics)


def floor(model: Model, user: int, *, gain: Gain = "exact",
          interference: Interference = "PPP", numerics: Numerics = DEFAULT_NUMERICS) -> Enclosure:
    """Certified floor at infinite SNR. C-INR: zero for a feasible link."""
    _validate(model, user, gain, interference, numerics)
    with rt.arithmetic(numerics.precision_bits):
        return _evaluate(model, user, None, gain, interference, numerics)


def required_snr(model: Model, user: int, target: Scalar, grid: SNRGrid = DEFAULT_GRID,
                 *, gain: Gain = "exact", interference: Interference = "PPP",
                 numerics: Numerics = DEFAULT_NUMERICS) -> SNRDecision:
    """Threshold in dB: last excluded point / first certified feasible point.

    An exhausted finite search is inconclusive; excluded requires the lower
    bound of the floor to lie strictly above the target. Chernoff never
    excludes the physical model. Undecided points are kept.
    """
    _validate(model, user, gain, interference, numerics)
    p = decimal(target, "target")
    if not 0 < p < 1:
        raise ValueError("target must lie in the open interval (0, 1)")
    if not isinstance(grid, SNRGrid):
        raise TypeError("grid must be an SNRGrid")
    base = floor(model, user, gain=gain, interference=interference, numerics=numerics)
    scope = "sufficient Chernoff rule" if gain == "chernoff" else _quantity(gain, interference)
    if Decimal.from_float(base.lower) > p:
        return SNRDecision("inconclusive" if gain == "chernoff" else "excluded", None, None,
                           base, "Chernoff floor exceeds target; no exclusion of outage" if gain == "chernoff"
                           else "floor lower bound exceeds target at every SNR", None, scope, target=str(p))
    # SNRGrid validates these integers exactly, independently of Decimal's context.
    a, b, h = (int(value * 128) for value in (grid.start, grid.stop, grid.step))
    last = (b - a) // h
    cache: dict[int, Enclosure] = {}

    def query(j: int) -> Enclosure:
        if j not in cache:
            cache[j] = outage_enclosure(model, user, (a + j * h) / 128,
                                        gain=gain, interference=interference, numerics=numerics)
        return cache[j]

    def first(upper: bool) -> int | None:
        def condition(j: int) -> bool:
            r = query(j)
            return Decimal.from_float(r.upper if upper else r.lower) <= p
        if condition(0):
            return 0
        if not condition(last):
            return None
        left, right = 0, last
        while right - left > 1:
            middle = (left + right) // 2
            if condition(middle):
                right = middle
            else:
                left = middle
        return right

    good, not_bad = first(True), first(False)
    bad = last if not_bad is None else not_bad - 1
    lower = (a + bad * h) / 128 if bad >= 0 else -math.inf
    upper = (a + good * h) / 128 if good is not None else None
    if bad >= 0 and not Decimal.from_float(query(bad).lower) > p:
        raise ArithmeticError("The lower edge is not certified excluded")
    if good is not None:
        if not Decimal.from_float(query(good).upper) <= p:
            raise ArithmeticError("The upper edge is not certified feasible")
        return SNRDecision("feasible", lower, upper, base,
                           "left-censored threshold" if bad < 0 else "finite threshold bracket",
                           good - bad - 1 if bad >= 0 else None, scope, query(good).contract, str(p))
    return SNRDecision("inconclusive", lower, None, base,
                       "floor overlaps target" if Decimal.from_float(base.upper) >= p else "search grid exhausted",
                       None, scope, query(last).contract, str(p))


def largest_interferer_bound(model: Model, user: int, *, numerics: Numerics = DEFAULT_NUMERICS) -> Enclosure:
    """Encloses E F_W(d_i g J_max) in C-TX, a lower bound on the PPP floor.

    An upper bound below the target proves no PPP feasibility.
    The central cases use the provided, integrity-checked certificates.
    In C-INR, returns the infinite-SNR limit: zero for a feasible link.
    """
    _validate(model, user, "exact", "PPP", numerics)
    d = model.d1 if user == 1 else model.d2
    assumptions = _assumptions(model)
    quantity = "largest-interferer bound: floor lower bound, not full PPP outage"
    if model.convention == "C-INR" and d != "inf":
        argument = "J_max" if model.g == "1" else "g J_max"
        quantity = f"C-INR largest-interferer floor: lim E F_W(d_i(1+{argument})/rho) = 0"
    parameters = _parameters(model, user, "exact", "J_max")
    if d == "inf":
        return Enclosure(1.0, 1.0, Contract(quantity, "analytic", numerics.precision_bits,
                         assumptions=assumptions, parameters=parameters,
                         notes=("infeasible power allocation: outage is 1 at every SNR",)))
    if model.convention == "C-INR" or Decimal(model.lam) == 0 or model.g == "0":
        notes = ("g=0: no interference contribution",) if model.g == "0" else ()
        return Enclosure(0.0, 0.0, Contract(quantity, "analytic", numerics.precision_bits,
                         assumptions=assumptions, parameters=parameters, notes=notes))
    name = f"MINORANTS_N{model.N}.json"
    if (model.m == 1 and model.N in (20, 24) and model.eta == 4 and user == 1
            and Decimal(model.lam) in (Decimal("0.1"), Decimal(1))
            and model.d1 == "80/3" and model.g == "1"):
        data = json.loads(_banks.verified_bytes(name))
        row = next(r for r in data["results"] if r["kind"] == "largest_jump" and Decimal(r["lam"]) == Decimal(model.lam))
        return Enclosure(row["integrated_lower"], row["integrated_upper"],
                         Contract(quantity, "provided-certificate", 160,
                                  _banks.receipt(name), assumptions=assumptions,
                                  notes=("stored endpoints at 160 bits; not recomputed",), parameters=parameters))
    with rt.arithmetic(numerics.precision_bits):
        signal = rt.signal(model.N, model.m, False, numerics.precision_bits)
        grid = np.arange(128 * 64 + 1, dtype=float) / 64
        yl, yh = rt.scale_grid_outward(grid, 3 * Fraction(d) * Fraction(model.g) / 80)
        il, ih = signal.indices(yl, yh)
        gl, gh = signal.lookup(il, ih, "exact")
        gl[0] = gh[0] = arb(0)
        ev = eta_value(model.eta)
        alpha = arb(2) / ev
        tails = [arb(1)]
        for x0 in grid[1:]:
            x = arb(float(x0))
            intensity = 2 * arb.pi() * arb(model.lam) / ev * x ** (-alpha) * x.gamma_upper(alpha)
            tails.append(-(-intensity).expm1())
        cdf = np.array([out(1 - q) for q in tails]).T
        cdf[:, 0] = 0
        wl, wh, missing = envelopes(cdf[0], cdf[1], grid, grid)
        lo = (arb_mat([wl]) * arb_mat(len(gl), 1, gl))[0, 0]
        hi = (arb_mat([wh]) * arb_mat(len(gh), 1, gh))[0, 0] + missing
        return Enclosure(max(0.0, float(out(lo)[0])), min(1.0, float(out(hi)[1])),
                         Contract(quantity, "mixed", numerics.precision_bits,
                                  _banks.receipt(*signal.names), assumptions=assumptions,
                                  notes=("J_max distribution calculated on demand",), parameters=parameters))


def compare_approximations(model: Model, user: int, target: Scalar, *,
                           grid: SNRGrid = DEFAULT_GRID,
                           numerics: Numerics = DEFAULT_NUMERICS) -> tuple[ComparisonRow, ...]:
    """Table II extended with the two mean rows, with PPP diagnostics."""
    settings: tuple[tuple[str, Gain, Interference], ...] = (
        ("Exact gain + PPP", "exact", "PPP"),
        ("Exact gain + Gamma", "exact", "Gamma"),
        ("Eq. (3) + Gamma", "eq3", "Gamma"),
        ("Exact gain + mean", "exact", "mean"),
        ("Eq. (3) + mean", "eq3", "mean"),
    )
    rows = []
    for label, gain, interference in settings:
        decision = required_snr(model, user, target, grid, gain=gain,
                                interference=interference, numerics=numerics)
        rows.append(ComparisonRow(label, decision.floor, decision))
    if rows[0].decision.status == "excluded":
        for index in range(1, len(rows)):
            if rows[index].decision.status == "feasible":
                rows[index] = replace(rows[index], diagnostic="falsely feasible")
        for exact_index, eq3_index in ((1, 2), (3, 4)):
            if rows[exact_index].diagnostic == "falsely feasible" and rows[eq3_index].decision.status == "excluded":
                rows[eq3_index] = replace(rows[eq3_index], diagnostic="masked")
    bound = largest_interferer_bound(model, user, numerics=numerics)
    excluded = Decimal.from_float(bound.lower) > decimal(target, "target")
    decision = SNRDecision("excluded" if excluded else "inconclusive", None, None, bound,
                           "largest-interferer floor lower bound exceeds target" if excluded else
                           "a floor lower bound cannot certify feasibility", None, "full PPP exclusion only",
                           target=str(decimal(target, "target")))
    if model.convention == "C-TX":
        label = "E F_W(d_i J_max)" if model.g == "1" else "E F_W(d_i g J_max)"
    else:
        limit = 1 if (model.d1 if user == 1 else model.d2) == "inf" else 0
        label = f"C-INR largest-interferer floor (limit = {limit})"
    rows.append(ComparisonRow(label, bound, decision))
    return tuple(rows)


def threshold_difference(a: SNRDecision, b: SNRDecision) -> ThresholdDifference:
    """Difference of finite thresholds with the same target, user and physical model."""
    if (a.status != "feasible" or b.status != "feasible" or
            any(x is None or not math.isfinite(x) for x in (a.lower_db, a.upper_db, b.lower_db, b.upper_db))):
        raise ValueError("A difference requires two finite, uncensored threshold enclosures")
    if a.target is None or b.target is None:
        raise ValueError("A difference requires a recorded target for each decision")
    if Decimal(a.target) != Decimal(b.target):
        raise ValueError("Both decisions must refer to the same target")
    left, right = dict(a.contract.parameters), dict(b.contract.parameters)
    for name in ("user", "convention", "N", "m", "lam", "eta", "R0", "d1", "d2", "g"):
        label = name
        if name not in left or name not in right:
            raise ValueError(f"Parameter {label} missing: the decisions are not comparable")
        if name in ("d1", "d2", "g"):
            equal = (left[name] == right[name] if "inf" in (left[name], right[name])
                     else Fraction(left[name]) == Fraction(right[name]))
        else:
            equal = (left[name] == right[name] if name == "convention"
                     else Decimal(left[name]) == Decimal(right[name]))
        if not equal:
            raise ValueError(f"Both decisions must have the same parameter {label}")
    return ThresholdDifference(a.lower_db - b.upper_db, a.upper_db - b.lower_db)


def clear_cache() -> None:
    """Frees the calculation objects; the next load verifies the banks again."""
    with rt.arithmetic(160):
        rt.clear()
        _banks.manifest.cache_clear()
