import json
from dataclasses import asdict, fields
from pathlib import Path

import pandas as pd
import plotly.express as px
import yaml


class IOHandler:
    def print(self, include_timeseries: bool = False):
        for field in fields(self):
            if include_timeseries:
                print(f"{field.name}: {getattr(self, field.name)}")
            elif isinstance(getattr(self, field.name), (pd.Series | pd.DataFrame | pd.DatetimeIndex)):
                continue
            else:
                print(f"{field.name}: {getattr(self, field.name)}")

    def to_dict(self, include_timeseries: bool = True) -> dict:
        if include_timeseries:
            return asdict(self)
        else:
            return {
                k: v
                for k, v in asdict(self).items()
                if not isinstance(v, (pd.Series | pd.DataFrame | pd.DatetimeIndex | list))
            }

    def to_json(self, path: str | Path):
        with open(path, "w") as f:
            json.dump(self.to_dict(include_timeseries=False), f, indent=4)

    def to_yaml(self, path: str | Path):
        with open(path, "w") as f:
            yaml.safe_dump(self.to_dict(include_timeseries=False), f, sort_keys=False)

    def _plot(self, cols_to_plot: list[str] | None = None):
        ts_df = self.timeseries_to_df()

        if not cols_to_plot:
            cols_to_plot = ts_df.columns.tolist()

        fig = px.line(ts_df, x=ts_df.index, y=cols_to_plot)
        fig.show()

    def plot_timeseries(self):
        self._plot()
