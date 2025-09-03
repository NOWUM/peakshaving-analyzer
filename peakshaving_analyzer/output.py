import logging
from dataclasses import dataclass
from pathlib import Path

import fine as fn
import pandas as pd
import sqlalchemy

from peakshaving_analyzer import Config
from peakshaving_analyzer.common import IOHandler

log = logging.getLogger(__name__)


@dataclass
class Results(IOHandler):
    # general parameters
    name: str

    # output timeseries
    grid_usage_kw: pd.Series | None = None
    storage_charge_kw: pd.Series | None = None
    storage_discharge_kw: pd.Series | None = None
    storage_soc_kwh: pd.Series | None = None
    solar_generation_kw: pd.Series | None = None
    consumption_kw: pd.Series | None = None
    energy_price_eur: pd.Series | None = None

    # energy costs itself
    energy_costs_eur: float | None = None

    # grid energy and capacity costs
    grid_energy_costs_eur: float | None = None
    grid_capacity_costs_eur: float | None = None
    grid_capacity_kw: float | None = None

    # storage system costs
    storage_invest_eur: float | None = None
    storage_annuity_eur: float | None = None
    storage_capacity_kwh: float | None = None
    inverter_invest_eur: float | None = None
    inverter_annuity_eur: float | None = None
    inverter_capacity_kw: float | None = None

    # solar system costs
    solar_invest_eur: float | None = None
    solar_annuity_eur: float | None = None
    solar_capacity_kwp: float | None = None

    # total costs
    total_yearly_costs_eur: float | None = None
    total_annuity_eur: float | None = None
    total_invest_eur: float | None = None

    def timeseries_to_df(self):
        df = pd.DataFrame()

        df["grid_usage_kw"] = self.grid_usage_kw
        df["storage_charge_kw"] = self.storage_charge_kw
        df["storage_discharge_kw"] = self.storage_discharge_kw
        df["storage_soc_kwh"] = self.storage_soc_kwh
        df["solar_generation_kw"] = self.solar_generation_kw
        df["consumption_kw"] = self.consumption_kw
        df["energy_price_eur"] = self.energy_price_eur

        return df

    def timeseries_to_csv(self, path: str | Path):
        df = self.timeseries_to_df()
        df.to_csv(path)

    def timeseries_to_json(self, path: str | Path):
        df = self.timeseries_to_df()
        df.to_json(path)

    def to_sql(
        self,
        connection: str | sqlalchemy.engine.Connection,
        include_timeseries: bool = True,
        overview_table_name: str = "overview",
        timeseries_table_name: str = "timeseries",
        schema: str = "public",
    ) -> None:
        df = pd.DataFrame([self.to_dict(include_timeseries=False)])
        df.to_sql(name=overview_table_name, schema=schema, con=connection, if_exists="append", index=False)

        if include_timeseries:
            df = self.timeseries_to_df()
            df["name"] = self.name
            df.to_sql(name=timeseries_table_name, schema=schema, con=connection, if_exists="append", index=False)

    def plot_storage_timeseries(self):
        storage_columns = ["storage_charge_kw", "storage_discharge_kw", "storage_soc_kwh"]
        self._plot(cols_to_plot=storage_columns)

    def plot_consumption_timeseries(self):
        consumption_columns = ["grid_usage_kw", "storage_discharge_kw", "solar_generation_kw", "consumption_kw"]
        self._plot(cols_to_plot=consumption_columns)


def create_results(config: Config, esm: fn.EnergySystemModel) -> Results:
    data = {}
    data["name"] = config.name

    _retrieve_timeseries(data, esm=esm, config=config)
    log.info("Retrieved timeseries")

    _retrieve_system_sizes(data, esm=esm)
    log.info("Retrieved system sizes")

    _retrieve_system_costs(data, esm=esm)
    log.info("Retrieved system costs")

    return Results(**data)


def _get_val_from_summary(esm: fn.EnergySystemModel, model_name: str, index: tuple[str], location) -> float:
    try:
        return esm.getOptimizationSummary(model_name).loc[index, location]
    except KeyError:
        log.warning(f"KeyError: {index} not found in {model_name} model.")
        return 0.0


def _get_optimum_ts(esm: fn.EnergySystemModel, model_name: str, variable: str, index: tuple[str]) -> pd.Series:
    """Retrieves optimum timeseries from ESM.

    Args:
        model_name (str): Component model name.
        variable (str): The variable to get.
        index (tuple[str]): Index to use.

    Returns:
        pd.Series: Optimum timeseries
    """

    try:
        mdl = esm.componentModelingDict[model_name]
        vals_df = mdl.getOptimalValues(variable)["values"]

        s = vals_df.loc[index]
    except Exception as e:
        print(model_name, variable, index)
        raise e

    return s


def _retrieve_timeseries(data: dict[str], esm: fn.EnergySystemModel, config: Config) -> None:
    """Writes optimum timeseries to database."""

    data["grid_usage_kw"] = (
        _get_optimum_ts(
            esm=esm,
            model_name="SourceSinkModel",
            variable="operationVariablesOptimum",
            index=("grid", "grid"),
        )
        / config.hours_per_timestep
    )

    if config.add_storage:
        data["storage_charge_kw"] = (
            _get_optimum_ts(
                esm=esm,
                model_name="StorageModel",
                variable="chargeOperationVariablesOptimum",
                index=("storage", "consumption_site"),
            )
            / config.hours_per_timestep
        )

        data["storage_discharge_kw"] = (
            _get_optimum_ts(
                esm=esm,
                model_name="StorageModel",
                variable="dischargeOperationVariablesOptimum",
                index=("storage", "consumption_site"),
            )
            / config.hours_per_timestep
        )

        data["storage_soc_kwh"] = (
            _get_optimum_ts(
                esm=esm,
                model_name="StorageModel",
                variable="stateOfChargeOperationVariablesOptimum",
                index=("storage", "consumption_site"),
            )
            / config.hours_per_timestep
        )

    else:
        data["storage_charge_kw"] = pd.Series(0, index=list(range(config.n_timesteps)))
        data["storage_discharge_kw"] = pd.Series(0, index=list(range(config.n_timesteps)))
        data["storage_soc_kwh"] = pd.Series(0, index=list(range(config.n_timesteps)))

    if config.add_solar:
        data["solar_generation_kw"] = (
            _get_optimum_ts(
                esm=esm,
                model_name="SourceSinkModel",
                variable="operationVariablesOptimum",
                index=("PV", "consumption_site"),
            )
            / config.hours_per_timestep
        )

    else:
        data["solar_generation_kw"] = pd.Series(0, index=list(range(config.n_timesteps)))

    data["consumption_kw"] = config.consumption_timeseries
    data["energy_price_eur"] = config.price_timeseries["grid"]


def _retrieve_system_sizes(data: dict, esm: fn.EnergySystemModel) -> None:
    data["grid_capacity_kw"] = _get_val_from_summary(
        esm=esm,
        model_name="TransmissionModel",
        index=("capacity_price", "capacity", "[kWh]", "grid"),
        location="consumption_site",
    )

    data["storage_capacity_kwh"] = _get_val_from_summary(
        esm=esm,
        model_name="StorageModel",
        index=("storage", "capacity", "[kWh*h]"),
        location="consumption_site",
    )

    data["inverter_capacity_kw"] = _get_val_from_summary(
        esm=esm,
        model_name="ConversionModel",
        index=("from_storage", "capacity", "[kWh]"),
        location="consumption_site",
    )

    data["solar_capacity_kwp"] = _get_val_from_summary(
        esm=esm,
        model_name="SourceSinkModel",
        index=("PV", "capacity", "[kWh]"),
        location="consumption_site",
    )


def _retrieve_system_costs(data: dict[str], esm: fn.EnergySystemModel) -> None:
    # energy itself
    data["energy_costs_eur"] = _get_val_from_summary(
        esm=esm,
        model_name="SourceSinkModel",
        index=("grid", "TAC", "[Euro/a]"),
        location="grid",
    )

    # grid data
    data["grid_energy_costs_eur"] = _get_val_from_summary(
        esm=esm,
        model_name="TransmissionModel",
        index=("capacity_price", "operation", "[kWh*h]", "grid"),
        location="consumption_site",
    )
    data["grid_capacity_costs_eur"] = (
        _get_val_from_summary(
            esm=esm,
            model_name="TransmissionModel",
            index=("capacity_price", "invest", "[Euro]", "grid"),
            location="consumption_site",
        )
        * 2
    )

    # storage data
    data["storage_invest_eur"] = _get_val_from_summary(
        esm=esm,
        model_name="StorageModel",
        index=("storage", "invest", "[Euro]"),
        location="consumption_site",
    )
    data["storage_annuity_eur"] = _get_val_from_summary(
        esm=esm,
        model_name="StorageModel",
        index=("storage", "TAC", "[Euro/a]"),
        location="consumption_site",
    )

    # inverter data
    data["inverter_invest_eur"] = _get_val_from_summary(
        esm=esm,
        model_name="ConversionModel",
        index=("from_storage", "invest", "[Euro]"),
        location="consumption_site",
    )
    data["inverter_annuity_eur"] = _get_val_from_summary(
        esm=esm,
        model_name="ConversionModel",
        index=("from_storage", "TAC", "[Euro/a]"),
        location="consumption_site",
    )

    # solar data
    data["solar_invest_eur"] = _get_val_from_summary(
        esm=esm,
        model_name="SourceSinkModel",
        index=("PV", "invest", "[Euro]"),
        location="consumption_site",
    )
    data["solar_annuity_eur"] = _get_val_from_summary(
        esm=esm,
        model_name="SourceSinkModel",
        index=("PV", "TAC", "[Euro/a]"),
        location="consumption_site",
    )

    # calculate total costs
    data["total_yearly_costs_eur"] = (
        data["energy_costs_eur"]
        + data["grid_energy_costs_eur"]
        + data["grid_capacity_costs_eur"]
        + data["storage_annuity_eur"]
        + data["inverter_annuity_eur"]
        + data["solar_annuity_eur"]
    )
    data["total_annuity_eur"] = data["storage_annuity_eur"] + data["inverter_annuity_eur"] + data["solar_annuity_eur"]
    data["total_invest_eur"] = data["storage_invest_eur"] + data["inverter_invest_eur"] + data["solar_invest_eur"]
