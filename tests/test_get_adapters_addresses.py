import platform
import re

import pytest


@pytest.fixture
def adapters_module():
    current_platform = platform.system()
    if current_platform == "Windows":
        import ingenialink.get_adapters_addresses as adapters  # noqa: PLC0415

        return adapters

    raise NotImplementedError(
        "Get adapters addresses is not implemented on this platform. "
        "Do not run these tests under this platform"
    )


@pytest.mark.ethercat
def test_get_adapters_addresses(adapters_module, setup_descriptor):
    ifname_match = re.search(r"\{[^}]*\}", setup_descriptor.ifname)
    expected_adapter_address = ifname_match.group(0) if ifname_match else None
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
