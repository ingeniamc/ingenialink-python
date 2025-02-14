import sys

import pytest

from ingenialink.get_adapters_addresses import get_adapters_addresses


@pytest.mark.skipif(
    sys.platform != "win32", reason="Skipping GetAdaptersAddresses, only available on Windows"
)
def test_get_adapters_addresses():
    assert get_adapters_addresses() is False
