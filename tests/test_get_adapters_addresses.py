import contextlib
import platform

import pytest

# Module will only be available for Windows
with contextlib.suppress(ImportError):
    from ingenialink.get_adapters_addresses import get_adapters_addresses


@pytest.mark.skipif(
    platform.system() != "Windows",
    reason=f"Skipping test, only available on Windows, platform={platform.system()}",
)
def test_get_adapters_addresses():
    addresses = get_adapters_addresses()
    assert not len(addresses)
