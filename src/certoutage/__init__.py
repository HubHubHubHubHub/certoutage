"""Numerical certificates for the thermal RIS-NOMA model of the Letter."""
from .models import (Model, Numerics, SNRGrid, Contract, Enclosure, SNRDecision,
                     ComparisonRow, ThresholdDifference)
from .api import (outage_enclosure, floor, required_snr, compare_approximations,
                  largest_interferer_bound, threshold_difference, clear_cache)
from ._banks import IntegrityError

__version__ = "0.2.0"
__all__ = ["Model", "Numerics", "SNRGrid", "Contract", "Enclosure", "SNRDecision",
           "ComparisonRow", "ThresholdDifference", "outage_enclosure", "floor",
           "required_snr", "compare_approximations", "largest_interferer_bound",
           "threshold_difference", "clear_cache", "IntegrityError"]
