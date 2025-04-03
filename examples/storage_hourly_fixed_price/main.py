from loadprofileanalyzer import Config, LoadProfileAnalyzer

if __name__ == "__main__":

    config = Config("./config.yml")
    lpa = LoadProfileAnalyzer(config=config)
