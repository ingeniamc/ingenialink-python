import contextlib
import sys

import pytest

# Module will only be available for Windows
with contextlib.suppress(ImportError):
    from ingenialink.get_adapters_addresses import get_adapters_addresses


@pytest.mark.skipif(
    sys.platform != "win32", reason="Skipping GetAdaptersAddresses, only available on Windows"
)
def test_get_adapters_addresses():
    assert get_adapters_addresses() is False
