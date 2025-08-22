from pathlib import Path

resources_path = absolute_module_path = Path(__file__).parent

COM_KIT_DICT = (resources_path / "com-kit.xdf").as_posix()
CORE_DICT = (resources_path / "core.xdf").as_posix()
