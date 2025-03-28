import yaml

import pandas as pd


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
        self.hours_per_timestep = opti_values.get('hours_per_timestep')
        self.add_storage = opti_values.get('add_storage')
        self.add_solar = opti_values.get('add_solar')
        self.auto_opt = opti_values.get('auto_opt')
        self.verbose = opti_values.get('verbose')
        self.db_uri = opti_values.get('db_uri')
        self.overwrite_existing_optimization = opti_values.get('overwrite_existing_optimization')
        
        eco_values = config.get('economic_parameters', {})
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


    def __repr__(self):
        """
        String representation of the Config object for debugging.
        """
        return (
            f"Config(producer_energy_price={self.producer_energy_price}, "
            f"grid_capacity_price={self.grid_capacity_price}, "
            f"grid_energy_price={self.grid_energy_price}, "
            f"pv_system_lifetime={self.pv_system_lifetime}, "
            f"pv_system_cost_per_kwp={self.pv_system_cost_per_kwp}, "
            f"inverter_lifetime={self.inverter_lifetime}, "
            f"inverter_cost_per_kw={self.inverter_cost_per_kw}, "
            f"storage_lifetime={self.storage_lifetime}, "
            f"storage_cost_per_kwh={self.storage_cost_per_kwh}, "
            f"interest_rate={self.interest_rate}, "
            f"storage_charge_efficiency={self.storage_charge_efficiency}, "
            f"storage_discharge_efficiency={self.storage_discharge_efficiency}, "
            f"storage_charge_rate={self.storage_charge_rate}, "
            f"storage_discharge_rate={self.storage_discharge_rate}, "
            f"inverter_efficiency={self.inverter_efficiency}, "
            f"pv_system_kwp_per_m2={self.pv_system_kwp_per_m2}, "
            f"solver={self.solver}, "
            f"number_of_timesteps={self.number_of_timesteps}, "
            f"hours_per_timestep={self.hours_per_timestep})"
        )