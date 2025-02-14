import contextlib
import platform

import pytest

# Module will only be available for Windows
with contextlib.suppress(ImportError):
    pass


@pytest.mark.skipif(
    platform.system != "Windows", reason="Skipping GetAdaptersAddresses, only available on Windows"
)
def test_get_adapters_addresses():
    addresses = []
    assert not len(addresses)
