import logging

import fine as fn
import numpy as np
import pandas as pd

logger = logging.getLogger("model_builder")


######################
### DEFAULT VALUES ###
######################

# TODO Cite these accordingly (maybe in readme?)

ENERGY_PRICE = 0.1665 # €/kWh
# value for 2024 taken from
# https://www.bdew.de/service/daten-und-grafiken/bdew-strompreisanalyse/
# https://de.statista.com/statistik/daten/studie/252029/umfrage/industriestrompreise-inkl-stromsteuer-in-deutschland/

PV_MODULE_LIFETIME = 30
# taken from https://www.mdpi.com/1996-1073/14/14/4278

INVERTER_LIFETIME = 15
# taken from 10.4229/WCPEC-82022-3DV.1.46 Bucher Joss

STORAGE_LIFETIME = 15
# taken from "Energiespeicher - Bedarf, Technologien, Integration", Stadler Sterner 2017

# TODO research these missing values accordingly
GRID_CAPACITY_PRICE = "XXX"
GRID_ENERGY_PRICE = "XXX"
STORAGE_COST_PER_KWH = "XXX"
PV_MODULE_COST_PER_KWH = "XXX"
INVERTER_COST_PER_KW = "XXX"
STORAGE_CHARGE_EFFICIENCY = "XXX"
STORAGE_DISCHARGE_EFFICIENCY = "XXX"
STORAGE_CHARGE_RATE = "XXX"
STORAGE_DISCHARGE_RATE = "XXX"


class LoadProfileAnalyzer:

    def __init__(
            self,
            consumption_timeseries: pd.Series | np.array | list[float],
            hours_per_timestep: float = 0.25,
            interest_rate: float = 0.03,
            grid_capacity_price: float = GRID_CAPACITY_PRICE,
            grid_energy_price: float = GRID_ENERGY_PRICE,
            producer_energy_price: float = ENERGY_PRICE,
            storage_cost_per_kwh: float = STORAGE_COST_PER_KWH,
            storage_lifetime: int = STORAGE_LIFETIME,
            storage_charge_efficiency: float = STORAGE_CHARGE_EFFICIENCY,
            storage_discharge_efficiency: float = STORAGE_DISCHARGE_EFFICIENCY,
            storage_charge_rate: float = STORAGE_CHARGE_RATE,
            storage_discharge_rate: float = STORAGE_DISCHARGE_RATE,
            max_storage_size_kwh: float | None = None,
            pv_module_cost_per_kwp: float = PV_MODULE_COST_PER_KWH,
            max_pv_system_size_kwp: float | None = None,
            pv_module_lifetime: int = PV_MODULE_LIFETIME,
            inverter_cost_per_kw: float = INVERTER_COST_PER_KW,
            inverter_lifetime: int = INVERTER_LIFETIME,
            log_level = 2) -> None:

        self.consumption_timeseries = consumption_timeseries
        self.hours_per_timestep = hours_per_timestep
        self.interest_rate = interest_rate
        self.grid_capacity_price = grid_capacity_price
        self.grid_energy_price = grid_energy_price
        self.producer_energy_price = producer_energy_price
        self.storage_cost_per_kwh = storage_cost_per_kwh
        self.max_storage_size_kwh = max_storage_size_kwh
        self.pv_module_cost_per_kwp = pv_module_cost_per_kwp
        self.max_pv_system_size_kwp = max_pv_system_size_kwp
        self.inverter_cost_per_kw = inverter_cost_per_kw
        self.pv_module_lifetime = pv_module_lifetime
        self.inverter_lifetime = inverter_lifetime
        self.storage_lifetime = storage_lifetime
        self.storage_charge_efficiency = storage_charge_efficiency
        self.storage_discharge_eifficiency = storage_discharge_efficiency
        self.storage_charge_rate = storage_charge_rate
        self.storage_discharge_rate = storage_discharge_rate
        self.log_level = log_level

        self.n_of_ts = len(consumption_timeseries)

        self.create_esm()


    def create_esm(self):

        self.esm = fn.EnergySystemModel(
            locations={"source", "load"},
            commodities={"energy", "stored_energy"},
            commodityUnitsDict={"energy": "kWh", "stored_energy": "kWh"},
            costUnit='Euro',
            numberOfTimeSteps=self.n_of_ts,
            hoursPerTimeStep=self.hours_per_timestep,
            verboseLogLevel=self.log_level)


    def add_sink(self):

        load_df = pd.DataFrame(
            columns=["source", "load"],
            index=np.arange(0, self.n_of_ts, 1))

        load_df["source"] = 0
        load_df["load"] = self.consumption_timeseries

        self.esm.add(
            fn.Sink(
                esM=self.esm,
                commodity="energy",
                name="load",
                hasCapacityVariable=False,
                operationRateFix=load_df))


    def add_source(self):

        source_df = pd.DataFrame(
            columns=["source", "load"],
            index=np.arange(0, self.n_of_ts, 1))

        source_df["source"] = 1e18
        source_df["load"] = 0

        self.esm.add(
            fn.Source(
                esM=self.esm,
                commodity="energy",
                name="source",
                hasCapacityVariable=False,
                operationRateMax=source_df,
                opexPerOperation=self.producer_energy_price))


    def add_transmission(self):

        self.esm.add(
            fn.Transmission(
                esM=self.esm,
                name="capacity_price",
                commodity="energy",
                hasCapacityVariable=True,
                investPerCapacity=self.grid_capacity_price,
                interestRate=self.interest_rate,
                economicLifetime=1,
                technicalLifetime=1))


    # TODO: remove solar data as required parameter
    # IMO this should be done per request or with csv or similar
    def add_solar(
        self,
        solar_data: pd.Series):

        solar_df = pd.DataFrame(
            columns=["source", "load"],
            index=np.arange(0, self.n_of_ts, 1))

        solar_df["source"] = 0
        solar_df["load"] = solar_data

        self.esm.add(
            fn.Source(
                esM=self.esm,
                name="PV",
                commodity="energy",
                hasCapacityVariable=True,
                operationRateMax=solar_df,
                capacityMax=self.max_pv_system_size_kwp,
                investPerCapacity=self.pv_module_cost_per_kwp,
                interestRate=self.interest_rate,
                economicLifetime=PV_MODULE_LIFETIME,
                technicalLifetime=PV_MODULE_LIFETIME))


    def add_storage(self):


        self.esm.add(
            fn.Conversion(
                esM=self.esm,
                name="to_storage",
                physicalUnit="kWh",
                commodityConversionFactors={'energy': -1, 'stored_energy': 1},
                hasCapacityVariable=True,
                investPerCapacity=0,
                linkedConversionCapacityID="storage",
                interestRate=self.interest_rate))

        self.esm.add(
            fn.Storage(
                esM=self.esm,
                name="storage",
                commodity="stored_energy",
                hasCapacityVariable=True,
                chargeEfficiency=self.storage_charge_efficiency,
                cyclicLifetime=10000,
                dischargeEfficiency=self.storage_charge_efficiency,
                capacityMax=self.max_storage_size_kwh,
                economicLifetime=self.storage_lifetime,
                technicalLifetime=self.storage_lifetime,
                chargeRate=self.storage_charge_rate,
                dischargeRate=self.storage_discharge_rate,
                doPreciseTsaModeling=False,
                investPerCapacity=self.storage_cost_per_kwh,
                opexPerCapacity=0.002,
                interestRate=self.interest_rate))

        self.esm.add(
            fn.Conversion(
                esM=self.esm,
                name="from_storage",
                physicalUnit="kWh",
                commodityConversionFactors={'stored_energy': -1, 'energy': 1},
                hasCapacityVariable=True,
                investPerCapacity=self.inverter_cost_per_kw,
                economicLifetime=self.inverter_lifetime,
                technicalLifetime=self.inverter_lifetime,
                linkedConversionCapacityID="storage",
                interestRate=self.interest_rate))


    def optimize(self, solver="appsi_highs"):

        self.esm.optimize(solver=solver)


    def build_and_optimize(
            self,
            add_storage: bool = False,
            add_solar: bool = False,
            solver: str = "appsi_highs"):

        # model building
        self.add_sink()
        self.add_source()
        self.add_transmission()
        if add_storage:
            self.add_storage()
        if add_solar:
            self.add_solar()

        # optimize
        self.optimize(solver=solver)
