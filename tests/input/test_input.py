import pandas as pd

from peakshaving_analyzer.input import load_yaml_config


def test_existing_pv():
    conf = load_yaml_config("./tests/input/test_existing_pv_config.yml", test_mode=True)

    # original values are [1, 4, 1], those should get scaled to [0.25, 1, 0.25]
    assert (conf.existing_pv_generation_timeseries["consumption_site"] == pd.Series([0.25, 1, 0.25])).all()
    assert (conf.new_pv_generation_timeseries["consumption_site"] == pd.Series([0.25, 1, 0.25])).all()


def test_brightsky():
    conf = load_yaml_config("./tests/input/test_brightsky_config.yml", test_mode=True)

    # brightsky should fetch for whole year
    assert len(conf.existing_pv_generation_timeseries) == 8760
