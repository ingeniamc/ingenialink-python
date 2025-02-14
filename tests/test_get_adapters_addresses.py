import contextlib
import platform

import pytest

# Module will only be available for Windows
with contextlib.suppress(ImportError):
    from ingenialink.get_adapters_addresses import get_adapters_addresses


@pytest.mark.skipif(
    platform.system == "Windows", reason="Skipping GetAdaptersAddresses, only available on Windows"
)
def test_get_adapters_addresses():
    assert get_adapters_addresses() is False
