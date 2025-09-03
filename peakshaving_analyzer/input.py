import calendar
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import pgeocode
import requests
import yaml

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@dataclass
class Config:
    # general parameters
    name: str
    db_uri: str | None = None
    overwrite_existing_optimization: bool = False
    add_storage: bool = True
    add_solar: bool = False
    auto_opt: bool = False
    solver: str | None = "appsi_highs"
    verbose: bool = False

    # timeseries
    consumption_timeseries: pd.Series | None = None
    price_timeseries: pd.Series | None = None
    solar_generation_timeseries: pd.Series | None = None

    # economic parameters
    overwrite_price_timeseries: bool = False
    producer_energy_price: float | None = None
    grid_capacity_price: float | None = None
    grid_energy_price: float | None = None
    pv_system_lifetime: int | None = None
    pv_system_cost_per_kwp: float | None = None
    inverter_lifetime: int | None = None
    inverter_cost_per_kw: float | None = None
    storage_lifetime: int | None = None
    storage_cost_per_kwh: float | None = None
    interest_rate: float | None = None

    # technical parameters
    max_storage_size_kwh: float | None = None
    storage_charge_efficiency: float | None = None
    storage_discharge_efficiency: float | None = None
    storage_charge_rate: float | None = None
    storage_discharge_rate: float | None = None
    inverter_efficiency: float | None = None
    max_pv_system_size_kwp: float | None = None
    pv_system_kwp_per_m2: float | None = None

    # metadata needed for optimization (set by peakshaving analyzer)
    timestamps: pd.DatetimeIndex | None = None
    n_timesteps: int | None = None
    hours_per_timestep: float | None = None


def load_yaml_config(config_file_path: Path | str) -> Config:
    # read in configuration file
    with open(config_file_path) as file:
        data = yaml.safe_load(file)
        log.info("Configuration file loaded")

    # read in consumption timeseries
    data["consumption_timeseries"] = pd.read_csv(data["consumption_file_path"])[data["consumption_value_column"]]
    log.info("Consumption timeseries loaded")

    # read in timestamps if provided
    if data.get("timestamp_column"):
        data["timestamps"] = pd.read_csv(data["consumption_file_path"])[data["timestamp_column"]]
        log.info("Timestamps loaded")
    else:
        data["timestamps"] = None

    # create metadata for timeseries
    _create_timeseries_metadata(data)
    log.info("Timeseries metadata created")

    # read or create price timeseries
    data["price_timeseries"] = _read_or_create_price_timeseries(data)
    log.info("Price timeseries loaded or created")

    if data["add_solar"]:
        if data["solar_file_path"]:
            data["solar_generation_timeseries"] = pd.read_csv(data["solar_file_path"])[
                data.get("solar_value_column", "value")
            ]
            log.info("Solar generation timeseries loaded")
        elif data["postal_code"]:
            data["solar_generation_timeseries"] = _fetch_solar_timeseries(data)
            log.info("Solar generation timeseries retrieved from brightsky")
        else:
            msg = "No solar generation timeseries available."
            msg += " Setting add_solar to False."
            log.warning(msg)
            data["add_solar"] = False

    _check_timeseries_length(data)

    _remove_unused_keys(data)

    return Config(**data)


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
            return _create_price_timeseries(data)

    # if the filepath is given, we either ...
    else:
        # we overwrite the timeseries by given fixed price
        if data.get("overwrite_price_timeseries"):
            return _create_price_timeseries(data)

        # or just read in the series from file
        else:
            return _read_price_timeseries(data)


def _create_price_timeseries(data):
    """Creates price timeseries from year and given fixed price.

    Returns:
        pd.Series: The price timeseries
    """

    log.info("Creating price timeseries from fixed price.")
    df = pd.DataFrame()

    year = datetime.now().year - 1
    if data["leap_year"]:
        while not calendar.isleap(year):
            year -= 1
    else:
        while calendar.isleap(year):
            year -= 1

    df["timestamp"] = pd.date_range(
        f"{data['assumed_year']}-01-01",
        freq=f"{data['hours_per_timestep']}h",
        periods=data["n_timesteps"],
    )
    df["grid"] = data["producer_energy_price"]
    df["consumption_site"] = 0

    log.info("Price timeseries successfully created.")

    return df[["grid", "consumption_site"]]


def _read_price_timeseries(data):
    """
    Read the price timeseries from the specified CSV file.

    Returns:
        pd.Series: The price timeseries.
    """
    log.info("Reading price timeseries from CSV file.")
    df = pd.read_csv(data["price_file_path"])
    df.rename(
        columns={data.get("price_value_column", "value"): "grid"},
        inplace=True,
    )
    df["consumption_site"] = 0
    log.info("Price timeseries successfully read and processed.")

    return df[["consumption_site", "grid"]]


def _fetch_solar_timeseries(data):
    """
    Read the solar timeseries from brightsky.

    Returns:
        pd.Series: The solar timeseries.
    """
    log.info("Fetching solar timeseries from BrightSky API.")
    # convert postal code to coordinates
    nomi = pgeocode.Nominatim("de")
    q = nomi.query_postal_code(data["postal_code"])
    lat, lon = q["latitude"], q["longitude"]
    log.info(f"Coordinates for postal code {data['postal_code']}: Latitude={lat}, Longitude={lon}")

    # make API Call
    url = f"https://api.brightsky.dev/weather?lat={lat}&lon={lon}&country=DE"
    url += f"&date={data['assumed_year']}-01-01T00:00:00&last_date={data['assumed_year']}-12-31T23:45:00"
    url += "&timezone=auto&format=json"
    log.info(f"Making API call to: {url}")
    weather_data = requests.get(url).json()

    # put data in dataframe
    df = pd.DataFrame(weather_data["weather"])[["solar"]]
    log.info("Solar timeseries data fetched successfully.")

    # rename to location in ESM, add grid column with no operation possible
    df.rename(columns={"solar": "consumption_site"}, inplace=True)
    df["grid"] = 0

    # resample to match hours per timestep
    if data["hours_per_timestep"] != 1:
        df = _resample_dataframe(df)

    # convert from kWh/m2 to kW
    # kWh/m2/h = kW/m2 = 1000W/m2
    # no converseion necessary, as solar modules are tested with 1000W/m2

    return df


def _resample_dataframe(df: pd.DataFrame, hours_per_timestep: float, assumed_year: int, n_timesteps: int):
    """Resamples given dataframe for provided details.

    Args:
        df (pd.DataFrame): The dataframe to resample.

    Returns:
        pd.DataFrame: the resampled dataframe.
    """

    log.info("Resampling solar timeseries to match your specifications")

    df["timestamp"] = pd.date_range(start=f"{assumed_year}-01-01", periods=len(df), freq="H")

    # upsample
    if hours_per_timestep < 1:
        # set index as needed for upsamling
        df.set_index("timestamp", inplace=True)

        # upsample using forward filling
        df = df.resample(rule=f"{hours_per_timestep}H", origin="start_day").ffill()

        # the last three quarter hours are missing as original timeseries ends on
        # Dec. 12th 23:00 and not 24:00 / Dec. 13th 00:00
        # so we reindex to include the missing timestamps
        df = df.reindex(
            labels=pd.date_range(
                start=f"{assumed_year}",
                periods=n_timesteps,
                freq=f"{hours_per_timestep}H",
            )
        )

        # and fill the newly created timestamps
        df.fillna(method="ffill", inplace=True)

    # downsample
    else:
        # resample
        df = df.resample(rule=f"{hours_per_timestep}H", on="timestamp").mean()

    df.reset_index(drop=True, inplace=True)

    log.info("Successfully resampled solar timeseries.")

    return df


def _check_timeseries_length(data):
    """
    Check if the length of the consumption and price timeseries matches the expected number of timesteps.

    Raises:
        ValueError: If the length of the timeseries does not match.
    """
    log.info("Checking length of timeseries.")
    if len(data["consumption_timeseries"]) != data["n_timesteps"]:
        msg = "Length of consumption timeseries does not match expected number of timesteps. "
        msg += f"Expected number of timesteps: {len(data['n_timesteps'])}, given timesteps: {len(data['consumption_timeseries'])}"
        raise ValueError(msg)
    if len(data["price_timeseries"]) != data["n_timesteps"]:
        msg = "Length of price timeseries does not match expected number of timesteps. "
        msg += f"Expected number of timesteps: {data['n_timesteps']}, given timesteps: {len(data['price_timeseries'])}"
        raise ValueError(msg)
    if "solar_generation_timeseries" in data and len(data["solar_generation_timeseries"]) != data["n_timesteps"]:
        msg = "Length of solar timeseries does not match expected number of timesteps. "
        msg += f"Expected number of timesteps: {data['n_timesteps']}, given timesteps: {len(data['solar_generation_timeseries'])}"
        raise ValueError(msg)
    log.info("Timeseries length check passed.")


def _remove_unused_keys(data):
    """
    Remove unused keys from the data dictionary.
    """
    log.info("Removing unused keys from data.")
    keys_to_remove = [
        "timestamp_column",
        "consumption_file_path",
        "consumption_value_column",
        "price_file_path",
        "price_value_column",
        "solar_file_path",
        "solar_value_column",
        "postal_code",
        "leap_year",
        "assumed_year",
    ]
    for key in keys_to_remove:
        data.pop(key, None)
    log.info("Unused keys removed.")
