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

```
from peakshaving_analyzer import Config, PeakShavingAnalyzer


config = Config("/path/to/your/config/file.yml")
psa = PeakShavingAnalyzer(config=config)
```

The optimization can be adjusted by changing values in the `config.yml` file.

If you're connecting to your own database either create the predefined tables or set `overwrite_existing_optimization` to `False` on the first optimization.

## Examples

In the `examples` directory are four examples:
* A scenario examining only a storage system using hourly values with a fixed, non-dynamic price for the used energy.
* A scenario examining only a storage system using quarterhouly values with a fixed, non-dynamic price for the used energy.
* A scenario examining only a storage system using quarterhourly values with a dynamic, time-depended price for the used energy.
* A scenario examining a storage system as well as a photovoltaic system using hourly values with a dynamic, time-depended price for the used energy.

You can run these examples with `python3 ./examples/example/main.py` from the base directory.

## License

This project is licensed under the terms of the LICENSE file.
