# __init__.py

import logging

from peakshaving_analyzer.config import Config, Results
from peakshaving_analyzer.output import OutputHandler
from peakshaving_analyzer.PSA import PeakShavingAnalyzer

logging.basicConfig(level=logging.WARNING)

"""
PeakShaverAnalyzer package initialization.
"""

__all__ = ["PeakShavingAnalyzer", "Config", "Results", "OutputHandler"]
__version__ = "0.0.3"
