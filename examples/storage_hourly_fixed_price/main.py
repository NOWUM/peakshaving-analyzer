from loadprofileanalyzer import Config, LoadProfileAnalyzer

if __name__ == "__main__":

    config = Config("./examples/storage_hourly_fixed_price/config.yml")
    lpa = LoadProfileAnalyzer(config=config)
