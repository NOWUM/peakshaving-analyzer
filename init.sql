CREATE SCHEMA IF NOT EXISTS input;
CREATE SCHEMA IF NOT EXISTS output;

CREATE TABLE IF NOT EXISTS input.parameters (
    name TEXT PRIMARY KEY,
    hours_per_timestep FLOAT NOT NULL,
    n_timesteps INTEGER NOT NULL,
    postal_code INTEGER,
    add_storage BOOL NOT NULL,
    add_solar BOOL NOT NULL,
    producer_energy_price FLOAT NOT NULL,
    grid_capacity_price FLOAT NOT NULL,
    grid_energy_price FLOAT NOT NULL,
    pv_system_lifetime INTEGER NOT NULL,
    pv_system_cost_per_kwp FLOAT NOT NULL,
    storage_lifetime INTEGER NOT NULL,
    storage_cost_per_kwh FLOAT NOT NULL,
    inverter_cost_per_kw FLOAT NOT NULL,
    inverter_lifetime INTEGER NOT NULL,
    interest_rate FLOAT NOT NULL,
    max_storage_size_kwh FLOAT,
    max_pv_system_size_kwp FLOAT,
    storage_charge_efficiency FLOAT NOT NULL,
    storage_discharge_efficiency FLOAT NOT NULL,
    storage_charge_rate FLOAT NOT NULL,
    storage_discharge_rate FLOAT NOT NULL,
    inverter_efficiency FLOAT NOT NULL,
    pv_system_kwp_per_m2 FLOAT NOT NULL,
    solver TEXT NOT NULL,
    assumed_year INTEGER NOT NULL,
    leap_year BOOL NOT NULL
);

CREATE TABLE IF NOT EXISTS input.timeseries (
    name TEXT NOT NULL,
    timestamp timestamptz NOT NULL,
    consumption_kw FLOAT NOT NULL,
    price_eur FLOAT NOT NULL,
    solar_generation FLOAT NOT NULL,
    PRIMARY KEY (name, timestamp)
);

CREATE TABLE IF NOT EXISTS output.eco (
    name TEXT PRIMARY KEY,
    energy_costs_eur FLOAT NOT NULL,
    grid_energy_costs_eur FLOAT NOT NULL,
    grid_capacity_costs_eur FLOAT NOT NULL,
    storage_invest_eur FLOAT NOT NULL,
    storage_annuity_eur FLOAT NOT NULL,
    inverter_invest_eur FLOAT NOT NULL,
    inverter_annuity_eur FLOAT NOT NULL,
    solar_invest_eur FLOAT NOT NULL,
    solar_annuity_eur FLOAT NOT NULL,
    total_costs_eur FLOAT NOT NULL
);

CREATE TABLE IF NOT EXISTS output.tech (
    name TEXT PRIMARY KEY,
    grid_capacity_kw FLOAT NOT NULL,
    storage_capacity_kwh FLOAT NOT NULL,
    inverter_capacity_kw FLOAT NOT NULL,
    solar_capacity_kwp FLOAT NOT NULL
);

CREATE TABLE IF NOT EXISTS output.timeseries (
    name TEXT NOT NULL,
    timestamp timestamptz NOT NULL,
    grid_usage_kw FLOAT,
    storage_charge_kw FLOAT,
    storage_discharge_kw FLOAT,
    storage_soc_kwh FLOAT,
    solar_generation_kw FLOAT,
    consumption_kw FLOAT NOT NULL,
    energy_price_eur FLOAT NOT NULL
    PRIMARY KEY (name, timestamp)
);
