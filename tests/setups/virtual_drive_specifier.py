from summit_testing_framework.jenkins.pytest_config import PyTestConfig
from summit_testing_framework.setups.specifiers import VirtualDriveSpecifier

VIRTUAL_DRIVE_ETHERNET_SETUP = VirtualDriveSpecifier.from_ethernet(
    extra_data={
        "execution_policy": "always",
        "test_configs": {
            "LINUX_DOCKER_TEST_SESSIONS": PyTestConfig(
                markers="virtual",
                run_test_stage_uid="virtual_drive_tests",
                stage_name="Virtual Drive Ethernet Tests",
            )
        },
    }
)
