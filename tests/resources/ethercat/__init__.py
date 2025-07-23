from pathlib import Path

resources_path = absolute_module_path = Path(__file__).parent

TEST_DICT_ETHERCAT = (resources_path / "test_dict_ethercat.xdf").as_posix()
TEST_DICT_ETHERCAT_AXIS = (resources_path / "test_dict_ethercat_axis.xdf").as_posix()
TEST_DICT_ETHERCAT_OLD_DIST = (resources_path / "test_dict_ethercat_old_dist.xdf").as_posix()
