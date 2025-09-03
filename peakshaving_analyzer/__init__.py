# __init__.py

import logging

from peakshaving_analyzer.input import Config, load_oeds_config, load_yaml_config
from peakshaving_analyzer.output import Results
from peakshaving_analyzer.PSA import PeakShavingAnalyzer

logging.basicConfig(level=logging.WARNING)

"""
PeakShaverAnalyzer package initialization.
"""

__all__ = ["PeakShavingAnalyzer", "Config", "Results", "load_yaml_config", "load_oeds_config"]
__version__ = "0.0.3"
