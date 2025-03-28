import logging
from copy import deepcopy

import sqlalchemy
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import fine as fn
import pandas as pd
from psycopg2.errors import UniqueViolation

from loadprofileanalyzer import Config

logger = logging.getLogger("DatabaseHandler")


TABLES = [
    "optimization_parameters",]

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
        self.overwrite_existing = deepcopy(config.overwrite_existing_optimization   )

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
