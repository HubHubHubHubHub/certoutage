"""Physical model, numerical settings and immutable public results."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_CEILING, localcontext
from fractions import Fraction
import math
from typing import Literal

Scalar = str | int | float | Decimal
Gain = Literal["exact", "eq3", "chernoff"]
Interference = Literal["PPP", "Gamma", "mean", "none"]
Status = Literal["feasible", "excluded", "inconclusive"]
SIZES = (8, 12, 16, 20, 24, 32, 48, 64)


def decimal(value: Scalar, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name}: a finite real number is required, not a boolean")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{name}: invalid real number ({value!r})") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class Model:
    """The model of the Letter. N is the number of RIS elements PER user.

    m=1: Rayleigh; m=2 or 3: Nakagami with unit mean power.
    lam=0 gives the case without PPP. R0=1 and the other constants are fixed.
    """

    N: int = 24
    lam: Scalar = "0.1"
    eta: int = 4
    convention: Literal["C-TX", "C-INR"] = "C-TX"
    m: int = 1
    R0: Scalar = 1

    def __post_init__(self) -> None:
        if type(self.N) is not int or self.N not in SIZES:
            raise ValueError(f"N must be one of the certified sizes {SIZES}")
        if type(self.m) is not int or self.m not in (1, 2, 3):
            raise ValueError("m must be 1 (Rayleigh), 2 or 3 (covered Nakagami)")
        if type(self.eta) is not int or self.eta not in (3, 4):
            raise ValueError("eta must be 3 or 4: only these transforms are implemented")
        if self.convention not in ("C-TX", "C-INR"):
            raise ValueError("convention must be 'C-TX' or 'C-INR'")
        lam = decimal(self.lam, "lam")
        if not 0 <= lam <= 10:
            raise ValueError("lam must lie in [0, 10] in this release; a small intensity may give a wide interval")
        if decimal(self.R0, "R0") != 1:
            raise ValueError("R0=1 is fixed by the normalization of the Letter")
        object.__setattr__(self, "lam", str(lam))
        object.__setattr__(self, "R0", 1)


@dataclass(frozen=True)
class Numerics:
    """Precision of the queries; the provided banks remain certified at 160 bits."""

    precision_bits: int = 160
    ppp_dft_power: int = 18
    bank_policy: Literal["auto", "fresh"] = "auto"

    def __post_init__(self) -> None:
        if type(self.precision_bits) is not int or not 160 <= self.precision_bits <= 1024:
            raise ValueError("precision_bits must be an integer between 160 and 1024")
        if type(self.ppp_dft_power) is not int or not 12 <= self.ppp_dft_power <= 20:
            raise ValueError("ppp_dft_power must be an integer between 12 and 20")
        if self.bank_policy not in ("auto", "fresh"):
            raise ValueError("bank_policy must be 'auto' or 'fresh' (PPP and Gamma)")


@dataclass(frozen=True)
class SNRGrid:
    """Finite grid in dB; endpoints and step are multiples of 1/128 dB."""

    start: Scalar = -40
    stop: Scalar = 96
    step: Scalar = "0.0625"

    def __post_init__(self) -> None:
        a, b, h = (Fraction(decimal(x, n)) for x, n in
                   ((self.start, "start"), (self.stop, "stop"), (self.step, "step")))
        if not -1000 <= a < b <= 1000 or h <= 0 or h > b - a:
            raise ValueError("grid: -1000 <= start < stop <= 1000 and 0 < step <= stop-start")
        if any((x * 128).denominator != 1 for x in (a, b, h)):
            raise ValueError("the grid must use exact multiples of 1/128 dB")
        if (b - a) % h:
            raise ValueError("stop-start must be a multiple of step")
        for n, x in (("start", a), ("stop", b), ("step", h)):
            # Bounded multiples of 1/128 are exactly representable in binary64.
            object.__setattr__(self, n, float(x))


@dataclass(frozen=True)
class Contract:
    """Scope of the certificate, provenance and assumptions attached to a result."""

    quantity: str
    source: Literal["provided-banks", "mixed", "analytic", "provided-certificate"]
    precision_bits: int
    banks: tuple[tuple[str, str], ...] = ()
    interval_library: str = "python-flint 0.9.0 / Arb-Acb"
    bank_precision_bits: int = 160
    assumptions: tuple[str, ...] = (
        "independent amplitudes, thermal term and marked PPP",
        "W=(sum sqrt(E F))²(10+Z)²/101, Z standard normal",
        "powers E,F Exp(1) or Gamma(m,rate=m), covered integer m",
        "planar PPP outside R0=1; Exp(1) power marks",
        "d1=80/3, d2=160; perfect CSI and phase alignment",
        "numerical certificate of the model; no physical or latency guarantee",
    )
    notes: tuple[str, ...] = ()
    parameters: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Enclosure:
    """Outward binary64 bounds, with no implicit cosmetic rounding."""

    lower: float
    upper: float
    contract: Contract

    def __post_init__(self) -> None:
        if not (math.isfinite(self.lower) and math.isfinite(self.upper)
                and 0 <= self.lower <= self.upper <= 1):
            raise ArithmeticError(f"invalid probability enclosure: {self.lower}, {self.upper}")

    def as_dict(self) -> dict[str, float]:
        """The two raw bounds, e.g. for the archive regressions."""
        return {"lower": self.lower, "upper": self.upper}

    def format(self, *, scale: Scalar = 1, places: int = 4) -> str:
        """Outward decimal display of the interval divided by scale."""
        s = decimal(scale, "scale")
        if s <= 0 or type(places) is not int or not 0 <= places <= 30:
            raise ValueError("scale must be positive and places an integer between 0 and 30")
        # Exact rational division, followed by integer floor/ceiling: no
        # intermediate rounding can erase a strict inequality at a boundary.
        unit = Fraction(s) / 10 ** places
        lower = Fraction.from_float(self.lower) / unit
        upper = Fraction.from_float(self.upper) / unit
        lo = lower.numerator // lower.denominator
        hi = -(-upper.numerator // upper.denominator)

        def fixed(value: int) -> str:
            digits = format(Decimal(value), "f").zfill(places + 1)
            return digits[:-places] + "." + digits[-places:] if places else digits

        return f"[{fixed(lo)}, {fixed(hi)}]"


@dataclass(frozen=True)
class SNRDecision:
    """Decision at the target; lower_db may be -inf under left censoring."""

    status: Status
    lower_db: float | None
    upper_db: float | None
    floor: Enclosure
    reason: str
    undecided_points: int | None
    scope: str
    evaluation_contract: Contract | None = None
    target: str | None = None

    @property
    def contract(self) -> Contract:
        """Common contract of the evaluations that produced this decision."""
        return self.evaluation_contract or self.floor.contract


@dataclass(frozen=True)
class ComparisonRow:
    """One approximation row; the diagnostic is always relative to the exact PPP."""

    label: str
    floor: Enclosure
    decision: SNRDecision
    diagnostic: Literal["falsely feasible", "masked"] | None = None


@dataclass(frozen=True)
class ThresholdDifference:
    """Enclosure in dB of a direct difference of finite thresholds."""

    lower: float
    upper: float

    def format(self, places: int = 4) -> str:
        """Outward decimal display, including on fine grids."""
        if type(places) is not int or not 0 <= places <= 30:
            raise ValueError("places must be an integer between 0 and 30")
        with localcontext() as context:
            context.prec = 400
            q = Decimal(1).scaleb(-places)
            lo = Decimal.from_float(self.lower).quantize(q, rounding=ROUND_FLOOR)
            hi = Decimal.from_float(self.upper).quantize(q, rounding=ROUND_CEILING)
        return f"[{lo:.{places}f}, {hi:.{places}f}]"
