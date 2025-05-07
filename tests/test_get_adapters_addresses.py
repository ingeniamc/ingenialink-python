import platform
import re

import pytest


@pytest.fixture
def adapters_module():
    current_platform = platform.system()
    if current_platform == "Windows":
        import ingenialink.get_adapters_addresses as adapters

        return adapters
    pytest.skip(f"Skipping test, only available on Windows, platform={current_platform}")


@pytest.mark.canopen
@pytest.mark.ethercat
def test_get_adapters_addresses(adapters_module, read_config, pytestconfig):
    protocol = pytestconfig.getoption("--protocol")
    protocol_info = read_config[protocol]
    if "ifname" not in protocol_info:
        pytest.skip(
            f"Skipping test because 'ifname' is not in the protocol '{protocol}' information."
        )

    match = re.search(r"\{[^}]*\}", protocol_info["ifname"])
    expected_adapter_address = match.group(0) if match else None
    assert expected_adapter_address is not None

    adapters = adapters_module.get_adapters_addresses(
        adapter_families=adapters_module.AdapterFamily.INET,
        scan_flags=[
            adapters_module.ScanFlags.INCLUDE_PREFIX,
            adapters_module.ScanFlags.INCLUDE_ALL_INTERFACES,
        ],
    )

    expected_adapter_address_found = False
    for adapter in adapters:
        # https://learn.microsoft.com/en-us/windows/win32/api/ifdef/ns-ifdef-net_luid_lh
        if adapter.IfType != 6 or not len(adapter.FirstUnicastAddress):
            continue

        if adapter.AdapterName == expected_adapter_address:
            expected_adapter_address_found = True
            break

    assert expected_adapter_address_found is True
