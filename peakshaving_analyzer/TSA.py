import logging

import plotly.express as px
import plotly.graph_objects as go
from statsmodels.tsa import seasonal

from peakshaving_analyzer.config import Config

log = logging.getLogger(__name__)


class TimeseriesAnalyzer:
    """Analysis helpers that operate on a `Config` instance.

    This keeps plotting and statistics out of the pure dataclass.
    """

    def __init__(self, config: Config):
        self.config = config

    def timeseries_to_df(self):
        return self.config.timeseries_to_df()

    def calculate_statistics(self, print_out: bool = False) -> dict[str, float]:
        ts_df = self.timeseries_to_df()
        stats = {}

        stats["min_load_kw"] = ts_df["consumption_kw"].min()
        stats["max_load_kw"] = ts_df["consumption_kw"].max()
        stats["mean_load_kw"] = ts_df["consumption_kw"].mean()
        stats["median_load_kw"] = ts_df["consumption_kw"].median()
        stats["variance"] = ts_df["consumption_kw"].var()
        stats["std"] = ts_df["consumption_kw"].std()
        stats["total_consumption_kwh"] = ts_df["consumption_kw"].sum() * self.config.hours_per_timestep

        if print_out:
            for key, value in stats.items():
                print(f"{key}: {value}")

        return stats

    def plot_load_duration_curve(self):
        ts_df = self.timeseries_to_df()

        fig = px.line(
            data_frame=ts_df.sort_values("consumption_kw", ascending=False, ignore_index=True),
            x=ts_df.index,
            y="consumption_kw",
            title="Load duration curve",
        )
        fig.update_layout(xaxis_title="Number of times", yaxis_title="Load in kW")

        fig.show()

    def plot_load_histogram(self):
        ts_df = self.timeseries_to_df()

        fig = px.histogram(data_frame=ts_df, x="consumption_kw", title="Histogram of load")
        fig.update_layout(xaxis_title="Load in kW")

        fig.show()

    def plot_load_box(self):
        ts_df = self.timeseries_to_df()

        fig = px.box(
            data_frame=ts_df,
            x="consumption_kw",
            title="Boxplot of load",
        )
        fig.update_layout(xaxis_title="Load in kW")

        fig.show()

    def seasonal_decompose(self) -> seasonal.DecomposeResult:
        ts_df = self.timeseries_to_df()
        ts_df.index = self.config.timestamps.copy()

        decompose_result = seasonal.seasonal_decompose(x=ts_df["consumption_kw"])

        return decompose_result

    def plot_seasonal_decompose(self):
        decompose_result = self.seasonal_decompose()

        fig = go.Figure()
        for var in ["seasonal", "trend", "resid"]:
            fig.add_scatter(
                x=self.config.timestamps,
                y=getattr(decompose_result, var),
                name=var,
            )

        fig.update_layout(
            title="Seasonal decomposition",
            xaxis_title="Time",
            yaxis_title="Load in kW",
        )

        fig.show()
