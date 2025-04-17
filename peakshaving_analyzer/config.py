import calendar
import logging
from datetime import datetime

import pandas as pd
import pgeocode
import requests
import yaml

log = logging.getLogger("peakshaving_config")


class Config:
    def __init__(self, config_path: str):
        """
        Initialize the Config class by loading values from a YAML file.

        Args:
            config_path (str): Path to the YAML configuration file.
        """
        log.info("Initializing Config class.")
        with open(config_path) as file:
            config = yaml.safe_load(file)
        log.info("Configuration file loaded successfully.")

        opti_values = config.get("optimization_parameters")
        self.name = opti_values.get("name")
        self.db_uri = opti_values.get("db_uri")
        self.overwrite_existing_optimization = opti_values.get("overwrite_existing_optimization")
        self.hours_per_timestep = opti_values.get("hours_per_timestep")
        self.add_storage = opti_values.get("add_storage")
        self.add_solar = opti_values.get("add_solar")
        self.auto_opt = opti_values.get("auto_opt")
        self.verbose = opti_values.get("verbose")
        log.info("Optimization parameters loaded.")

        eco_values = config.get("economic_parameters", {})
        self.overwrite_price_timeseries = eco_values.get("overwrite_price_timeseries")
        self.producer_energy_price = eco_values.get("producer_energy_price")
        self.grid_capacity_price = eco_values.get("grid_capacity_price")
        self.grid_energy_price = eco_values.get("grid_energy_price")
        self.pv_system_lifetime = eco_values.get("pv_system_lifetime")
        self.pv_system_cost_per_kwp = eco_values.get("pv_system_cost_per_kwp")
        self.inverter_lifetime = eco_values.get("inverter_lifetime")
        self.inverter_cost_per_kw = eco_values.get("inverter_cost_per_kw")
        self.storage_lifetime = eco_values.get("storage_lifetime")
        self.storage_cost_per_kwh = eco_values.get("storage_cost_per_kwh")
        self.interest_rate = eco_values.get("interest_rate") / 100

        tech_values = config.get("technical_parameters", {})
        self.max_storage_size_kwh = tech_values.get("max_storage_size_kwh")
        self.storage_charge_efficiency = tech_values.get("storage_charge_efficiency")
        self.storage_discharge_efficiency = tech_values.get("storage_discharge_efficiency")
        self.storage_charge_rate = tech_values.get("storage_charge_rate")
        self.storage_discharge_rate = tech_values.get("storage_discharge_rate")
        self.inverter_efficiency = tech_values.get("inverter_efficiency")
        self.max_pv_system_size_kwp = tech_values.get("max_pv_system_size_kwp")
        self.pv_system_kwp_per_m2 = tech_values.get("pv_system_kwp_per_m2")

        self.solver = config.get("solver", "appsi_highs")

        if self.verbose:
            log.setLevel(logging.INFO)

        self.consumption_timeseries = self.read_consumption_timeseries(config=config)

        self.n_timesteps = len(self.consumption_timeseries)
        self.leap_year = self.detect_leap_year()
        self.assumed_year = self._assume_year()
        self.timestamps = self._create_timestamps()

        if self.overwrite_price_timeseries:
            self.price_timeseries = self.create_price_timeseries()
        else:
            self.price_timeseries = self.read_price_timeseries(config=config)

        self.adjust_price_timeseries()

        if self.add_solar:
            self.postal_code = config.get("solar_timeseries").get("postal_code")
            if self.postal_code:
                log.info("Fetching solar timeseries using postal code.")
                self.solar_timeseries = self.fetch_solar_timeseries()
            else:
                log.info("Reading solar timeseries from CSV file.")
                self.solar_timeseries = self.read_solar_timeseries(config=config)

            # fill NaN with 0
            self.solar_timeseries.fillna(0, inplace=True)

        self.check_timeseries_length()

        log.info("Config class initialized successfully.")

    def read_consumption_timeseries(self, config):
        """Reads consumption timeseries from given file

        Returns:
            pd.Series: the consumption timeseries.
        """

        log.info("Reading consumption timeseries")

        cons_values = config.get("consumption_timeseries")
        path = cons_values.get("file_path")
        df = pd.read_csv(path)
        df.rename(columns={cons_values.get("value_column"): "consumption"}, inplace=True)
        log.info("Consumption timeseries loaded.")

        return df["consumption"]

    def _assume_year(self):
        """Assumes year for given timeseries.

        Returns:
            int: the assumed year
        """

        log.info("Assuming year.")
        year = datetime.now().year - 1
        if self.leap_year:
            while not calendar.isleap(year):
                year -= 1
        else:
            while calendar.isleap(year):
                year -= 1

        log.info(f"Assumed year to be {year}.")

        return year

    def _create_timestamps(self) -> pd.Series:
        """Creates timestamps from given information

        Returns:
            pd.Series: The timestamps
        """

        return pd.date_range(
            start=f"{self.assumed_year}-01-01",
            periods=self.n_timesteps,
            freq=f"{self.hours_per_timestep}H",
            tz="UTC",
        )

    def _resample_dataframe(self, df: pd.DataFrame):
        """Resamples given dataframe for provided details.

        Args:
            df (pd.DataFrame): The dataframe to resample.

        Returns:
            pd.DataFrame: the resampled dataframe.
        """

        log.info("Resampling solar timeseries to match your specifications")

        df["timestamp"] = pd.date_range(start=f"{self.assumed_year}-01-01", periods=len(df), freq="H")

        # upsample
        if self.hours_per_timestep < 1:
            # set index as needed for upsamling
            df.set_index("timestamp", inplace=True)

            # upsample using forward filling
            df = df.resample(rule=f"{self.hours_per_timestep}H", origin="start_day").ffill()

            # the last three quarter hours are missing as original timeseries ends on
            # Dec. 12th 23:00 and not 24:00 / Dec. 13th 00:00
            # so we reindex to include the missing timestamps
            df = df.reindex(
                labels=pd.date_range(
                    start=f"{self.assumed_year}",
                    periods=self.n_timesteps,
                    freq=f"{self.hours_per_timestep}H",
                )
            )

            # and fill the newly created timestamps
            df.fillna(method="ffill", inplace=True)

        # downsample
        else:
            # resample
            df = df.resample(rule=f"{self.hours_per_timestep}H", on="timestamp").mean()

        df.reset_index(drop=True, inplace=True)

        log.info("Successfully resampled solar timeseries.")

        return df

    def read_price_timeseries(self, config):
        """
        Read the price timeseries from the specified CSV file.

        Returns:
            pd.Series: The price timeseries.
        """
        log.info("Reading price timeseries from CSV file.")
        df = pd.read_csv(config.get("price_timeseries").get("file_path"))
        df.rename(
            columns={config.get("price_timeseries").get("value_column"): "grid"},
            inplace=True,
        )
        df["consumption_site"] = 0
        log.info("Price timeseries successfully read and processed.")

        return df[["consumption_site", "grid"]]

    def create_price_timeseries(self):
        """Creates price timeseries from year and given fixed price.

        Returns:
            pd.Series: The price timeseries
        """

        log.info("Creating price timeseries from fixed price.")
        df = pd.DataFrame()

        year = datetime.now().year - 1
        if self.leap_year:
            while not calendar.isleap(year):
                year -= 1
        else:
            while calendar.isleap(year):
                year -= 1

        df["timestamp"] = pd.date_range(
            f"{year}-01-01",
            freq=f"{self.hours_per_timestep}H",
            periods=self.n_timesteps,
        )
        df["grid"] = self.producer_energy_price
        df["consumption_site"] = 0

        log.info("Price timeseries successfully created.")

        return df[["grid", "consumption_site"]]

    def adjust_price_timeseries(self):
        """Removes negative values from price timeseries"""

        if len(self.price_timeseries[self.price_timeseries < 0]) > 0:
            msg = "We can't integrate negative prices yet. We set the "
            msg += "negative prices in your price timeseries to 0."
            log.warning(msg)

        self.price_timeseries[self.price_timeseries < 0] = 0

    def detect_leap_year(self):
        """
        Detect if given timeseries is a leap year.

        Returns:
            bool: True if the current year is a leap year, False otherwise.
        """

        return self.n_timesteps * self.hours_per_timestep == 8784

    def fetch_solar_timeseries(self):
        """
        Read the solar timeseries from brightsky.

        Returns:
            pd.Series: The solar timeseries.
        """
        log.info("Fetching solar timeseries from BrightSky API.")
        # convert postal code to coordinates
        nomi = pgeocode.Nominatim("de")
        q = nomi.query_postal_code(self.postal_code)
        lat, lon = q["latitude"], q["longitude"]
        log.info(f"Coordinates for postal code {self.postal_code}: Latitude={lat}, Longitude={lon}")

        # make API Call
        url = f"https://api.brightsky.dev/weather?lat={lat}&lon={lon}&country=DE"
        url += f"&date={self.assumed_year}-01-01T00:00:00&last_date={self.assumed_year}-12-31T23:45:00"
        url += "&timezone=auto&format=json"
        log.info(f"Making API call to: {url}")
        data = requests.get(url).json()

        # put data in dataframe
        df = pd.DataFrame(data["weather"])[["solar"]]
        log.info("Solar timeseries data fetched successfully.")

        # rename to location in ESM, add grid column with no operation possible
        df.rename(columns={"solar": "consumption_site"}, inplace=True)
        df["grid"] = 0

        # resample to match hours per timestep
        if self.hours_per_timestep != 1:
            df = self._resample_dataframe(df)

        # convert from kWh/m2 to kW
        # kWh/m2/h = kW/m2 = 1000W/m2
        # no converseion necessary, as solar modules are tested with 1000W/m2

        return df

    def read_solar_timeseries(self, config):
        """
        Read the solar timeseries from the specified CSV file.

        Returns:
            pd.Series: The solar timeseries.
        """
        log.info("Reading solar timeseries from CSV file.")
        df = pd.read_csv(config.get("solar_timeseries").get("file_path"), index_col=0)
        df.rename(
            columns={config.get("solar_timeseries").get("value_column"): "consumption_site"},
            inplace=True,
        )
        df["grid"] = 0
        log.info("Solar timeseries successfully read and processed.")

        return df

    def check_timeseries_length(self):
        """
        Check if the length of the consumption and price timeseries matches the expected number of timesteps.

        Raises:
            ValueError: If the length of the timeseries does not match.
        """
        log.info("Checking length of timeseries.")
        if len(self.consumption_timeseries) != self.n_timesteps:
            msg = "Length of consumption timeseries does not match expected number of timesteps. "
            msg += (
                f"Expected number of timesteps: {self.n_timesteps}, given timesteps: {len(self.consumption_timeseries)}"
            )
            raise ValueError(msg)
        if len(self.price_timeseries) != self.n_timesteps:
            msg = "Length of price timeseries does not match expected number of timesteps. "
            msg += f"Expected number of timesteps: {self.n_timesteps}, given timesteps: {len(self.price_timeseries)}"
            raise ValueError(msg)
        if hasattr(self, "solar_timeseries") and len(self.solar_timeseries) != self.n_timesteps:
            msg = "Length of solar timeseries does not match expected number of timesteps. "
            msg += f"Expected number of timesteps: {self.n_timesteps}, given timesteps: {len(self.solar_timeseries)}"
            raise ValueError(msg)
        log.info("Timeseries length check passed.")
