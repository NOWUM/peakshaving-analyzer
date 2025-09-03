# __init__.py

import logging

from peakshaving_analyzer.input import Config, load_yaml_config
from peakshaving_analyzer.output import OutputHandler, Results
from peakshaving_analyzer.PSA import PeakShavingAnalyzer

logging.basicConfig(level=logging.WARNING)

"""
PeakShaverAnalyzer package initialization.
"""

__all__ = ["PeakShavingAnalyzer", "Config", "Results", "OutputHandler", "load_yaml_config"]
__version__ = "0.0.3"
