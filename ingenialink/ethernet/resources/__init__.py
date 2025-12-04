from pathlib import Path

resources_path = absolute_module_path = Path(__file__).parent

BASIC_ETHERNET_V2_XDF = (resources_path / "basic_ethernet_dict.xdf").as_posix()