import logging
from copy import deepcopy

import fine as fn
import pandas as pd
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from peakshaving_analyzer import Config

log = logging.getLogger("DatabaseHandler")


TABLES = [
    "input.parameters",
    "input.timeseries",
    "output.tech",
    "output.eco",
    "output.timeseries",
]


class DatabaseHandler:
    def __init__(self, config: Config, esm: fn.EnergySystemModel) -> None:
        self.config = config
        self.esm = esm
        self.engine = sqlalchemy.create_engine(config.db_uri)

        if self.config.verbose:
            log.setLevel(logging.INFO)

        self.name = deepcopy(config.name)
        self.overwrite_existing = deepcopy(config.overwrite_existing_optimization)

        self._test_connection()

        if self.overwrite_existing:
            self._remove_old_optimization()

    def _test_connection(self):
        """Tries to connect to provided database URI in 5 attempts."""
        attempt = 0
        try:
            self.engine.connect()
        except sqlalchemy.exc.OperationalError as e:
            if attempt < 5:
                attempt += 1

            log.error(f"Could not connect to database in 5 tries: {e}")

            raise e

    def _remove_old_optimization(self):
        """Removes old optimization data from the database."""
        log.info("Removing old optimization data from database.")
        try:
            with self.engine.connect() as conn:
                for table in TABLES:
                    sql = text(f"DELETE FROM {table} WHERE name = '{self.name}'")
                    conn.execute(sql)
                conn.commit()
            log.info("Old optimization data removed from database.")
        except Exception as e:
            log.error(f"Error removing old optimization data from database: {e}")

    def _df_to_sql(
        self,
        df: pd.DataFrame,
        table_name: str,
        schema: str,
    ) -> None:
        """Writes a DataFrame to the database.

        Args:
            df (pd.DataFrame): DataFrame to write.
            table_name (str): Name of the table to write to.
        """
        log.info(f"Writing DataFrame to {table_name} table in database.")
        try:
            df.to_sql(
                name=table_name,
                schema=schema,
                con=self.engine,
                if_exists="append",
                index=False,
            )
            log.info(f"DataFrame written to {schema}.{table_name} table in database.")
        except IntegrityError as ie:
            log.error(f"Integrityerror writing DataFrame to {schema}.{table_name} table in database: {ie}")
            raise ie
        except Exception as e:
            log.error(f"Error writing DataFrame to {schema}.{table_name} table in database: {e}")
            raise e

    def save_all(self) -> None:
        """Saves all data to the database."""
        log.info("Saving all data to database.")
        self.save_config()
        self.save_input_timeseries()
        self.save_opti_data()
        self.save_output_timeseries()

        log.info("All data saved to database.")

    def save_config(self) -> None:
        """Writes the configuration to the database."""

        # remove unnecessary keys from config
        keys_to_exclude = [
            "timestamps",
            "consumption_timeseries",
            "price_timeseries",
            "solar_timeseries",
            "db_uri",
            "overwrite_price_timeseries",
            "overwrite_existing_optimization",
            "auto_opt",
            "verbose",
        ]
        conf_to_save = {key: value for key, value in vars(self.config).items() if key not in keys_to_exclude}

        # create dataFrame from config
        config_df = pd.DataFrame(conf_to_save, index=[0])

        # write to sql
        self._df_to_sql(config_df, "parameters", "input")

    def save_input_timeseries(self) -> None:
        """Writes the consumption data to the database."""
        log.info("Saving consumption data to database.")

        # create DataFrame from config
        df = pd.DataFrame()
        df["timestamp"] = self.config.timestamps
        df["name"] = self.name
        df["consumption_kw"] = self.config.consumption_timeseries
        df["price_eur"] = self.config.price_timeseries["grid"]

        if self.config.add_solar:
            df["solar_generation"] = self.config.solar_timeseries["consumption_site"]
        else:
            df["solar_generation"] = 0

        # write to sql
        self._df_to_sql(df, "timeseries", "input")

    def _get_val_from_sum(self, model_name: str, index: tuple[str], location) -> float:
        try:
            return self.esm.getOptimizationSummary(model_name).loc[index, location]
        except KeyError:
            log.warning(f"KeyError: {index} not found in {model_name} model.")
            return 0.0

    def _get_optimum_ts(self, model_name: str, variable: str, index: tuple[str]) -> pd.Series:
        """Retrieves optimum timeseries from ESM.

        Args:
            model_name (str): Component model name.
            variable (str): The variable to get.
            index (tuple[str]): Index to use.

        Returns:
            pd.Series: Optimum timeseries
        """

        try:
            mdl = self.esm.componentModelingDict[model_name]
            vals_df = mdl.getOptimalValues(variable)["values"]

            s = vals_df.loc[index]
        except Exception as e:
            print(model_name, variable, index)
            raise e

        return s

    def save_output_timeseries(self):
        """Writes optimum timeseries to database."""

        df = pd.DataFrame()
        df["timestamp"] = self.config.timestamps
        df["name"] = self.config.name

        df["grid_usage_kw"] = (
            self._get_optimum_ts(
                model_name="SourceSinkModel",
                variable="operationVariablesOptimum",
                index=("grid", "grid"),
            )
            / self.config.hours_per_timestep
        )

        if self.config.add_storage:
            df["storage_charge_kw"] = (
                self._get_optimum_ts(
                    model_name="StorageModel",
                    variable="chargeOperationVariablesOptimum",
                    index=("storage", "consumption_site"),
                )
                / self.config.hours_per_timestep
            )
            df["storage_discharge_kw"] = (
                self._get_optimum_ts(
                    model_name="StorageModel",
                    variable="dischargeOperationVariablesOptimum",
                    index=("storage", "consumption_site"),
                )
                / self.config.hours_per_timestep
            )
            df["storage_soc_kwh"] = (
                self._get_optimum_ts(
                    model_name="StorageModel",
                    variable="stateOfChargeOperationVariablesOptimum",
                    index=("storage", "consumption_site"),
                )
                / self.config.hours_per_timestep
            )
        else:
            df["storage_charge_kw"] = 0
            df["storage_discharge_kw"] = 0
            df["storage_soc_kwh"] = 0

        if self.config.add_solar:
            df["solar_generation_kw"] = (
                self._get_optimum_ts(
                    model_name="SourceSinkModel",
                    variable="operationVariablesOptimum",
                    index=("PV", "consumption_site"),
                )
                / self.config.hours_per_timestep
            )
        else:
            df["solar_generation_kw"] = 0

        df["consumption_kw"] = self.config.consumption_timeseries
        df["energy_price_eur"] = self.config.price_timeseries["grid"]

        self._df_to_sql(df, "timeseries", "output")

    def save_opti_data(self) -> None:
        """Writes the data to the database."""
        log.info("Saving data to database.")

        # create DataFrame
        eco_df = pd.DataFrame()
        tech_df = pd.DataFrame()
        eco_df["name"] = [self.name]
        tech_df["name"] = [self.name]

        # energy itself
        eco_df["energy_costs_eur"] = [
            self._get_val_from_sum(
                model_name="SourceSinkModel",
                index=("grid", "TAC", "[Euro/a]"),
                location="grid",
            )
        ]

        # grid data
        eco_df["grid_energy_costs_eur"] = [
            self._get_val_from_sum(
                model_name="TransmissionModel",
                index=("capacity_price", "operation", "[kWh*h]", "grid"),
                location="consumption_site",
            )
        ]
        eco_df["grid_capacity_costs_eur"] = [
            self._get_val_from_sum(
                model_name="TransmissionModel",
                index=("capacity_price", "invest", "[Euro]", "grid"),
                location="consumption_site",
            )
            * 2
        ]
        tech_df["grid_capacity_kw"] = [
            self._get_val_from_sum(
                model_name="TransmissionModel",
                index=("capacity_price", "capacity", "[kWh]", "grid"),
                location="consumption_site",
            )
        ]

        # storage data
        eco_df["storage_invest_eur"] = self._get_val_from_sum(
            model_name="StorageModel",
            index=("storage", "invest", "[Euro]"),
            location="consumption_site",
        )
        eco_df["storage_annuity_eur"] = self._get_val_from_sum(
            model_name="StorageModel",
            index=("storage", "TAC", "[Euro/a]"),
            location="consumption_site",
        )
        tech_df["storage_capacity_kwh"] = self._get_val_from_sum(
            model_name="StorageModel",
            index=("storage", "capacity", "[kWh*h]"),
            location="consumption_site",
        )

        # inverter data
        eco_df["inverter_invest_eur"] = self._get_val_from_sum(
            model_name="ConversionModel",
            index=("from_storage", "invest", "[Euro]"),
            location="consumption_site",
        )
        eco_df["inverter_annuity_eur"] = self._get_val_from_sum(
            model_name="ConversionModel",
            index=("from_storage", "TAC", "[Euro/a]"),
            location="consumption_site",
        )
        tech_df["inverter_capacity_kw"] = self._get_val_from_sum(
            model_name="ConversionModel",
            index=("from_storage", "capacity", "[kWh]"),
            location="consumption_site",
        )

        # solar data
        eco_df["solar_invest_eur"] = self._get_val_from_sum(
            model_name="SourceSinkModel",
            index=("PV", "invest", "[Euro]"),
            location="consumption_site",
        )
        eco_df["solar_annuity_eur"] = self._get_val_from_sum(
            model_name="SourceSinkModel",
            index=("PV", "TAC", "[Euro/a]"),
            location="consumption_site",
        )
        tech_df["solar_capacity_kwp"] = self._get_val_from_sum(
            model_name="SourceSinkModel",
            index=("PV", "capacity", "[kWh]"),
            location="consumption_site",
        )

        # calculate total costs
        eco_df["total_costs_eur"] = eco_df.drop(columns="name").sum(axis=1)

        # write to sql
        self._df_to_sql(eco_df, "eco", "output")
        self._df_to_sql(tech_df, "tech", "output")
