from peakshaving_analyzer import PeakShavingAnalyzer, load_yaml_config

if __name__ == "__main__":
    config = load_yaml_config("./examples/storage_hourly_fixed_price/config.yml")
    psa = PeakShavingAnalyzer(config=config)
    results = psa.optimize()
