from pathlib import Path

resources_path = absolute_module_path = Path(__file__).parent

VIRTUAL_DRIVE_XCF = (resources_path / "virtual_drive.xcf").as_posix()
VIRTUAL_DRIVE_V2_XDF = (resources_path / "virtual_drive.xdf").as_posix()
VIRTUAL_DRIVE_V3_XDF = (resources_path / "virtual_drive_v3.0.xdf").as_posix()
