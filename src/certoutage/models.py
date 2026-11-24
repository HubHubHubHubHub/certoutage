"""Modèle physique, réglages et résultats publics immuables."""
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
        raise ValueError(f"{name} : un nombre réel fini est requis, pas un booléen")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{name} : nombre réel invalide ({value!r})") from exc
    if not result.is_finite():
        raise ValueError(f"{name} doit être fini")
    return result


@dataclass(frozen=True)
class Model:
    """Modèle de la Letter. N est le nombre d'éléments PAR usager.

    m=1 : Rayleigh ; m=2 ou 3 : Nakagami à puissance moyenne unitaire.
    lam=0 donne le cas sans PPP. R0=1 et les constantes utiles restent fixes.
    """

    N: int = 24
    lam: Scalar = "0.1"
    eta: int = 4
    convention: Literal["C-TX", "C-INR"] = "C-TX"
    m: int = 1
    R0: Scalar = 1

    def __post_init__(self) -> None:
        if type(self.N) is not int or self.N not in SIZES:
            raise ValueError(f"N doit appartenir aux tailles certifiées {SIZES}")
        if type(self.m) is not int or self.m not in (1, 2, 3):
            raise ValueError("m doit être 1 (Rayleigh), 2 ou 3 (Nakagami couvert)")
        if type(self.eta) is not int or self.eta not in (3, 4):
            raise ValueError("eta doit être 3 ou 4 : seules ces transformées sont implémentées")
        if self.convention not in ("C-TX", "C-INR"):
            raise ValueError("convention doit être 'C-TX' ou 'C-INR'")
        lam = decimal(self.lam, "lam")
        if not 0 <= lam <= 10:
            raise ValueError("lam doit appartenir à [0, 10] dans cette phase ; une petite intensité peut donner un intervalle large")
        if decimal(self.R0, "R0") != 1:
            raise ValueError("R0=1 est fixé par la normalisation de la Letter")
        object.__setattr__(self, "lam", str(lam))
        object.__setattr__(self, "R0", 1)


@dataclass(frozen=True)
class Numerics:
    """Précision des requêtes ; les banques fournies restent certifiées à 160 bits."""

    precision_bits: int = 160
    ppp_dft_power: int = 18
    bank_policy: Literal["auto", "fresh"] = "auto"

    def __post_init__(self) -> None:
        if type(self.precision_bits) is not int or not 160 <= self.precision_bits <= 1024:
            raise ValueError("precision_bits doit être un entier entre 160 et 1024")
        if type(self.ppp_dft_power) is not int or not 12 <= self.ppp_dft_power <= 20:
            raise ValueError("ppp_dft_power doit être un entier entre 12 et 20")
        if self.bank_policy not in ("auto", "fresh"):
            raise ValueError("bank_policy doit être 'auto' ou 'fresh' (PPP et Gamma)")


@dataclass(frozen=True)
class SNRGrid:
    """Grille finie en dB ; bornes et pas sont des multiples de 1/128 dB."""

    start: Scalar = -40
    stop: Scalar = 96
    step: Scalar = "0.0625"

    def __post_init__(self) -> None:
        a, b, h = (Fraction(decimal(x, n)) for x, n in
                   ((self.start, "start"), (self.stop, "stop"), (self.step, "step")))
        if not -1000 <= a < b <= 1000 or h <= 0 or h > b - a:
            raise ValueError("grille : -1000 <= start < stop <= 1000 et 0 < step <= stop-start")
        if any((x * 128).denominator != 1 for x in (a, b, h)):
            raise ValueError("la grille doit utiliser des multiples exacts de 1/128 dB")
        if (b - a) % h:
            raise ValueError("stop-start doit être un multiple du pas")
        for n, x in (("start", a), ("stop", b), ("step", h)):
            # Bounded multiples of 1/128 are exactly representable in binary64.
            object.__setattr__(self, n, float(x))


@dataclass(frozen=True)
class Contract:
    """Portée du certificat, provenance et hypothèses attachées au résultat."""

    quantity: str
    source: Literal["provided-banks", "mixed", "analytic", "provided-certificate"]
    precision_bits: int
    banks: tuple[tuple[str, str], ...] = ()
    interval_library: str = "python-flint 0.9.0 / Arb-Acb"
    bank_precision_bits: int = 160
    assumptions: tuple[str, ...] = (
        "indépendance des amplitudes, thermique et PPP marqué",
        "W=(somme sqrt(E F))²(10+Z)²/101, Z normal standard",
        "puissances E,F Exp(1) ou Gamma(m,rate=m), m entier couvert",
        "PPP plan hors R0=1 ; marques de puissance Exp(1)",
        "d1=80/3, d2=160 ; CSI et alignement de phase parfaits",
        "certificat numérique du modèle ; aucune garantie physique ou de latence",
    )
    notes: tuple[str, ...] = ()
    parameters: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Enclosure:
    """Bornes binaires64 vers l'extérieur, sans arrondi décoratif implicite."""

    lower: float
    upper: float
    contract: Contract

    def __post_init__(self) -> None:
        if not (math.isfinite(self.lower) and math.isfinite(self.upper)
                and 0 <= self.lower <= self.upper <= 1):
            raise ArithmeticError(f"encadrement de probabilité invalide : {self.lower}, {self.upper}")

    def as_dict(self) -> dict[str, float]:
        """Les deux bornes brutes, notamment pour les régressions d'archive."""
        return {"lower": self.lower, "upper": self.upper}

    def format(self, *, scale: Scalar = 1, places: int = 4) -> str:
        """Affichage décimal extérieur de l'intervalle divisé par scale."""
        s = decimal(scale, "scale")
        if s <= 0 or type(places) is not int or not 0 <= places <= 30:
            raise ValueError("scale doit être positif et places un entier entre 0 et 30")
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
    """Décision à la cible ; lower_db peut être -inf en cas de censure gauche."""

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
        """Contrat commun des évaluations ayant produit cette décision."""
        return self.evaluation_contract or self.floor.contract


@dataclass(frozen=True)
class ComparisonRow:
    """Une ligne d'approximation ; diagnostic toujours relatif au PPP exact."""

    label: str
    floor: Enclosure
    decision: SNRDecision
    diagnostic: Literal["falsely feasible", "masked"] | None = None


@dataclass(frozen=True)
class ThresholdDifference:
    """Encadrement en dB d'une différence directe de seuils finis."""

    lower: float
    upper: float

    def format(self, places: int = 4) -> str:
        """Affichage décimal extérieur, y compris sur les grilles fines."""
        if type(places) is not int or not 0 <= places <= 30:
            raise ValueError("places doit être un entier entre 0 et 30")
        with localcontext() as context:
            context.prec = 400
            q = Decimal(1).scaleb(-places)
            lo = Decimal.from_float(self.lower).quantize(q, rounding=ROUND_FLOOR)
            hi = Decimal.from_float(self.upper).quantize(q, rounding=ROUND_CEILING)
        return f"[{lo:.{places}f}, {hi:.{places}f}]"
