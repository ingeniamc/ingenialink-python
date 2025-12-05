import pytest

import tests.resources
from ingenialink.table import Table


def test_servo_get_table(virtual_drive_custom_dict):
    """Test that Servo.get_table method works correctly."""
    dict_path = tests.resources.DEN_NET_E_WITH_TABLES

    _, _, servo = virtual_drive_custom_dict(dict_path)

    # Test with existing table
    uid = "COGGING_COMP"
    table = servo.get_table(uid=uid, axis=None)
    assert isinstance(table, Table)

    # Test with axis specified
    table_axis1 = servo.get_table(uid=uid, axis=1)
    assert isinstance(table_axis1, Table)

    # Test with non-existent table
    uid = "TEST_UID"
    with pytest.raises(ValueError, match=f"Table {uid} not found."):
        servo.get_table(uid=uid, axis=None)

    # Test with non-existent axis
    with pytest.raises(KeyError, match="axis=3 does not exist."):
        servo.get_table(uid=uid, axis=3)

    # Test with wrong axis for a table
    uid = "COGGING_COMP"
    with pytest.raises(KeyError, match=f"Table {uid} not present in axis=0"):
        servo.get_table(uid=uid, axis=0)

    # Test with table of non-axis
    uid = "MEM_USR"
    table_1 = servo.get_table(uid=uid, axis=None)
    assert isinstance(table_1, Table)
    table_2 = servo.get_table(uid=uid, axis=0)
    assert isinstance(table_2, Table)
