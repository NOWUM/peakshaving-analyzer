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


SOLAR_PROFILE_HOURLY = [0] * 6 + [0.2, 0.4, 0.6, 0.8, 1, 1, 1, 1, 0.8, 0.6, 0.4, 0.2] + [0] * 6


def test_add_solar():
    n_timesteps = 48
    solar_profile = SOLAR_PROFILE_HOURLY * (1 + 50 // len(SOLAR_PROFILE_HOURLY))
    solar_profile = solar_profile[0:n_timesteps]
    config = Config(
        "test_config",
        consumption_timeseries=[1] * n_timesteps,
        hours_per_timestep=1,
        n_timesteps=n_timesteps,
        price_timeseries=pd.DataFrame({"grid": [0.3] * n_timesteps, "consumption_site": [0] * n_timesteps}),
        add_solar=True,
        solar_generation_timeseries=pd.DataFrame({"grid": 0, "consumption_site": solar_profile}),
        interest_rate=0,
    )
    psa = PeakShavingAnalyzer(config=config)
    results = psa.optimize()

    # check that an inverter and storage is available
    assert results.inverter_capacity_kw >= 5
    assert results.storage_capacity_kwh >= 10
    assert results.grid_capacity_kw == 1
    assert results.solar_capacity_kwp >= 3

    # energy costs are now much lower
    assert results.energy_costs_eur < 400
    assert isclose(results.grid_capacity_costs_eur, config.grid_capacity_price * 1)
    assert isclose(results.inverter_invest_eur, results.inverter_capacity_kw * config.inverter_cost_per_kw)

    # sum of investment should match
    assert (
        results.total_invest_eur == results.solar_invest_eur + results.inverter_invest_eur + results.storage_invest_eur
    )

    # annuities should match
    assert (
        results.total_yearly_costs_eur
        == results.energy_costs_eur
        + results.grid_energy_costs_eur
        + results.grid_capacity_costs_eur
        + results.solar_annuity_eur
        + results.inverter_annuity_eur
        + results.storage_annuity_eur
    )


def test_storage_only():
    # 4 cheap hours, one expensive hour
    # adding a storage of 1 kwh reduces cost here
    config = Config(
        "test_config",
        consumption_timeseries=[1] * 6,
        hours_per_timestep=1,
        n_timesteps=6,
        price_timeseries=pd.DataFrame({"grid": [0.3] * 4 + [1] + [0.3], "consumption_site": [0] * 6}),
        storage_charge_rate=10,
        storage_discharge_rate=10,
        # cyclic lifetime must be increased, otherwise we are building much more storage
        storage_cyclic_lifetime=1e5,
        interest_rate=2,
        storage_charge_efficiency=1,
        storage_discharge_efficiency=1,
    )
    psa = PeakShavingAnalyzer(config=config)
    results = psa.optimize()
    ts = results.timeseries_to_df()
    # we need to charge in the first few hours
    assert (ts["grid_usage_kw"][0:4] >= 1).all()
    # but do not charge in the last hour
    assert (ts["grid_usage_kw"][4] == 0).all()

    assert results.inverter_capacity_kw == 1
    results.storage_capacity_kwh
    assert results.storage_capacity_kwh == 1
