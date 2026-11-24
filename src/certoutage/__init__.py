"""Certificats numériques pour le modèle thermique RIS-NOMA de la Letter."""
from .models import (Model, Numerics, SNRGrid, Contract, Enclosure, SNRDecision,
                     ComparisonRow, ThresholdDifference)
from .api import (outage_enclosure, floor, required_snr, compare_approximations,
                  largest_interferer_bound, threshold_difference, clear_cache)
from ._banks import IntegrityError

__version__ = "0.1.0"
__all__ = ["Model", "Numerics", "SNRGrid", "Contract", "Enclosure", "SNRDecision",
           "ComparisonRow", "ThresholdDifference", "outage_enclosure", "floor",
           "required_snr", "compare_approximations", "largest_interferer_bound",
           "threshold_difference", "clear_cache", "IntegrityError"]
