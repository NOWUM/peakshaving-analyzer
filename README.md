# Peak Shaving Analyzer

This repository contains tools and utilities for analyzing and optimizing energy consumption with peak shaving strategies. The project includes data fetching, analysis, and visualization components, as well as Docker configurations for deployment.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Examples](#examples)
- [License](#license)

## Overview

Peak shaving is a strategy to reduce energy costs by minimizing peak demand utilizing energy storage systems. This project provides tools to optimize a given consumption time series with peak-shaving reducing capacity costs and visualizing results using Grafana.

## Features

- Peak shaving optimization using [FINE by FZJ](https://github.com/FZJ-IEK3-VSA/FINE)
- Easy configuration of many parameters
- Support for dynamic prices
- Inclusion of PV system integration with automatic retrieving of generation timeseries depending on location (with detection for leap years)
- Dockerized deployment with Grafana dashboards
- Example configurations for various scenarios

## Installation

You can install peakshaving-analyzer using pip. Choose the appropriate installation method based on your needs:

### Using pip

To install the core package:

```bash
pip install peakshaving-analyzer
```

### Timescale Database and Grafana Dashboards

If you want to benefit from a supported database and integrated Grafana dashboards for scenario analysis, you can use the provided Docker Compose file.

Follow these steps:

1. Clone the repository and navigate to its directory:

```bash
git clone https://github.com/NOWUM/peakshaving-analyzer.git
cd peakshaving-analyzer
```

2. Start the database and Grafana using the following command:

```bash
docker compose up -d
```

This will launch a container for TimescaleDB and Grafana with preconfigured dashboards for analysis. You can access the Grafana dashboards at `http://localhost:3000`.

## Usage

You can use Peak Shaving Analyzer flexibly – either with a YAML configuration file, directly from Python code or use the [OpenEnergyDataServer](https://github.com/open-energy-data-server/open-energy-data-server). Results can be saved locally as files or in a database.

### Using the CLI

Use `psa -h` to see the usage of the CLI tool and it's options.

### Loading the Configuration

**1. Load from YAML configuration file:**
```python
from peakshaving_analyzer import PeakShavingAnalyzer, load_yaml_config

config = load_yaml_config("/path/to/your/config.yml")
```

**2. Load from OEDS:**
```python
from peakshaving_analyzer import PeakShavingAnalyzer, load_oeds_config

config = load_oeds_config(load_oeds_config(con="your/database/uri", profile_id=id_to_analyze))
```

**3. Load from a Python dictionary:**

Please note that a lot of configuration is done by the loaders, so it's best to use one of the provided loaders.
```python
from peakshaving_analyzer import PeakShavingAnalyzer, Config

config_dict = {
    "name": "MyScenario",
    "consumption_timeseries": [...],
    # further parameters
}
config = Config(config_dict)
```

### Initialize the Peakshaving Analyzer and run it:

Running the `optimize()` method will return a `Results` object.
```python
psa = PeakShavingAnalyzer(config=config)
results = psa.optimize(solver="your_prefered_solver")
```

### Saving Results

Results objects can be printed to std-out, written to file (.csv, .yaml, .json) or converted to python objects.

**1. Save as file (e.g. CSV, YAML, ...):**
```python
results = psa.optimize()
results.to_csv("results.csv")
results.to_json("results.json")
results.to_yaml("results.yaml")
```

For saving the timeseries, please use the following functions:
```python
results = psa.optimize()
results.timeseries_to_csv("timeseries.csv")
results.timeseries_to_json("timeseries.json")
```


**2. Save to database (TimescaleDB):**
If you use the Docker environment, results are automatically written to TimescaleDB. You can also trigger saving explicitly:
```python
results = psa.optimize()
results.to_sql(connection="your/database/uri")
```

**3. Use as Python object:**

After optimization, results are available as a Python object for further processing:
```python
results = psa.optimize()
# Access individual values
print(results.total_yearly_costs_eur)

# print everything
results.print()

# convert to dict or dataframe
results_dict = results.to_dict()
results_dataframe = results.to_dataframe()
```

**4. Plot the resulting timeseries:**

The resulting timeseries (storage charging / discharging, state of charge, PV generation, grid usage, ...) can be easily plotted:

```python
results = psa.optimize()
results.plot_timeseries()
results.plot_consumption_timeseries()
results.plot_storage_timeseries()
```

For more details on configuration, see the example files in the `examples` directory.

## Examples

In the `examples` directory are four examples:
* A scenario examining only a storage system using hourly values with a fixed, non-dynamic price for the used energy.
* A scenario examining only a storage system using quarterhouly values with a fixed, non-dynamic price for the used energy.
* A scenario examining only a storage system using quarterhourly values with a dynamic, time-depended price for the used energy.
* A scenario examining a storage system as well as a photovoltaic system using hourly values with a dynamic, time-depended price for the used energy.

You can run these examples with `python3 ./examples/example/main.py` from the base directory.

## License

This project is licensed under the terms of the LICENSE file.
