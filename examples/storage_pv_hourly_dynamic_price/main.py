import logging

from peakshaving_analyzer import PeakShavingAnalyzer, load_yaml_config

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    config = load_yaml_config("./examples/storage_pv_hourly_dynamic_price/config.yml")
    psa = PeakShavingAnalyzer(config=config)
    results = psa.optimize()
    results.print()
