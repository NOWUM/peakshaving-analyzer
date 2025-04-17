# __init__.py

import logging

from peakshaving_analyzer.config import Config
from peakshaving_analyzer.DBHandler import DatabaseHandler
from peakshaving_analyzer.PSA import PeakShavingAnalyzer

logging.basicConfig(level=logging.WARNING)

"""
PeakShaverAnalyzer package initialization.
"""

__all__ = ["PeakShavingAnalyzer", "Config", "DatabaseHandler"]
__version__ = "0.1.0"
__author__ = "Christoph Komanns"
