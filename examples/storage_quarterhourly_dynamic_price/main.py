from loadprofileanalyzer import Config, LoadProfileAnalyzer

import logging

if __name__ == "__main__":

    config = Config("./examples/storage_quarterhourly_dynamic_price/config.yml")
    lpa = LoadProfileAnalyzer(config=config)
