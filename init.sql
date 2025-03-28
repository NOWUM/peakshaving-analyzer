CREATE TABLE IF NOT EXISTS optimization_parameters (
    name TEXT PRIMARY KEY,
    hours_per_timestep FLOAT NOT NULL,
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
    solver TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS consumption_timeseries (
    name TEXT NOT NULL,
    timestep INTEGER NOT NULL,
    consumption FLOAT NOT NULL,
    PRIMARY KEY (name, timestep)
);
