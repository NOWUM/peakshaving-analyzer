import calendar
import datetime
import logging
from pathlib import Path

import pandas as pd
import yaml

from peakshaving_analyzer import Config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def load_yaml(config_file_path: Path | str) -> Config:
    # read in configuration file
    with open(config_file_path) as file:
        data = yaml.safe_load(file)
        log.info("Configuration file loaded")

    # read in consumption timeseries
    data["consumption_timeseries"] = pd.read_csv(data["consumption_file_path"])[data["consumption_value_column"]]
    log.info("Consumption timeseries loaded")

    # read in timestamps if provided
    if data.get("timestamp_column"):
        data["timestamps"] = pd.read_csv(data["consumption_timeseries_path"])[data["timestamp_column"]]
        log.info("Timestamps loaded")
    else:
        data["timestamps"] = None

    # create metadata for timeseries
    _create_timeseries_metadata(data)
    log.info("Timeseries metadata created")

    # read or create price timeseries
    data["price_timeseries"] = _read_or_create_price_timeseries(data)
    log.info("Price timeseries loaded or created")


def _create_timeseries_metadata(data):
    # if no timestamps are given, we create them
    if data["timestamps"] is None:
        data["n_timesteps"] = len(data["consumption_timeseries"])
        data["leap_year"] = _detect_leap_year(data)
        data["assumed_year"] = _assume_year(data)
        data["timestamps"] = pd.date_range(
            start=f"{data['assumed_year']}-01-01",
            periods=data["n_timesteps"],
            freq=f"{data['hours_per_timestep']}h",
            tz="UTC",
        )
    # otherwise we just create the metadata from the timestamps
    else:
        data["n_timesteps"] = len(data["timestamps"])
        data["leap_year"] = calendar.isleap(data["timestamps"][0].year)
        data["assumed_year"] = data["timestamps"][0].year


def _detect_leap_year(data):
    """
    Detect if given timeseries is a leap year.

    Returns:
        bool: True if the current year is a leap year, False otherwise.
    """

    return data["n_timesteps"] * data["hours_per_timestep"] == 8784


def _assume_year(data):
    """Assumes year for given timeseries.

    Returns:
        int: the assumed year
    """

    log.info("Assuming year.")
    year = datetime.now().year - 1
    if data["leap_year"]:
        while not calendar.isleap(year):
            year -= 1
    else:
        while calendar.isleap(year):
            year -= 1

    log.info(f"Assumed year to be {year}.")

    return year


def _read_or_create_price_timeseries(data):
    # if no filepath is given, we either...
    if not data.get("price_file_path"):
        # throw an error if no price information is given
        if not data.get("producer_energy_price"):
            msg = "No price information found."
            msg += "Please provide either producer_energy_price or "
            msg += "price_file_path in the configuration file."
            log.error(msg)

        # ... or create a timeseries from a fixed price
        else:
            return pd.Series(data=data["producer_energy_price"], index=data["timestamps"])

    # if the filepath is given, we either ...
    else:
        # we overwrite the timeseries by given fixed price
        if data.get("overwrite_price_timeseries"):
            return pd.Series(data=data["producer_energy_price"], index=data["timestamps"])

        # or just read in the series from file
        else:
            return pd.read_csv(data["price_file_path"])[data["price_value_column"]]
