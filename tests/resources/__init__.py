from pathlib import Path

from tests.resources import canopen, comkit, ethercat, ethernet

resources_path = absolute_module_path = Path(__file__).parent

DEN_NET_E_2_8_0_xdf_v3 = (resources_path / "den-net-e_2.8.0_v3.xdf").as_posix()
TEST_DICT_ECAT_EOE_SAFE_v3 = (resources_path / "test_dict_ecat_eoe_safe_v3.0.xdf").as_posix()
TEST_DICT_ECAT_EOE_v3 = (resources_path / "test_dict_ecat_eoe_v3.0.xdf").as_posix()
TEST_CONFIG_FILE = (resources_path / "test_config_file.xcf").as_posix()
TEST_DICTIONARY_WITH_TABLES_FOR_ALL_COM_TYPES = (resources_path / "dictionary_with_tables_minimal.xdf3").as_posix()
DEN_NET_E_WITH_TABLES = (resources_path / "den-net-e_dev4f4c26.xdf3").as_posix()

__all__ = [
    "DEN_NET_E_2_8_0_xdf_v3",
    "TEST_DICT_ECAT_EOE_SAFE_v3",
    "TEST_DICT_ECAT_EOE_v3",
    "TEST_CONFIG_FILE",
    "TEST_DICTIONARY_WITH_TABLES_FOR_ALL_COM_TYPES",
    "DEN_NET_E_WITH_TABLES",
    "canopen",
    "comkit",
    "ethercat",
    "ethernet",
]
