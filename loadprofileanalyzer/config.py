import yaml

import pandas as pd
import pgeocode
from datetime import datetime
import requests


class Config:
    def __init__(self, config_path: str):
        """
        Initialize the Config class by loading values from a YAML file.

        Args:
            config_path (str): Path to the YAML configuration file.
        """
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)

        cons_values = config.get('consumption_timeseries')
        self.consumption_timeseries = pd.read_csv(cons_values.get('file_path'))[cons_values.get('value_column')]

        opti_values = config.get('optimization_parameters')
        self.name = opti_values.get('name')
        self.db_uri = opti_values.get('db_uri')
        self.overwrite_existing_optimization = opti_values.get('overwrite_existing_optimization')
        self.postal_code = opti_values.get('postal_code')
        self.hours_per_timestep = opti_values.get('hours_per_timestep')
        self.add_storage = opti_values.get('add_storage')
        self.add_solar = opti_values.get('add_solar')
        self.auto_opt = opti_values.get('auto_opt')
        self.verbose = opti_values.get('verbose')
        
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
        self.pv_module_efficiency = tech_values.get('pv_module_efficiency')

        self.solver = config.get('solver', 'appsi_highs')

        self.price_timeseries = self.read_price_timeseries(config=config)

        if self.overwrite_price_timeseries:
            self.price_timeseries['grid'] = self.producer_energy_price

        if self.add_solar:
            self.solar_timeseries = self.get_solar_timeseries(config=config)


    def read_price_timeseries(self, config):
        """
        Read the price timeseries from the specified CSV file.

        Returns:
            pd.Series: The price timeseries.
        """
        df = pd.read_csv(config.get('price_timeseries').get('file_path'), index_col=0)
        df.rename(columns={config.get('price_timeseries').get('value_column'): 'grid'}, inplace=True)
        df["consumption_site"] = 0

        return df
    

    def get_solar_timeseries(self, config):
        """
        Read the solar timeseries from brightsky.

        Returns:
            pd.Series: The solar timeseries.
        """

        # convert postal code to coordinates
        nomi = pgeocode.Nominatim("de")
        q = nomi.query_postal_code(self.postal_code)
        lat, lon = q["latitude"], q["longitude"]

        # make API Call
        year = datetime.now().year - 1
        url = f"https://api.brightsky.dev/weather?lat={lat}&lon={lon}&country=DE"
        url += f"&date={year}-01-01T00:00:00&last_date={year}-12-31T23:45:00"
        url += f"&timezone=auto&format=json"
        data = requests.get(url).json()

        log.info("Got data from brightsky")

        # put data in dataframe
        df = pd.DataFrame(data["weather"])[["solar"]]

        # rename to location in ESM, add grid column with no operation possible
        df.rename(columns={"solar": "consumption_site"}, inplace=True)
        df["grid"] = 0

        # convert from kWh/m2 to kW
        # kWh/m2/h = kW/m2 = 1000W/m2
        # no converseion necessary, as solar modules are tested with 1000W/m2

        return df.head()
