import pytest

import tests.resources
from ingenialink import Servo
from ingenialink.dictionary import DictionaryTable
from ingenialink.table import Table


@pytest.fixture
def virtual_drive_with_tables(virtual_drive_custom_dict) -> tuple[Servo, Table]:
    """Fixture that provides a virtual servo with user memory table.

    Returns:
        Tuple[Servo, Table]: The virtual servo and the user memory table.
    """
    dict_path = tests.resources.DEN_NET_E_WITH_TABLES
    _, _, servo = virtual_drive_custom_dict(dict_path)
    table = servo.get_table(uid="MEM_USR", axis=0)
    return servo, table


@pytest.fixture
def real_servo_with_tables(servo) -> tuple[Servo, Table]:
    """Fixture that provides a real servo with user memory table.

    Real servos have table functionality in hardware, but their XDF dictionaries
    don't define the tables. This fixture injects the table definition.

    Raises:
        AssertionError: If the MEM_USR table is already defined in the XDF.

    Returns:
        Tuple[Servo, Table]: The real servo and the user memory table.
    """
    # Assert that the table is not already defined in the XDF
    # When XDFs are updated to include tables, this assertion will fail
    # and we can remove this injection logic
    try:
        servo.get_table(uid="MEM_USR", axis=0)
        raise AssertionError(
            "MEM_USR table is now defined in the XDF dictionary! "
            "Please remove the table injection logic from this fixture."
        )
    except (ValueError, KeyError):
        # Expected: table not found in dictionary
        pass

    # Inject the MEM_USR table definition into the servo's dictionary
    # The table uses MEM_USR_ADDR as index register and MEM_USR_DATA as value register
    mem_usr_table = DictionaryTable(
        id="MEM_USR",
        axis=None,  # Non-axis specific
        id_index="MEM_USR_ADDR",
        id_value="MEM_USR_DATA",
    )

    # Add the table to axis 0 in the dictionary
    if 0 not in servo.dictionary._tables:
        servo.dictionary._tables[0] = {}
    servo.dictionary._tables[0]["MEM_USR"] = mem_usr_table

    # Now get the table from the servo
    table = servo.get_table(uid="MEM_USR", axis=0)
    return servo, table


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


@pytest.mark.parametrize(
    "table_fixture",
    [
        pytest.param(virtual_drive_with_tables.__name__, id="virtual"),
        pytest.param(
            real_servo_with_tables.__name__,
            marks=[pytest.mark.canopen, pytest.mark.ethernet, pytest.mark.ethercat],
            id="real",
        ),
    ],
)
def test_table_set_and_get_value(table_fixture, request):
    """Test that Table.set_value and get_value methods work correctly."""
    _servo, table = request.getfixturevalue(table_fixture)

    # Test writing and reading a value
    index = 0
    value = 12345
    table.set_value(index, value)
    read_value = table.get_value(index)
    assert read_value == value

    # Test writing and reading at different indices
    test_data = {
        0: 100,
        1: 200,
        5: 500,
        10: 1000,
    }

    for idx, val in test_data.items():
        table.set_value(idx, val)

    for idx, val in test_data.items():
        read_val = table.get_value(idx)
        assert read_val == val, f"Expected {val} at index {idx}, got {read_val}"
