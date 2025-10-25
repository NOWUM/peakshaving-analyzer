from dataclasses import dataclass

import pandas as pd

from peakshaving_analyzer.common import IOHandler


@dataclass
class Config(IOHandler):
    # general parameters
    name: str
    overwrite_existing_optimization: bool = False
    add_storage: bool = True
    allow_additional_pv: bool = False
    auto_opt: bool = False
    solver: str = "appsi_highs"
    verbose: bool = False
    postal_code: int | str | None = None

    # general timeseries
    consumption_timeseries: pd.Series | None = None
    price_timeseries: pd.DataFrame | None = None

    # storage system (battery) parameters
    storage_lifetime: int = 15
    storage_cost_per_kwh: float = 285
    storage_charge_efficiency: float = 0.95
    storage_discharge_efficiency: float = 0.95
    storage_charge_rate: float = 5
    storage_cyclic_lifetime: float = 10000
    storage_discharge_rate: float = 5
    max_storage_size_kwh: float | None = None

    # storage system (inverter) parameters
    inverter_efficiency: float = 0.95
    inverter_cost_per_kw: float = 180
    inverter_lifetime: int = 15
    max_inverter_charge: float | None = None
    max_inverter_discharge: float | None = None

    # Existing PV system parameters
    pv_system_already_exists: bool = False
    existing_pv_size_kwp: float | None = None
    existing_pv_generation_timeseries: pd.DataFrame | None = None

    # New PV system parameters
    pv_system_lifetime: int = 30
    pv_system_cost_per_kwp: float = 1200.0
    max_pv_system_size_kwp: float | None = None
    pv_system_kwp_per_m2: float = 0.4
    new_pv_generation_timeseries: pd.DataFrame | None = None

    # economic parameters
    overwrite_price_timeseries: bool = False
    producer_energy_price: float = 0.1665
    grid_capacity_price: float = 101.22
    grid_energy_price: float = 0.046
    interest_rate: float = 2

    # metadata needed for optimization (set by peakshaving analyzer)
    timestamps: pd.DatetimeIndex | None = None
    n_timesteps: int | None = None
    hours_per_timestep: float | None = None

    def timeseries_to_df(self) -> pd.DataFrame:
        """Return a small dataframe assembled from contained timeseries (pure, no IO)."""
        df = pd.DataFrame()

        if self.consumption_timeseries is not None:
            df["consumption_kw"] = self.consumption_timeseries

        if self.price_timeseries is not None and "grid" in self.price_timeseries:
            df["energy_price_eur"] = self.price_timeseries["grid"]

        if self.new_pv_generation_timeseries is not None:
            df["new_pv_generation_kw"] = self.new_pv_generation_timeseries["consumption_site"]

        return df
