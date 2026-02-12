from summit_testing_framework.setups.specifiers import VirtualDriveSpecifier

VIRTUAL_DRIVE_SETUP = VirtualDriveSpecifier.from_dictionary(
    ip="127.0.0.1", port=1061, extra_data={"execution_policy": "always"}
)
