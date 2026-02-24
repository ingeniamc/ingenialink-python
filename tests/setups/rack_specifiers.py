from pathlib import Path

from summit_testing_framework.jenkins.pytest_config import PyTestConfig
from summit_testing_framework.setups.specifier_container import SpecifierContainer
from summit_testing_framework.setups.specifiers import (
    DictionaryType,
    MultiRackServiceConfigSpecifier,
    PartNumber,
    RackServiceConfigSpecifier,
    VersionConfig,
)

from ingenialink.dictionary import Interface

__EXECUTION_POLICY_KEY: str = "execution_policy"
__TEST_CONFIGS_KEY: str = "test_configs"
__CONFIG_FILES_PATH: Path = Path(__file__).parent / "config_files"

ECAT_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_E: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.EVE_XCR_E,
        interface=Interface.ECAT,
        config_file=__CONFIG_FILES_PATH / "ethercat/eve_xcr_e.xcf",
        version="2.6.0",
        dictionary_type=DictionaryType.XDF_V2,
        extra_data={
            __EXECUTION_POLICY_KEY: "always",
            __TEST_CONFIGS_KEY: {
                "ECAT_TEST_SESSIONS": PyTestConfig(
                    markers="ethercat",
                    run_test_stage_uid="ethercat_everest",
                    stage_name="EtherCAT Everest",
                )
            },
        },
    ),
    PartNumber.CAP_XCR_E: RackServiceConfigSpecifier.from_version_configs(
        part_number=PartNumber.CAP_XCR_E,
        interface=Interface.ECAT,
        version_configs={
            "2.6.0": VersionConfig.from_version(
                version="2.6.0",
                config_file=__CONFIG_FILES_PATH / "ethercat/cap_xcr_e.xcf",
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "always",
                    __TEST_CONFIGS_KEY: {
                        "ECAT_TEST_SESSIONS": PyTestConfig(
                            markers="ethercat",
                            run_test_stage_uid="ethercat_capitan",
                            stage_name="EtherCAT Capitan - FW. 2.6.0",
                        )
                    },
                },
            ),
            "2.9.0": VersionConfig.from_version(
                version="2.9.0",
                config_file=__CONFIG_FILES_PATH / "ethercat/cap_xcr_e.xcf",
                dictionary_type=DictionaryType.XDF_V2,
                extra_data={
                    __EXECUTION_POLICY_KEY: "always",
                    __TEST_CONFIGS_KEY: {
                        "ECAT_TEST_SESSIONS": PyTestConfig(
                            markers="ethercat",
                            run_test_stage_uid="ethercat_capitan",
                            stage_name="EtherCAT Capitan - FW. 2.9.0",
                        )
                    },
                },
            ),
        },
    ),
})

ETH_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_C: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.EVE_XCR_C,
        interface=Interface.ETH,
        config_file=__CONFIG_FILES_PATH / "canopen/eve_xcr_c.xcf",
        version="2.4.0",
        dictionary_type=DictionaryType.XDF_V2,
        extra_data={
            __EXECUTION_POLICY_KEY: "always",
            __TEST_CONFIGS_KEY: {
                "ETH_TEST_SESSIONS": PyTestConfig(
                    markers="ethernet",
                    run_test_stage_uid="ethernet_everest",
                    stage_name="Ethernet Everest",
                )
            },
        },
    ),
    PartNumber.CAP_XCR_C: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.CAP_XCR_C,
        interface=Interface.ETH,
        config_file=__CONFIG_FILES_PATH / "canopen/cap_xcr_c.xcf",
        version="2.4.0",
        dictionary_type=DictionaryType.XDF_V2,
        extra_data={
            __EXECUTION_POLICY_KEY: "always",
            __TEST_CONFIGS_KEY: {
                "ETH_TEST_SESSIONS": PyTestConfig(
                    markers="ethernet",
                    run_test_stage_uid="ethernet_capitan",
                    stage_name="Ethernet Capitan",
                )
            },
        },
    ),
})

CAN_SETUP = SpecifierContainer({
    PartNumber.EVE_XCR_C: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.EVE_XCR_C,
        interface=Interface.CAN,
        config_file=__CONFIG_FILES_PATH / "canopen/eve_xcr_c.xcf",
        version="2.4.0",
        dictionary_type=DictionaryType.XDF_V2,
        extra_data={
            __EXECUTION_POLICY_KEY: "always",
            __TEST_CONFIGS_KEY: {
                "CAN_TEST_SESSIONS": PyTestConfig(
                    markers="canopen",
                    run_test_stage_uid="canopen_everest",
                    stage_name="CANopen Everest",
                )
            },
        },
    ),
    PartNumber.CAP_XCR_C: RackServiceConfigSpecifier.from_firmware(
        part_number=PartNumber.CAP_XCR_C,
        interface=Interface.CAN,
        config_file=__CONFIG_FILES_PATH / "canopen/cap_xcr_c.xcf",
        version="2.4.0",
        dictionary_type=DictionaryType.XDF_V2,
        extra_data={
            __EXECUTION_POLICY_KEY: "always",
            __TEST_CONFIGS_KEY: {
                "CAN_TEST_SESSIONS": PyTestConfig(
                    markers="canopen",
                    run_test_stage_uid="canopen_capitan",
                    stage_name="CANopen Capitan",
                )
            },
        },
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
            extra_data={
                __EXECUTION_POLICY_KEY: "always",
                __TEST_CONFIGS_KEY: {
                    "ECAT_TEST_SESSIONS": PyTestConfig(
                        markers="fsoe",
                        run_test_stage_uid="fsoe_phase1",
                        stage_name="Safety Denali Phase I",
                    )
                },
            },
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
            extra_data={
                __EXECUTION_POLICY_KEY: "always",
                __TEST_CONFIGS_KEY: {
                    "ECAT_TEST_SESSIONS": PyTestConfig(
                        markers="fsoe",
                        run_test_stage_uid="fsoe_phase2",
                        stage_name="Safety Denali Phase II",
                    )
                },
            },
        ),
    },
)

ECAT_MULTISLAVE_SETUP = MultiRackServiceConfigSpecifier.create(
    identifier="ECAT_MULTISLAVE",
    specifiers=[
        ECAT_SETUP.get_specifier_by_identifier(PartNumber.EVE_XCR_E),
        ECAT_SETUP.get_specifier_by_identifier_with_version(
            identifier=PartNumber.CAP_XCR_E, version="2.6.0"
        ),
    ],
    extra_data={
        __EXECUTION_POLICY_KEY: "always",
        __TEST_CONFIGS_KEY: {
            "ECAT_TEST_SESSIONS": PyTestConfig(
                markers="multislave",
                run_test_stage_uid="ethercat_multislave",
                stage_name="EtherCAT Multislave",
            )
        },
    },
)
