from collections.abc import Callable
from pathlib import Path
from typing import Optional

import pytest
from summit_testing_framework.setups.specifiers import DictionaryType, DictionaryVersion

from ingenialink.dictionary import Interface


@pytest.fixture(scope="session")
def den_net_e_2_8_0_xdf_v3(
    product_dictionary: Callable[[str, DictionaryVersion, Optional[Interface]], Path],
) -> Path:
    return product_dictionary(
        "DEN-NET-E",
        DictionaryVersion("2.9.1", DictionaryType.XDF_V3),
    )
