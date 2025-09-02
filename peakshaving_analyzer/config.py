import logging
from dataclasses import dataclass

import pandas as pd

log = logging.getLogger("peakshaving_config")


@dataclass
class Config:
    # general parameters
    name: str
    db_uri: str | None = None
    overwrite_existing_optimization: bool = False
    add_storage: bool = True
    add_solar: bool = False
    auto_opt: bool = False
    solver: str | None = "appsi_highs"
    verbose: bool = False

    # timeseries
    consumption_timeseries: pd.Series | None = None
    price_timeseries: pd.Series | None = None
    solar_generation_timeseries: pd.Series | None = None

    # economic parameters
    overwrite_price_timeseries: bool = False
    producer_energy_price: float | None = None
    grid_capacity_price: float | None = None
    grid_energy_price: float | None = None
    pv_system_lifetime: int | None = None
    pv_system_cost_per_kwp: float | None = None
    inverter_lifetime: int | None = None
    inverter_cost_per_kw: float | None = None
    storage_lifetime: int | None = None
    storage_cost_per_kwh: float | None = None
    interest_rate: float | None = None

    # technical parameters
    max_storage_size_kwh: float | None = None
    storage_charge_efficiency: float | None = None
    storage_discharge_efficiency: float | None = None
    storage_charge_rate: float | None = None
    storage_discharge_rate: float | None = None
    inverter_efficiency: float | None = None
    max_pv_system_size_kwp: float | None = None
    pv_system_kwp_per_m2: float | None = None

    # metadata needed for optimization (set by peakshaving analyzer)
    timestamps: pd.DatetimeIndex | None = None
    n_timesteps: int | None = None
    hours_per_timestep: float | None = None
