from pathlib import Path

from summit_testing_framework.execution_policies import ExecutionPolicies
from summit_testing_framework.setups.specifier_container import SpecifierContainer
from summit_testing_framework.setups.specifiers import (
    DictionaryType,
    MultiRackServiceConfigSpecifier,
    PartNumber,
    RackServiceConfigSpecifier,
    VersionConfig,
)

from ingenialink.dictionary import Interface

ECAT_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_E: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.EVE_XCR_E,
        interface=Interface.ECAT,
        config_file=Path("//azr-srv-ingfs1/dist/setups/setup_eve_ecat/1.2.0/config.xml"),
        version="2.6.0",
        dictionary_type=DictionaryType.XDF_V2,
        execution_policy=ExecutionPolicies.ALWAYS,
    ),
    PartNumber.CAP_XCR_E: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.CAP_XCR_E,
        interface=Interface.ECAT,
        config_file=Path("//azr-srv-ingfs1/dist/setups/setup_cap_ecat/1.1.0/config.xml"),
        version="2.6.0",
        dictionary_type=DictionaryType.XDF_V2,
        execution_policy=ExecutionPolicies.ALWAYS,
    ),
})

ETH_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_C: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.EVE_XCR_C,
        interface=Interface.ETH,
        config_file=Path("//azr-srv-ingfs1/dist/setups/setup_eve_can/1.2.0/config.xml"),
        version="2.4.0",
        dictionary_type=DictionaryType.XDF_V2,
        execution_policy=ExecutionPolicies.ALWAYS,
    ),
    PartNumber.CAP_XCR_C: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.CAP_XCR_C,
        interface=Interface.ETH,
        config_file=Path("//azr-srv-ingfs1/dist/setups/setup_cap_can/1.1.0/config.xml"),
        version="2.4.0",
        dictionary_type=DictionaryType.XDF_V2,
        execution_policy=ExecutionPolicies.ALWAYS,
    ),
})

CAN_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_C: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.EVE_XCR_C,
        interface=Interface.CAN,
        config_file=Path("//azr-srv-ingfs1/dist/setups/setup_eve_can/1.2.0/config.xml"),
        version="2.4.0",
        dictionary_type=DictionaryType.XDF_V2,
        execution_policy=ExecutionPolicies.ALWAYS,
    ),
    PartNumber.CAP_XCR_C: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.CAP_XCR_C,
        interface=Interface.CAN,
        config_file=Path("//azr-srv-ingfs1/dist/setups/setup_cap_can/1.1.0/config.xml"),
        version="2.4.0",
        dictionary_type=DictionaryType.XDF_V2,
        execution_policy=ExecutionPolicies.ALWAYS,
    ),
})


ECAT_DEN_S_NET_E_SETUP = RackServiceConfigSpecifier.from_version_configs(
    part_number=PartNumber.DEN_S_NET_E,
    interface=Interface.ECAT,
    version_configs={
        "PHASE1": VersionConfig.from_version(
            version="2.7.4",
            config_file=None,
            dictionary_type=DictionaryType.XDF_V2,
            execution_policy=ExecutionPolicies.ALWAYS,
        ),
        "PHASE2": VersionConfig.from_files(
            version="2.9.0.16",
            config_file=None,
            firmware=Path(
                "//azr-srv-ingfs1/dist/products/i050_summit/i056_den-s-net-e/release_candidate/2.9.0.8/den-s-net-e_2.9.0.lfu"
            ),
            dictionary=Path(
                "//azr-srv-ingfs1/dist/products/i050_summit/i056_den-s-net-e/release_candidate/2.9.0.8/den-s-net-e_2.9.0.008_v3.xdf"
            ),
            execution_policy=ExecutionPolicies.ALWAYS,
        ),
    },
)

ECAT_MULTISLAVE_SETUP = MultiRackServiceConfigSpecifier.create(
    specifiers=[
        ECAT_SETUP.get_specifier_by_identifier(PartNumber.EVE_XCR_E),
        ECAT_SETUP.get_specifier_by_identifier(PartNumber.CAP_XCR_E),
    ],
    execution_policy=ExecutionPolicies.ALWAYS,
)
