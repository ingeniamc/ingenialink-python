from os.path import dirname, join

from . import canopen, comkit, ethercat, ethernet

__all__ = ["canopen", "comkit", "ethernet", "ethercat"]


DIR = dirname(__file__)

TEST_CONFIG_FILE = join(DIR, "test_config_file.xcf")
TEST_DICT_ECAT_EOE_3_0 = join(DIR, "test_dict_ecat_eoe_v3.0.xdf")
