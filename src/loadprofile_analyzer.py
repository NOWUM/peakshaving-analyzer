import logging

import fine as fn
import numpy as np
import pandas as pd

logger = logging.getLogger("model_builder")


######################
### DEFAULT VALUES ###
######################
# TODO Cite these accordingly (maybe in readme?)
PRODUCER_ENERGY_PRICE = 0.1665 # €/kWh
# value for 2024 taken from
# https://www.bdew.de/service/daten-und-grafiken/bdew-strompreisanalyse/
# https://de.statista.com/statistik/daten/studie/252029/umfrage/industriestrompreise-inkl-stromsteuer-in-deutschland/

GRID_CAPACITY_PRICE_OVER_2500H = 101.22
GRID_CAPACITY_PRICE_UNDER_2500H = 17.78
GRID_ENERGY_PRICE_OVER_2500H = 0.0127
GRID_ENERGY_PRICE_UNDER_2500H = 0.0460
# mean updated with historical inflation of cumulative 26,24% from
# https://zenodo.org/records/13734730

PV_SYSTEM_LIFETIME = 30
# taken from https://www.mdpi.com/1996-1073/14/14/4278

INVERTER_LIFETIME = 15
# taken from 10.4229/WCPEC-82022-3DV.1.46 Bucher Joss

STORAGE_LIFETIME = 15
# taken from "Energiespeicher - Bedarf, Technologien, Integration", Stadler Sterner 2017

STORAGE_COST_PER_KWH = 145
# taken from https://www.pem.rwth-aachen.de/cms/pem/der-lehrstuhl/presse-medien/aktuelle-meldungen/~bexlow/battery-monitor-2023-nachfrage-waechst/

STORAGE_CHARGE_EFFICIENCY = 0.9
STORAGE_DISCHARGE_EFFICIENCY = 0.9
# for round trip efficiency of 0.81
# taken from https://www.sciencedirect.com/science/article/pii/S2352152X23027846

STORAGE_CHARGE_RATE = 1
STORAGE_DISCHARGE_RATE = 1
# taken from https://www.sciencedirect.com/science/article/pii/S2590116819300116

INVERTER_EFFICIENCY = 0.95
# taken from https://www.sciencedirect.com/science/article/pii/S1364032116306712

INVERTER_COST_PER_KW = 180
# https://www.sciencedirect.com/science/article/pii/S1876610216310736

PV_SYSTEM_COST_PER_KWP = 1250
# taken from https://www.ise.fraunhofer.de/de/veroeffentlichungen/studien/studie-stromgestehungskosten-erneuerbare-energien.html

class LoadProfileAnalyzer:

    def __init__(
            self,
            consumption_timeseries: pd.Series | list | np.ndarray,
            hours_per_timestep: float = 0.25,
            interest_rate: float = 0.03,
            grid_capacity_price_over_2500h: float = 101.22,
            grid_capacity_price_under_2500h: float = 17.78,
            grid_energy_price_over_2500h: float = 0.0127,
            grid_energy_price_under_2500h: float = 0.0460,
            producer_energy_price: float = 0.1665,
            log_level = 2) -> None:

        self.consumption_timeseries = consumption_timeseries
        self.hours_per_timestep = hours_per_timestep

        self.interest_rate = interest_rate

        self.grid_capacity_price_over_2500h = grid_capacity_price_over_2500h
        self.grid_capacity_price_under_2500h = grid_capacity_price_under_2500h
        self.grid_energy_price_over_2500h = grid_energy_price_over_2500h
        self.grid_energy_price_under_2500h = grid_energy_price_under_2500h
        self.producer_energy_price = producer_energy_price

        self.log_level = log_level
        self.n_of_ts = len(consumption_timeseries)

        self.create_esm()
        self.calc_flh()
        self.set_capacity_energy_price()


    def calc_flh(self):

        self.flh = sum(self.consumption_timeseries) / max(self.consumption_timeseries)


    def set_capacity_energy_price(self):
        if self.flh > 2500:
            self.grid_capacity_price = self.grid_capacity_price_over_2500h
            self.grid_energy_price = self.grid_energy_price_over_2500h

        else:
            self.grid_capacity_price = self.grid_capacity_price_under_2500h
            self.grid_energy_price = self.grid_energy_price_under_2500h


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
        solar_data: pd.Series,
        pv_system_cost_per_kwp: float = 900,
        max_pv_system_size_kwp: float | None = None,
        pv_system_lifetime: int = 30,):

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
                capacityMax=max_pv_system_size_kwp,
                investPerCapacity=pv_system_cost_per_kwp,
                interestRate=self.interest_rate,
                economicLifetime=pv_system_lifetime,
                technicalLifetime=pv_system_lifetime))


    def add_storage(
            self,
            storage_cost_per_kwh: float = 145,
            storage_lifetime: int = 15,
            storage_charge_efficiency: float = 0.9,
            storage_discharge_efficiency: float = 0.9,
            storage_charge_rate: float = 1,
            storage_discharge_rate: float = 1,
            max_storage_size_kwh: float | None = None,
            inverter_cost_per_kw: float = 180,
            inverter_lifetime: int = 15,
            inverter_efficiency: float = 0.95):

        self.esm.add(
            fn.Conversion(
                esM=self.esm,
                name="to_storage",
                physicalUnit="kWh",
                commodityConversionFactors={'energy': -1, 'stored_energy': inverter_efficiency},
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
                cyclicLifetime=10000,
                chargeEfficiency=storage_charge_efficiency,
                dischargeEfficiency=storage_discharge_efficiency,
                capacityMax=max_storage_size_kwh,
                economicLifetime=storage_lifetime,
                technicalLifetime=storage_lifetime,
                chargeRate=storage_charge_rate,
                dischargeRate=storage_discharge_rate,
                doPreciseTsaModeling=False,
                investPerCapacity=storage_cost_per_kwh,
                opexPerCapacity=0.002,
                interestRate=self.interest_rate))

        self.esm.add(
            fn.Conversion(
                esM=self.esm,
                name="from_storage",
                physicalUnit="kWh",
                commodityConversionFactors={'stored_energy': -1, 'energy': 1},
                hasCapacityVariable=True,
                investPerCapacity=inverter_cost_per_kw,
                economicLifetime=inverter_lifetime,
                technicalLifetime=inverter_lifetime,
                linkedConversionCapacityID="storage",
                interestRate=self.interest_rate))


    def optimize(self, solver="appsi_highs"):

        self.esm.optimize(solver=solver)


    def build_and_optimize(
            self,
            add_storage: bool = False,
            storage_cost_per_kwh: float = 145,
            storage_lifetime: int = 15,
            storage_charge_efficiency: float = 0.9,
            storage_discharge_efficiency: float = 0.9,
            storage_charge_rate: float = 1,
            storage_discharge_rate: float = 1,
            max_storage_size_kwh: float | None = None,
            inverter_cost_per_kw: float = 180,
            inverter_lifetime: int = 15,
            inverter_efficiency: float = 0.95,
            add_solar: bool = False,
            solar_data: pd.Series | None = None,
            pv_system_cost_per_kwp: float = 900,
            max_pv_system_size_kwp: float | None = None,
            pv_system_lifetime: int = 30,
            solver: str = "appsi_highs"):

        # model building
        self.add_sink()
        self.add_source()
        self.add_transmission()
        if add_storage:
            self.add_storage(
                storage_cost_per_kwh=storage_cost_per_kwh,
                storage_lifetime=storage_lifetime,
                storage_charge_efficiency=storage_charge_efficiency,
                storage_discharge_efficiency=storage_discharge_efficiency,
                storage_charge_rate=storage_charge_rate,
                storage_discharge_rate=storage_discharge_rate,
                max_storage_size_kwh=max_storage_size_kwh,
                inverter_cost_per_kw=inverter_cost_per_kw,
                inverter_lifetime=inverter_lifetime,
                inverter_efficiency=inverter_efficiency)

        if add_solar:
            self.add_solar(
                solar_data=solar_data,
                pv_system_cost_per_kwp=pv_system_cost_per_kwp,
                max_pv_system_size_kwp=max_pv_system_size_kwp,
                pv_system_lifetime=pv_system_lifetime)

        # optimize
        self.optimize(solver=solver)
