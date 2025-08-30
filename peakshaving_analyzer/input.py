import logging
from pathlib import Path

import pandas as pd
import yaml

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class InputHandler:
    def __init__(self, data: dict[str], *args, **kwds):
        self.data = data

        # read in consumption timeseries
        data["consumption_timeseries"] = self.read_csv_timeseries(
            path=data["consumption_timeseries_path"],
            value_column=data.get("consumption_value_column", "value"),
            target_column="consumption",
        )

        data["n_timesteps"] = len(data["consumption_timeseries"])
        data["leap_year"] = self.detect_leap_year()
        data["assumed_year"] = self._assume_year()
        data["timestamps"] = self._create_timestamps()

        # check and read price information
        data["price_timeseries"] = self._read_or_create_price_timeseries(data)

    def _read_or_create_price_timeseries(self, data):
        # if no filepath is given, we either...
        if not data.get("price_file_path"):
            # throw an error if no price information is given
            if not data.get("producer_energy_price"):
                msg = "No price information found."
                msg += "Please provide either producer_energy_price or "
                msg += "price_file_path in the configuration file."
                log.error(msg)

            # ... or create a timeseries from a fixed price
            else:
                return pd.Series(data=data["producer_energy_price"], index=data["timestamps"])

        # if the filepath is given, we either ...
        else:
            # we overwrite the timeseries by given fixed price
            if data.get("overwrite_price_timeseries"):
                return pd.Series(data=data["producer_energy_price"], index=data["timestamps"])

            # or just read in the series from file
            else:
                return self.read_csv_timeseries(
                    path=data["price_file_path"],
                    value_column=data.get("price_value_column", "value"),
                    target_column="price",
                )


class YAMLHandler(InputHandler):
    def __init__(self, config_path: Path | str) -> None:
        with open(config_path) as file:
            data = yaml.safe_load(file)
            log.info("Configuration file loaded")

        super().__init__(data)

    def read_csv_timeseries(self, path: str, value_column: str, target_column: str) -> pd.Series:
        """Reads consumption timeseries from given .csv-file

        Returns:
            pd.Series: the target timeseries.
        """

        log.info("Reading consumption timeseries")

        df = pd.read_csv(path)
        df.rename(columns={value_column: target_column}, inplace=True)
        log.info("Consumption timeseries loaded.")

        return df[target_column]
