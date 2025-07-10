from pathlib import Path

from summit_testing_framework.setups.specifiers import (
    DictionaryType,
    DictionaryVersion,
    FirmwareVersion,
    MultiRackServiceConfigSpecifier,
    PartNumber,
    RackServiceConfigSpecifier,
)

from ingenialink.dictionary import Interface

ETH_EVE_SETUP = RackServiceConfigSpecifier.from_firmware(
    part_number=PartNumber.EVE_XCR_C,
    interface=Interface.ETH,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_eve_can/1.2.0/config.xml"),
    firmware=FirmwareVersion("2.4.0"),
    dictionary=DictionaryVersion("2.4.0", DictionaryType.XDF_V2),
)

ETH_CAP_SETUP = RackServiceConfigSpecifier.from_firmware(
    part_number=PartNumber.CAP_XCR_C,
    interface=Interface.ETH,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_cap_can/1.1.0/config.xml"),
    firmware=FirmwareVersion("2.4.0"),
    dictionary=DictionaryVersion("2.4.0", DictionaryType.XDF_V2),
)

ECAT_EVE_SETUP = RackServiceConfigSpecifier.from_firmware(
    part_number=PartNumber.EVE_XCR_E,
    interface=Interface.ECAT,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_eve_ecat/1.2.0/config.xml"),
    firmware=FirmwareVersion("2.6.0"),
    dictionary=DictionaryVersion("2.6.0", DictionaryType.XDF_V2),
)

ECAT_CAP_SETUP = RackServiceConfigSpecifier.from_firmware(
    part_number=PartNumber.CAP_XCR_E,
    interface=Interface.ECAT,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_cap_ecat/1.1.0/config.xml"),
    firmware=FirmwareVersion("2.6.0"),
    dictionary=DictionaryVersion("2.6.0", DictionaryType.XDF_V2),
)

CAN_EVE_SETUP = RackServiceConfigSpecifier.from_firmware(
    part_number=PartNumber.EVE_XCR_C,
    interface=Interface.CAN,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_eve_can/1.2.0/config.xml"),
    firmware=FirmwareVersion("2.4.0"),
    dictionary=DictionaryVersion("2.4.0", DictionaryType.XDF_V2),
)

CAN_CAP_SETUP = RackServiceConfigSpecifier.from_firmware(
    part_number=PartNumber.CAP_XCR_C,
    interface=Interface.CAN,
    config_file=Path("//azr-srv-ingfs1/dist/setups/setup_cap_can/1.1.0/config.xml"),
    firmware=FirmwareVersion("2.4.0"),
    dictionary=DictionaryVersion("2.4.0", DictionaryType.XDF_V2),
)

ECAT_MULTISLAVE_SETUP = MultiRackServiceConfigSpecifier(
    specifiers=[ECAT_EVE_SETUP, ECAT_CAP_SETUP],
)
