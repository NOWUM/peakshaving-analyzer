import calendar
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import pgeocode
import requests
import sqlalchemy
import yaml

from peakshaving_analyzer.common import IOHandler

log = logging.getLogger(__name__)


@dataclass
class Config(IOHandler):
    # general parameters
    name: str
    overwrite_existing_optimization: bool = False
    add_storage: bool = True
    add_solar: bool = False
    auto_opt: bool = False
    solver: str | None = "appsi_highs"
    verbose: bool = False
    postal_code: int | str | None = None

    # timeseries
    consumption_timeseries: pd.Series | None = None
    price_timeseries: pd.Series | None = None
    solar_generation_timeseries: pd.Series | None = None

    # economic parameters
    overwrite_price_timeseries: bool = False
    producer_energy_price: float = 0.1665
    grid_capacity_price: float = 101.22
    grid_energy_price: float = 0.046
    pv_system_lifetime: int = 30
    pv_system_cost_per_kwp: float = 1200.0
    inverter_lifetime: int = 15
    inverter_cost_per_kw: float = 180
    storage_lifetime: int = 15
    storage_cost_per_kwh: float = 285
    interest_rate: float = 2

    # technical parameters
    max_storage_size_kwh: float | None = None
    storage_charge_efficiency: float = 0.95
    storage_discharge_efficiency: float = 0.95
    storage_charge_rate: float = 5
    storage_discharge_rate: float = 5
    inverter_efficiency: float = 0.95
    max_pv_system_size_kwp: float | None = None
    pv_system_kwp_per_m2: float = 0.4

    # metadata needed for optimization (set by peakshaving analyzer)
    timestamps: pd.DatetimeIndex | None = None
    n_timesteps: int | None = None
    hours_per_timestep: float | None = None

    def timeseries_to_df(self):
        df = pd.DataFrame()

        df["consumption_kw"] = self.consumption_timeseries
        df["energy_price_eur"] = self.price_timeseries
        df["solar_generation_kw"] = self.solar_generation_timeseries

        return df


def load_yaml_config(config_file_path: Path | str) -> Config:
    config_path = Path(config_file_path)

    # read in configuration file
    with open(config_path) as file:
        data = yaml.safe_load(file)
        log.info("Configuration file loaded")

    # set log level according to flag
    if data.get("verbose", True):
        log.setLevel(level=logging.INFO)
    else:
        log.setLevel(level=logging.WARNING)

    # set config dir var
    data["config_dir"] = config_path.parent

    # read in consumption timeseries
    data["consumption_timeseries"] = pd.read_csv(data["config_dir"] / data["consumption_file_path"])[
        data["consumption_value_column"]
    ]
    log.info("Consumption timeseries loaded")

    # read in timestamps if provided
    if data.get("timestamp_column"):
        data["timestamps"] = pd.read_csv(data["config_dir"] / data["consumption_file_path"])[data["timestamp_column"]]
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
            data["solar_generation_timeseries"] = pd.read_csv(data["config_dir"] / data["solar_file_path"])[
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


def load_oeds_config(
    con: str | sqlalchemy.engine.Connection,
    profile_id: int,
    price_inflation_percent: float = 26.24,
    use_given_grid_prices: bool = True,
    producer_energy_price: float = 0.1665,
    *args,
    **kwargs,
) -> Config:
    """
    Loads a configuration for the Peak Shaving Analyzer from an OEDS (OpenEnergyDataServer).

    This function retrieves consumption and price time series for a given profile ID from the OEDS,
    applies optional price inflation, and constructs a Config object for optimization.

    Args:
        con (str or sqlalchemy.engine.Connection): Database connection string or SQLAlchemy connection object.
        profile_id (int): The profile ID to load from the database.
        price_inflation_percent (float, optional): Percentage to inflate grid prices. Default is 26.24.
        use_given_grid_prices (bool, optional): If True, use grid prices from the database. Default is True.
        producer_energy_price (float, optional): Fixed producer energy price if not using database prices. Default is 0.1665.
        *args: Additional positional arguments.
        **kwargs: Additional keyword arguments to override or supplement configuration.

    Returns:
        Config: A configuration object populated with time series and parameters from the database.

    Raises:
        ValueError: If required data cannot be loaded from the database.
    """

    data = {}

    data.update(kwargs)

    # set fixed values
    if "name" not in data:
        data["name"] = "profile_" + str(profile_id)
    data["hours_per_timestep"] = 0.25
    data["producer_energy_price"] = producer_energy_price
    log.info("Set fixed values")

    # load consumption timeseries
    data["consumption_timeseries"] = pd.read_sql(
        sql=f"""
        SELECT *
        FROM vea_industrial_load_profiles.load
        WHERE id = {profile_id}
        ORDER BY timestamp ASC
        """,
        con=con,
    )["value"]
    log.info("Loaded consumption timeseries from OEDS")

    data["n_timesteps"] = len(data["consumption_timeseries"])
    data["leap_year"] = True
    data["assumed_year"] = 2016
    data["timestamps"] = pd.date_range(
        start="2016-01-01",
        periods=data["n_timesteps"],
        freq="0.25h",
        tz="UTC",
    )
    log.info("Created timeseries metadata")

    data["price_timeseries"] = _read_or_create_price_timeseries(data)

    # if we want to add solar / PV...
    if data.get("add_solar"):
        # and we have a given timeseries for generation
        if data.get("solar_generation_timeseries"):
            # we dont need to do anything
            pass

        # if we have a given postal code
        elif data.get("postal_code"):
            # fetch the generation timeseries for this
            data["solar_generation_timeseries"] = _fetch_solar_timeseries(data)

        # if we dont have a given postal code
        elif not data.get("postal_code"):
            # get a random zip code that is possible for this profile ID
            data["postal_code"] = _get_random_zip_code(profile_id, con)
            log.info("Generated random postal code corresponding to given zip code start in OEDS")

        # and then add solar generation timeseries to data
        data["solar_generation_timeseries"] = _fetch_solar_timeseries(data)

    # calculate if consumption is over 2500h full load hours
    is_over_2500h = (data["consumption_timeseries"].sum() / 4) / data["consumption_timeseries"].max() > 2500

    if is_over_2500h:
        sql_flh_text = "under"
    else:
        sql_flh_text = "over"

    if use_given_grid_prices:
        # get capacity_price
        original_cap_price = pd.read_sql(
            sql=f"""
            SELECT capacity_price_{sql_flh_text}_2500h_eur_per_kw
            FROM vea_industrial_load_profiles.master
            WHERE id = {profile_id}
            """,
            con=con,
        )[f"capacity_price_{sql_flh_text}_2500h_eur_per_kw"].values[0]
        data["grid_capacity_price"] = original_cap_price * (1 + price_inflation_percent / 100)
        log.info(f"Retrieved grid_capacity_price and updated with an inflation of {price_inflation_percent}%")

        # get energy_price
        original_energy_price = pd.read_sql(
            sql=f"""
            SELECT energy_price_{sql_flh_text}_2500h_eur_per_kwh
            FROM vea_industrial_load_profiles.master
            WHERE id = {profile_id}
            """,
            con=con,
        )[f"energy_price_{sql_flh_text}_2500h_eur_per_kwh"].values[0]
        log.info("")
        data["grid_energy_price"] = original_energy_price * (1 + price_inflation_percent / 100)
        log.info(f"Retrieved grid_energy_price and updated with an inflation of {price_inflation_percent}%")

    _remove_unused_keys(data)

    return Config(**data)


def _create_timeseries_metadata(data):
    # if no timestamps are given, we create them
    if not data.get("timestamps", None):
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
            raise ValueError

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
    if data["producer_energy_price"] < 0:
        msg = "Producer energy price is negative."
        log.error(msg)
        raise ValueError(msg)

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
    df = pd.read_csv(data["config_dir"] / data["price_file_path"])
    df.rename(
        columns={data.get("price_value_column", "value"): "grid"},
        inplace=True,
    )
    df["consumption_site"] = 0
    df.loc[df["grid"] < 0, "grid"] = 0  # set negative prices to zero
    log.info("Price timeseries successfully read and processed.")

    return df[["consumption_site", "grid"]]


def _get_random_zip_code(profile_id: int, con: str | sqlalchemy.engine.Connection):
    zip_code_start = pd.read_sql(
        f"SELECT zip_code FROM vea_industrial_load_profiles.master WHERE id = {profile_id}", con
    )["zip_code"].values[0]
    zip_code_start = str(zip_code_start)

    all_zip_codes = pgeocode.Nominatim("de")._index_postal_codes()
    zip_code_range = all_zip_codes[all_zip_codes["postal_code"].str.startswith(zip_code_start)]

    return zip_code_range["postal_code"].sample(1).values[0]


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

    df.fillna(0, inplace=True)

    # resample to match hours per timestep
    if data["hours_per_timestep"] != 1:
        df = _resample_dataframe(
            df,
            hours_per_timestep=data["hours_per_timestep"],
            assumed_year=data["assumed_year"],
            n_timesteps=data["n_timesteps"],
        )

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
        "leap_year",
        "assumed_year",
        "config_dir",
    ]
    for key in keys_to_remove:
        data.pop(key, None)
    log.info("Unused keys removed.")
