import platform

import pytest


@pytest.fixture
def adapters_module():
    current_platform = platform.system()
    if current_platform == "Windows":
        import ingenialink.get_adapters_addresses as adapters

        return adapters
    pytest.skip(f"Skipping test, only available on Windows, platform={current_platform}")


def test_get_adapters_addresses(adapters_module):
    addresses = adapters_module.get_adapters_addresses()
    assert not len(addresses)
