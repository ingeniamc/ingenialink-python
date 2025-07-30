from pathlib import Path

resources_path = absolute_module_path = Path(__file__).parent

TEST_DICT_ETHERNET = (resources_path / "test_dict_eth.xdf").as_posix()
TEST_DICT_ETHERNET_AXIS = (resources_path / "test_dict_eth_axis.xdf").as_posix()
