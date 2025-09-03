import logging

import fine as fn
import numpy as np
import pandas as pd

from peakshaving_analyzer.input import Config
from peakshaving_analyzer.output import Results, create_results

logger = logging.getLogger("peakshaving_analyzer")


class PeakShavingAnalyzer:
    def __init__(
        self,
        config: Config,
    ) -> None:
        self.config = config

        self.consumption_timeseries = config.consumption_timeseries
        self.price_timeseries = config.price_timeseries
        self.hours_per_timestep = config.hours_per_timestep
        self.number_of_timesteps = len(self.consumption_timeseries)
        self.add_stor = config.add_storage
        self.add_sol = config.add_solar
        self.auto_opt = config.auto_opt
        self.verbose = config.verbose
        self.db_uri = config.db_uri

        self.interest_rate = config.interest_rate

        self.grid_capacity_price = config.grid_capacity_price
        self.grid_energy_price = config.grid_energy_price
        self.producer_energy_price = config.producer_energy_price

        self.storage_cost_per_kwh = config.storage_cost_per_kwh
        self.storage_lifetime = config.storage_lifetime
        self.storage_charge_efficiency = config.storage_charge_efficiency
        self.storage_discharge_efficiency = config.storage_discharge_efficiency
        self.storage_charge_rate = config.storage_charge_rate
        self.storage_discharge_rate = config.storage_discharge_rate
        self.max_storage_size_kwh = config.max_storage_size_kwh
        self.inverter_cost_per_kw = config.inverter_cost_per_kw
        self.inverter_lifetime = config.inverter_lifetime
        self.inverter_efficiency = config.inverter_efficiency

        self.max_pv_system_size_kwp = config.max_pv_system_size_kwp
        self.pv_system_cost_per_kwp = config.pv_system_cost_per_kwp
        self.pv_system_lifetime = config.pv_system_lifetime
        self.pv_system_lifetime = config.pv_system_lifetime

        if self.add_sol:
            self.solar_generation_timeseries = config.solar_generation_timeseries

        self.solver = config.solver

        if self.verbose:
            logger.setLevel(logging.INFO)

        self._create_esm()
        self._add_source()
        self._add_transmission()
        self._add_sink()
        logger.info("Built default ESM.")

        if self.add_stor:
            self.add_storage()
            logger.info("Added storage.")

        if self.add_sol:
            self.add_solar()
            logger.info("Added solar.")

        if self.auto_opt:
            self.optimize(solver=self.solver)
            logger.info("Optimized.")

            self.save_results(config)
            logger.info("Saved results.")

    def _create_esm(self):
        self.esm = fn.EnergySystemModel(
            locations={"grid", "consumption_site"},
            commodities={"energy", "stored_energy"},
            commodityUnitsDict={"energy": "kWh", "stored_energy": "kWh"},
            costUnit="Euro",
            numberOfTimeSteps=self.number_of_timesteps,
            hoursPerTimeStep=self.hours_per_timestep,
            verboseLogLevel=2,
        )

    def _add_sink(self):
        load_df = pd.DataFrame(
            columns=["grid", "consumption_site"],
            index=np.arange(0, self.number_of_timesteps, 1),
        )

        load_df["grid"] = 0
        load_df["consumption_site"] = self.consumption_timeseries * self.hours_per_timestep

        self.esm.add(
            fn.Sink(
                esM=self.esm,
                commodity="energy",
                name="consumption_site",
                hasCapacityVariable=False,
                operationRateFix=load_df,
            )
        )

    def _add_source(self):
        source_df = pd.DataFrame(
            columns=["grid", "consumption_site"],
            index=np.arange(0, self.number_of_timesteps, 1),
        )

        source_df["grid"] = 1e18
        source_df["consumption_site"] = 0

        self.esm.add(
            fn.Source(
                esM=self.esm,
                commodity="energy",
                name="grid",
                hasCapacityVariable=False,
                operationRateMax=source_df,
                commodityCostTimeSeries=self.price_timeseries,
            )
        )

    def _add_transmission(self):
        self.esm.add(
            fn.Transmission(
                esM=self.esm,
                name="capacity_price",
                commodity="energy",
                hasCapacityVariable=True,
                investPerCapacity=self.grid_capacity_price,
                interestRate=self.interest_rate,
                economicLifetime=1,
                technicalLifetime=1,
            )
        )

    def add_solar(self):
        self.esm.add(
            fn.Source(
                esM=self.esm,
                name="PV",
                commodity="energy",
                hasCapacityVariable=True,
                operationRateMax=self.solar_generation_timeseries,
                capacityMax=self.max_pv_system_size_kwp,
                investPerCapacity=self.pv_system_cost_per_kwp,
                interestRate=self.interest_rate,
                economicLifetime=self.pv_system_lifetime,
                technicalLifetime=self.pv_system_lifetime,
            )
        )

    def add_storage(self):
        self.esm.add(
            fn.Conversion(
                esM=self.esm,
                name="to_storage",
                physicalUnit="kWh",
                commodityConversionFactors={
                    "energy": -1,
                    "stored_energy": self.inverter_efficiency,
                },
                hasCapacityVariable=True,
                investPerCapacity=0,
                linkedConversionCapacityID="storage",
                interestRate=self.interest_rate,
            )
        )

        self.esm.add(
            fn.Storage(
                esM=self.esm,
                name="storage",
                commodity="stored_energy",
                locationalEligibility=pd.Series([1, 0], index=["consumption_site", "grid"]),
                hasCapacityVariable=True,
                cyclicLifetime=10000,
                chargeEfficiency=self.storage_charge_efficiency,
                dischargeEfficiency=self.storage_discharge_efficiency,
                capacityMax=self.max_storage_size_kwh,
                economicLifetime=self.storage_lifetime,
                technicalLifetime=self.storage_lifetime,
                chargeRate=self.storage_charge_rate,
                dischargeRate=self.storage_discharge_rate,
                doPreciseTsaModeling=False,
                investPerCapacity=self.storage_cost_per_kwh,
                interestRate=self.interest_rate,
            )
        )

        self.esm.add(
            fn.Conversion(
                esM=self.esm,
                name="from_storage",
                physicalUnit="kWh",
                commodityConversionFactors={"stored_energy": -1, "energy": 1},
                hasCapacityVariable=True,
                investPerCapacity=self.inverter_cost_per_kw,
                economicLifetime=self.inverter_lifetime,
                technicalLifetime=self.inverter_lifetime,
                linkedConversionCapacityID="storage",
                interestRate=self.interest_rate,
            )
        )

    def optimize(self, solver: str | None = None) -> Results:
        logger.info("Creating pyomo model.")
        self.esm.declareOptimizationProblem()

        # add constraint setting storage level on start
        # of optimization to zero
        if self.add_stor:
            self.esm.pyM.stateOfCharge_stor["consumption_site", "storage", 0, 0, 0].setub(0)

        # set solver if not provided
        if not solver:
            solver = self.config.solver

        logger.info("Optimizing. Depending on the given parameters and your setup, this may take a while.")

        self.esm.optimize(solver=solver, declaresOptimizationProblem=False)

        results = create_results(self.config, self.esm)

        return results

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
    ) -> Results:
        # model building
        self._add_sink()
        self._add_source()
        self._add_transmission()

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
                inverter_efficiency=inverter_efficiency,
            )

        if add_solar:
            self.add_solar(
                solar_data=solar_data,
                pv_system_cost_per_kwp=pv_system_cost_per_kwp,
                max_pv_system_size_kwp=max_pv_system_size_kwp,
                pv_system_lifetime=pv_system_lifetime,
            )

        # optimize and return results
        return self.optimize()
