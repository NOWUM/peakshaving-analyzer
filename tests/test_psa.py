from math import isclose

import pandas as pd
import pytest

from peakshaving_analyzer.input import Config
from peakshaving_analyzer.PSA import PeakShavingAnalyzer


def test_charge_from_grid():
    config = Config(
        "test_config",
        consumption_timeseries=[1, 1, 1, 1, 1],
        hours_per_timestep=1,
        n_timesteps=5,
        price_timeseries=pd.DataFrame({"grid": [0.3] * 5, "consumption_site": [0] * 5}),
    )
    psa = PeakShavingAnalyzer(config=config)
    results = psa.optimize()
    ts = results.timeseries_to_df()
    assert (ts["grid_usage_kw"] == 1).all()
    assert results.energy_costs_eur == 8760 * 0.3
    assert isclose(results.grid_energy_costs_eur, 8760 * config.grid_energy_price)
    assert isclose(results.grid_capacity_costs_eur, config.grid_capacity_price)

    # sum of prices should match
    assert (
        results.total_yearly_costs_eur
        == results.energy_costs_eur + results.grid_energy_costs_eur + results.grid_capacity_costs_eur
    )


@pytest.mark.parametrize("n_timesteps", [1, 2, 50, 100])
def test_various_steps(n_timesteps):
    energy_price = 300

    config = Config(
        "test_config",
        consumption_timeseries=[1] * n_timesteps,
        hours_per_timestep=1,
        n_timesteps=n_timesteps,
        price_timeseries=pd.DataFrame({"grid": [energy_price] * n_timesteps, "consumption_site": [0] * n_timesteps}),
    )
    psa = PeakShavingAnalyzer(config=config)
    results = psa.optimize()
    results.to_dict(include_timeseries=False)
    ts = results.timeseries_to_df()
    assert (ts["grid_usage_kw"] == 1).all()
    assert results.energy_costs_eur == 8760 * energy_price
    assert isclose(results.grid_energy_costs_eur, 8760 * config.grid_energy_price)
    assert isclose(results.grid_capacity_costs_eur, config.grid_capacity_price)

    # sum of prices should match
    assert (
        results.total_yearly_costs_eur
        == results.energy_costs_eur + results.grid_energy_costs_eur + results.grid_capacity_costs_eur
    )
