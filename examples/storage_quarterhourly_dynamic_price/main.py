from loadprofileanalyzer import Config, LoadProfileAnalyzer

import logging

if __name__ == "__main__":

    config = Config("./examples/storage_only_dynamic_price/config.yml")
    lpa = LoadProfileAnalyzer(config=config)
