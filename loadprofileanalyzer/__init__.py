# __init__.py

from loadprofileanalyzer.config import Config
from loadprofileanalyzer.LPA import LoadProfileAnalyzer

"""
LoadProfileAnalyzer package initialization.
"""

__all__ = ["LoadProfileAnalyzer", "Config"]
__version__ = "0.1.0"
__author__ = "Christoph Komanns"