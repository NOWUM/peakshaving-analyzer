from loadprofileanalyzer import Config, LoadProfileAnalyzer

if __name__ == "__main__":

    config = Config("./examples/storage_pv_hourly_dynamic_price/config.yml")
    lpa = LoadProfileAnalyzer(config=config)
