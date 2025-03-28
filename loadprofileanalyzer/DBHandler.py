import logging
from copy import deepcopy

import sqlalchemy
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import fine as fn
import pandas as pd
import numpy as np

from loadprofileanalyzer import Config

logger = logging.getLogger("DatabaseHandler")


TABLES = [
    "optimization_parameters",
    "consumption_timeseries"]

class DatabaseHandler:

    def __init__(
            self,
            config: Config,
            esm: fn.EnergySystemModel
            ) -> None:

        self.config = config
        self.esm = esm
        self.engine = sqlalchemy.create_engine(config.db_uri)

        self.name = deepcopy(config.name)
        self.overwrite_existing = deepcopy(config.overwrite_existing_optimization)

        self._test_connection()

        if self.overwrite_existing:
            self._remove_old_optimization()


    def _test_connection(self):
        """Tries to connect to provided database URI in 5 attempts.
        """
        attempt = 0
        try:
            self.engine.connect()
        except sqlalchemy.exc.OperationalError as e:
            if attempt < 5:
                attempt += 1

            logger.error(f"Could not connect to database in 5 tries: {e}")

            raise e


    def _remove_old_optimization(self):
        """Removes old optimization data from the database.
        """
        logger.info("Removing old optimization data from database.")
        try:
            with self.engine.connect() as conn:
                for table in TABLES:
                    sql = text(f"DELETE FROM {table} WHERE name = '{self.name}'")
                    conn.execute(sql)
                conn.commit()
            logger.info("Old optimization data removed from database.")
        except Exception as e:
            logger.error(f"Error removing old optimization data from database: {e}")


    def _df_to_sql(
            self,
            df: pd.DataFrame,
            table_name: str,
    ) -> None:
        """Writes a DataFrame to the database.

        Args:
            df (pd.DataFrame): DataFrame to write.
            table_name (str): Name of the table to write to.
        """
        logger.info(f"Writing DataFrame to {table_name} table in database.")
        try:
            df.to_sql(
                name=table_name,
                con=self.engine,
                if_exists="append",
                index=False,
            )
            logger.info(f"DataFrame written to {table_name} table in database.")
        except IntegrityError as uv:
            logger.error("Optimization already exist! To overwrite, set overwrite_existing_optimization to True.")
        except Exception as e:
            logger.error(f"Error writing DataFrame to {table_name} table in database: {e}")


    def save_all(self) -> None:
        """Saves all data to the database.
        """
        logger.info("Saving all data to database.")
        self.save_config()
        self.save_consumption()
        self.save_grid()

        if self.config.add_storage:
            self.save_storage_data()
            self.save_inverter_data()

        if self.config.add_solar:
            self.save_solar_data()

        logger.info("All data saved to database.")


    def save_config(self) -> None:
        """Writes the configuration to the database.
        """

        # remove unnecessary keys from config
        keys_to_exclude = ["consumption_timeseries", "db_uri", "overwrite_existing_optimization", "auto_opt", "verbose"]
        conf_to_save = {key: value for key, value in vars(self.config).items() if key not in keys_to_exclude}

        # create dataFrame from config
        config_df = pd.DataFrame(conf_to_save, index=[0])

        # write to sql
        self._df_to_sql(config_df, "optimization_parameters")


    def save_consumption(self) -> None:
        """Writes the consumption data to the database.
        """
        logger.info("Saving consumption data to database.")

        # create DataFrame from config
        consumption_df = pd.DataFrame(self.config.consumption_timeseries)
        consumption_df["timestep"] = np.arange(len(consumption_df))
        consumption_df["name"] = self.name

        # write to sql
        self._df_to_sql(consumption_df, "consumption_timeseries")


    def _get_val_from_sum(
            self,
            model_name: str,
            index: tuple[str],
            location) -> float:

        return self.esm.getOptimizationSummary(model_name).loc[index, location]


    def save_grid_data(self) -> None:
        """Writes the costs data to the database.
        """
        logger.info("Saving costs data to database.")

        # create DataFrame
        df = pd.DataFrame()
        df["name"] = [self.name]
        df["grid_energy_costs_eur"] = [self._get_val_from_sum(
            model_name="TransmissionModel",
            index=("capacity_price", "operation", "[kWh*h]", "grid"),
            location="consumption_site")]
        df["grid_capacity_costs_eur"] = [self._get_val_from_sum(
            model_name="TransmissionModel",
            index=("capacity_price", "invest", "[Euro]", "grid"),
            location="consumption_site")]
        df["grid_capacity_kw"] = [self._get_val_from_sum(
            model_name="TransmissionModel",
            index=("capacity_price", "capacity", "[kWh]", "grid"),
            location="consumption_site")]
        df["total_costs"] = df["grid_energy_costs_eur" ] + df["grid_capacity_costs_eur"]

        # write to sql
        self._df_to_sql(df, "grid")


    def save_storage_data(self) -> None:
        """Writes the storage data to the database.
        """
        logger.info("Saving investment costs data to database.")

        # create DataFrame
        df = pd.DataFrame()
        df["name"] = [self.name]
        df["invest_eur"] = self._get_val_from_sum(
            model_name="StorageModel",
            index=("storage", "invest", "[Euro]"),
            location="consumption_site")
        df["annuity_eur"] = self._get_val_from_sum(
            model_name="SourceSinkModel",
            index=("storage", "TAC", "[Euro/a]"),
            location="consumption_site")
        df["capacity_kwh"] = self._get_val_from_sum(
            model_name="StorageModel",
            index=("storage", "capacity", "[kWh*h]"),
            location="consumption_site")

        # write to sql
        self._df_to_sql(df, "storage")


    def save_inverter_data(self) -> None:
        """Writes the inverter data to the database.
        """
        logger.info("Saving inverter data to database.")

        # create DataFrame
        df = pd.DataFrame()
        df["name"] = [self.name]
        df["invest_eur"] = self._get_val_from_sum(
            model_name="ConversionModel",
            index=("from_storage", "invest", "[Euro]"),
            location="consumption_site")
        df["annuity_eur"] = self._get_val_from_sum(
            model_name="ConversionModel",
            index=("from_storage", "TAC", "[Euro/a]"),
            location="consumption_site")
        df["capacity_kw"] = self._get_val_from_sum(
            model_name="ConversionModel",
            index=("inverter", "capacity", "[kWh]"),
            location="consumption_site")

        # write to sql
        self._df_to_sql(df, "inverter")
