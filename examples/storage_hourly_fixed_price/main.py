from peakshaving_analyzer import Config, PeakShavingAnalyzer

if __name__ == "__main__":

    config = Config("./examples/storage_hourly_fixed_price/config.yml")
    psa = PeakShavingAnalyzer(config=config)
