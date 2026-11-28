"""Numerical certificates for the thermal RIS-NOMA model of the Letter."""
from .models import (Model, Numerics, SNRGrid, Contract, Enclosure, SNRDecision,
                     ComparisonRow, ThresholdDifference)
from .api import (outage_enclosure, floor, required_snr, compare_approximations,
                  largest_interferer_bound, threshold_difference, clear_cache)
from ._banks import IntegrityError, BankNotAvailable
from ._prepare import prepare, PreparedBank
from ._fetch import fetch_banks, BankDownloadError

__version__ = "0.3.0"
__all__ = ["Model", "Numerics", "SNRGrid", "Contract", "Enclosure", "SNRDecision",
           "ComparisonRow", "ThresholdDifference", "outage_enclosure", "floor",
           "required_snr", "compare_approximations", "largest_interferer_bound",
           "threshold_difference", "clear_cache", "IntegrityError",
           "prepare", "PreparedBank", "BankNotAvailable", "fetch_banks", "BankDownloadError"]
