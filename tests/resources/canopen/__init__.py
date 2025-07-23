from pathlib import Path

resources_path = absolute_module_path = Path(__file__).parent


TEST_DICT_CAN = (resources_path / "test_dict_can.xdf").as_posix()
TEST_DICT_CAN_AXIS = (resources_path / "test_dict_can_axis.xdf").as_posix()
TEST_DICT_CAN_NO_ATTR_REG = (resources_path / "test_dict_can_no_attr_reg.xdf").as_posix()
TEST_DICT_CAN_V3 = (resources_path / "test_dict_can_v3.0.xdf").as_posix()
TEST_DICT_CAN_V3_AXIS = (resources_path / "test_dict_can_v3.0_axis.xdf").as_posix()
