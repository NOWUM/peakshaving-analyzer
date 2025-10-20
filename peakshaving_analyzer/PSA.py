import logging

import fine as fn
import numpy as np
import pandas as pd

from peakshaving_analyzer.input import Config
from peakshaving_analyzer.output import Results, create_results

log = logging.getLogger(__name__)


class PeakShavingAnalyzer:
    def __init__(
        self,
        config: Config,
    ) -> None:
        self.config = config

        self.consumption_timeseries = config.consumption_timeseries
        self.price_timeseries = config.price_timeseries
        self.verbose = config.verbose

        if self.config.allow_additional_pv:
            self.new_pv_generation_timeseries = config.new_pv_generation_timeseries

        if config.verbose:
            log.setLevel(level=logging.INFO)
        else:
            log.setLevel(level=logging.WARNING)

        self._create_esm()
        self._add_source()
        self._add_transmission()
        self._add_sink()
        log.info("Built default ESM.")

        if self.config.pv_system_already_exists:
            self._add_existing_pv()
            log.info("Added existing PV system.")

        if self.config.add_storage:
            self.add_storage()
            log.info("Added storage.")

        if self.config.allow_additional_pv:
            self.add_additional_pv()
            log.info("Added pv.")

    def _create_esm(self):
        self.esm = fn.EnergySystemModel(
            locations={"grid", "consumption_site"},
            commodities={"energy", "stored_energy"},
            commodityUnitsDict={"energy": "kWh", "stored_energy": "kWh"},
            costUnit="Euro",
            numberOfTimeSteps=self.config.n_timesteps,
            hoursPerTimeStep=self.config.hours_per_timestep,
            verboseLogLevel=2,
        )

    def _add_sink(self):
        load_df = pd.DataFrame(
            columns=["grid", "consumption_site"],
            index=np.arange(0, self.config.n_timesteps, 1),
        )

        load_df["grid"] = 0
        load_df["consumption_site"] = self.consumption_timeseries * self.config.hours_per_timestep

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
            index=np.arange(0, self.config.n_timesteps, 1),
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
                commodityCostTimeSeries=self.config.price_timeseries,
            )
        )

    def _add_transmission(self):
        self.esm.add(
            fn.Transmission(
                esM=self.esm,
                name="capacity_price",
                commodity="energy",
                hasCapacityVariable=True,
                investPerCapacity=self.config.grid_capacity_price,
                opexPerOperation=self.config.grid_energy_price,
                interestRate=self.config.interest_rate,
                economicLifetime=1,
                technicalLifetime=1,
            )
        )

    def _add_existing_pv(self):
        self.esm.add(
            fn.Source(
                esM=self.esm,
                name="Existing PV",
                commodity="energy",
                hasCapacityVariable=True,
                operationRateMax=self.config.existing_pv_generation_timeseries,
                capacityMax=self.config.existing_pv_size_kwp,
            )
        )

    def add_additional_pv(self):
        self.esm.add(
            fn.Source(
                esM=self.esm,
                name="New PV",
                commodity="energy",
                hasCapacityVariable=True,
                operationRateMax=self.config.new_pv_generation_timeseries,
                capacityMax=self.config.max_pv_system_size_kwp,
                investPerCapacity=self.config.pv_system_cost_per_kwp,
                interestRate=self.config.interest_rate / 100,
                economicLifetime=self.config.pv_system_lifetime,
                technicalLifetime=self.config.pv_system_lifetime,
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
                    "stored_energy": self.config.inverter_efficiency,
                },
                hasCapacityVariable=True,
                investPerCapacity=0,
                linkedConversionCapacityID="storage",
                interestRate=self.config.interest_rate / 100,
            )
        )

        if self.config.max_storage_size_kwh:
            max_cap = pd.Series([self.config.max_storage_size_kwh, 0], index=["consumption_site", "grid"])
        else:
            max_cap = None
        self.esm.add(
            fn.Storage(
                esM=self.esm,
                name="storage",
                commodity="stored_energy",
                locationalEligibility=pd.Series([1, 0], index=["consumption_site", "grid"]),
                hasCapacityVariable=True,
                cyclicLifetime=self.config.storage_cyclic_lifetime,
                chargeEfficiency=self.config.storage_charge_efficiency,
                dischargeEfficiency=self.config.storage_discharge_efficiency,
                capacityMax=max_cap,
                economicLifetime=self.config.storage_lifetime,
                technicalLifetime=self.config.storage_lifetime,
                chargeRate=self.config.storage_charge_rate,
                dischargeRate=self.config.storage_discharge_rate,
                doPreciseTsaModeling=False,
                investPerCapacity=self.config.storage_cost_per_kwh,
                interestRate=self.config.interest_rate / 100,
            )
        )

        self.esm.add(
            fn.Conversion(
                esM=self.esm,
                name="from_storage",
                physicalUnit="kWh",
                commodityConversionFactors={"stored_energy": -1, "energy": 1},
                hasCapacityVariable=True,
                investPerCapacity=self.config.inverter_cost_per_kw,
                economicLifetime=self.config.inverter_lifetime,
                technicalLifetime=self.config.inverter_lifetime,
                linkedConversionCapacityID="storage",
                interestRate=self.config.interest_rate / 100,
            )
        )

    def optimize(self, solver: str | None = None) -> Results:
        log.info("Creating pyomo model.")
        self.esm.declareOptimizationProblem()

        # add constraint setting storage level on start
        # of optimization to zero
        if self.config.add_storage:
            self.esm.pyM.stateOfCharge_stor["consumption_site", "storage", 0, 0, 0].setub(0)

        # set solver if not provided
        if not solver:
            solver = self.config.solver

        log.info("Optimizing. Depending on the given parameters and your setup, this may take a while.")

        self.esm.optimize(solver=solver, declaresOptimizationProblem=False)

        results = create_results(self.config, self.esm)

        return results
