import yaml

import pandas as pd
import pgeocode
from datetime import datetime
import requests


import logging
log = logging.getLogger("config")


class Config:
    def __init__(self, config_path: str):
        """
        Initialize the Config class by loading values from a YAML file.

        Args:
            config_path (str): Path to the YAML configuration file.
        """
        log.info("Initializing Config class.")
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        log.info("Configuration file loaded successfully.")

        cons_values = config.get('consumption_timeseries')
        self.consumption_timeseries = pd.read_csv(cons_values.get('file_path'))[cons_values.get('value_column')]
        log.info("Consumption timeseries loaded.")

        opti_values = config.get('optimization_parameters')
        self.name = opti_values.get('name')
        self.db_uri = opti_values.get('db_uri')
        self.overwrite_existing_optimization = opti_values.get('overwrite_existing_optimization')
        self.hours_per_timestep = opti_values.get('hours_per_timestep')
        self.add_storage = opti_values.get('add_storage')
        self.add_solar = opti_values.get('add_solar')
        self.auto_opt = opti_values.get('auto_opt')
        self.verbose = opti_values.get('verbose')
        log.info("Optimization parameters loaded.")

        eco_values = config.get('economic_parameters', {})
        self.overwrite_price_timeseries = eco_values.get('overwrite_price_timeseries')
        self.producer_energy_price = eco_values.get('producer_energy_price')
        self.grid_capacity_price = eco_values.get('grid_capacity_price')
        self.grid_energy_price = eco_values.get('grid_energy_price')
        self.pv_system_lifetime = eco_values.get('pv_system_lifetime')
        self.pv_system_cost_per_kwp = eco_values.get('pv_system_cost_per_kwp')
        self.inverter_lifetime = eco_values.get('inverter_lifetime')
        self.inverter_cost_per_kw = eco_values.get('inverter_cost_per_kw')
        self.storage_lifetime = eco_values.get('storage_lifetime')
        self.storage_cost_per_kwh = eco_values.get('storage_cost_per_kwh')
        self.interest_rate = eco_values.get('interest_rate')

        tech_values = config.get('technical_parameters', {})
        self.max_storage_size_kwh = tech_values.get('max_storage_size_kwh')
        self.storage_charge_efficiency = tech_values.get('storage_charge_efficiency')
        self.storage_discharge_efficiency = tech_values.get('storage_discharge_efficiency')
        self.storage_charge_rate = tech_values.get('storage_charge_rate')
        self.storage_discharge_rate = tech_values.get('storage_discharge_rate')
        self.inverter_efficiency = tech_values.get('inverter_efficiency')
        self.max_pv_system_size_kwp = tech_values.get('max_pv_system_size_kwp')
        self.pv_system_kwp_per_m2 = tech_values.get('pv_system_kwp_per_m2')

        self.solver = config.get('solver', 'appsi_highs')

        if self.verbose:
            log.setLevel(logging.INFO)

        self.price_timeseries = self.read_price_timeseries(config=config)

        if self.overwrite_price_timeseries:
            self.price_timeseries['grid'] = self.producer_energy_price
            log.info("Price timeseries overwritten with producer energy price.")

        if self.add_solar:
            self.postal_code = config.get('solar_timeseries').get('postal_code')
            if self.postal_code:
                log.info("Fetching solar timeseries using postal code.")
                self.solar_timeseries = self.fetch_solar_timeseries()
            else:
                log.info("Reading solar timeseries from CSV file.")
                self.solar_timeseries = self.read_solar_timeseries(config=config)

        log.info("Config class initialized successfully.")


    def read_price_timeseries(self, config):
        """
        Read the price timeseries from the specified CSV file.

        Returns:
            pd.Series: The price timeseries.
        """
        log.info("Reading price timeseries from CSV file.")
        df = pd.read_csv(config.get('price_timeseries').get('file_path'), index_col=0)
        df.rename(columns={config.get('price_timeseries').get('value_column'): 'grid'}, inplace=True)
        df["consumption_site"] = 0
        log.info("Price timeseries successfully read and processed.")

        return df
    

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
        year = datetime.now().year - 1
        url = f"https://api.brightsky.dev/weather?lat={lat}&lon={lon}&country=DE"
        url += f"&date={year}-01-01T00:00:00&last_date={year}-12-31T23:45:00"
        url += f"&timezone=auto&format=json"
        log.info(f"Making API call to: {url}")
        data = requests.get(url).json()

        # put data in dataframe
        df = pd.DataFrame(data["weather"])[["solar"]]
        log.info("Solar timeseries data fetched successfully.")

        # rename to location in ESM, add grid column with no operation possible
        df.rename(columns={"solar": "consumption_site"}, inplace=True)
        df["grid"] = 0

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
        df = pd.read_csv(config.get('solar_timeseries').get('file_path'), index_col=0)
        df.rename(columns={config.get('solar_timeseries').get('value_column'): 'consumption_site'}, inplace=True)
        df["grid"] = 0
        log.info("Solar timeseries successfully read and processed.")

        return df.head()
