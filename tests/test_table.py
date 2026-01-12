import csv
from pathlib import Path

import pytest

import tests.resources
from ingenialink import Servo
from ingenialink.configuration_file import ConfigurationFile
from ingenialink.dictionary import DictionaryTable
from ingenialink.exceptions import ILConfigurationError
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

    index_register = servo.dictionary.get_register(uid="MEM_USR_ADDR", axis=None)
    # The index register on this fw version does not have defined range yet
    assert index_register._range == (-32768, 32767)
    index_register._range = (-1, 255)

    # Now get the table from the servo
    table = servo.get_table(uid="MEM_USR", axis=None)

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


@pytest.fixture(
    params=[
        pytest.param(virtual_drive_with_tables.__name__, id="virtual"),
        pytest.param(
            real_servo_with_tables.__name__,
            marks=[
                pytest.mark.fsoe
            ],  # Fsoe is not related to tables, but is a modern firmware that does have user memory
            id="real",
        ),
    ]
)
def servo_with_table(request) -> tuple[Servo, Table]:
    """Parametrized fixture that provides both virtual and real servos with tables.

    This fixture makes each test run as a virtual drive with custom dictionary,
    and as a real servo with injected table definition.
    Each case is run separately in the corresponding Jenkins stage

    Returns:
        Tuple[Servo, Table]: The servo and table from either virtual or real fixture.
    """
    return request.getfixturevalue(request.param)


def test_table_set_and_get_value(servo_with_table):
    """Test that Table.set_value and get_value methods work correctly."""
    _servo, table = servo_with_table

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


def test_table_set_all_values(servo_with_table):
    """Test that Table.set_all_values method works correctly."""
    _servo, table = servo_with_table

    # Write a deterministic value for each address
    for address in table.addresses():
        table.set_value(address, address * 2)

    # Read back and verify each value was set correctly
    for address in table.addresses():
        read_value = table.get_value(address)
        expected_value = address * 2
        assert read_value == expected_value, (
            f"Address {address}: expected {expected_value}, got {read_value}"
        )
def test_table_iteration(servo_with_table):
    """Test that Table supports iteration over all values."""
    _servo, table = servo_with_table

    # Write known values to the table
    test_values = [10, 20, 30, 40, 50]
    for idx, val in enumerate(test_values):
        table.set_value(idx, val)

    # Iterate over the table and verify values
    values_read = []
    for value in table:
        values_read.append(value)
        if len(values_read) >= len(test_values):
            break

    # Verify the first few values match what we wrote
    for i, expected_val in enumerate(test_values):
        assert values_read[i] == expected_val, (
            f"Index {i}: expected {expected_val}, got {values_read[i]}"
        )


def test_table_bulk_write(servo_with_table):
    """Test that Table.write() method works for writing multiple values at once."""
    _servo, table = servo_with_table

    # Test writing a list of values starting from default index (min_index)
    test_values = [10, 20, 30, 40, 50]
    table.write(test_values)

    # Verify the values were written correctly
    for idx, expected_val in enumerate(test_values):
        read_val = table.get_value(idx)
        assert read_val == expected_val, f"Index {idx}: expected {expected_val}, got {read_val}"


def test_table_bulk_write_with_start_index(servo_with_table):
    """Test that Table.write() works with a custom start index."""
    _servo, table = servo_with_table

    # Write values starting at index 5
    start_index = 5
    test_values = [100, 200, 300]
    table.write(test_values, start_index=start_index)

    # Verify the values were written at the correct indices
    for i, expected_val in enumerate(test_values):
        idx = start_index + i
        read_val = table.get_value(idx)
        assert read_val == expected_val, f"Index {idx}: expected {expected_val}, got {read_val}"


def test_table_bulk_read(servo_with_table):
    """Test that Table.read() method works for reading multiple values at once."""
    _servo, table = servo_with_table

    # Write known values
    test_values = [111, 222, 333, 444, 555]
    for idx, val in enumerate(test_values):
        table.set_value(idx, val)

    # Read all values using bulk read
    read_values = table.read(start_index=0, count=len(test_values))

    # Verify
    assert read_values == test_values, f"Expected {test_values}, got {read_values}"


def test_table_bracket_notation(servo_with_table):
    """Test that Table supports bracket notation for reading and writing."""
    _servo, table = servo_with_table

    # Test writing with bracket notation
    table[0] = 123
    table[1] = 456
    table[5] = 789

    # Test reading with bracket notation
    assert table[0] == 123
    assert table[1] == 456
    assert table[5] == 789


def test_table_len(servo_with_table):
    """Test that Table supports len() function."""
    _servo, table = servo_with_table

    # Get the length of the table
    table_len = len(table)

    # Verify it's a positive integer
    assert isinstance(table_len, int)
    assert table_len > 0


def test_table_index_out_of_bounds(servo_with_table):
    """Test that Table raises IndexError for out of bounds access."""
    _servo, table = servo_with_table

    # Try to access an index that's definitely out of bounds
    with pytest.raises(IndexError, match="out of range"):
        _ = table[99999]

    # Try to write to an index that's out of bounds
    with pytest.raises(IndexError, match="out of range"):
        table[99999] = 123


def test_save_and_load_xcf_with_tables(virtual_drive_with_tables, tmp_path):
    """Save configuration to XCF from a virtual servo that has tables.

    This test writes integer values to a table, saves the servo configuration to an XCF file,
    verifies the XCF contains a table entry, changes the table values on the servo,
    then calls `servo.load_configuration` to restore them from the XCF."""
    servo, table = virtual_drive_with_tables

    # Write integer values to two table entries
    val0 = 11223344
    val1 = 55667788
    table.set_value(0, val0)
    table.set_value(1, val1)

    # Save configuration to XCF
    xcf_path = tmp_path / "virt_tables.xcf"
    servo.save_configuration(str(xcf_path))
    assert xcf_path.exists()

    # Load configuration file and verify a table was saved (contents are validated
    # by restoring them into the virtual drive and reading back).
    loaded_conf = ConfigurationFile.load_from_xcf(str(xcf_path))
    tables = [t for t in loaded_conf.tables if t.uid == "MEM_USR"]
    assert len(tables) == 1
    cfg_table = tables[0]
    assert cfg_table.subnode == 0
    assert len(cfg_table.elements) >= 2
    assert cfg_table.elements[0].address == 0

    # Change values on the servo and restore from file
    table.set_value(0, 0)
    table.set_value(1, 0)

    servo.load_configuration(str(xcf_path))

    # Verify integer values were restored
    assert table.get_value(0) == val0
    assert table.get_value(1) == val1


def test_check_configuration_with_tables(virtual_drive_with_tables, tmp_path):
    """Verify `check_configuration` compares table contents and raises on mismatch.

    Steps:
    - Save current configuration (includes tables) to XCF
    - check_configuration should pass
    - Mutate a table entry on the servo
    - check_configuration should raise ILConfigurationError referencing the table address
    - Reload configuration from XCF and check_configuration should pass again
    """
    servo, table = virtual_drive_with_tables

    filename = tmp_path / "table_check.xcf"
    servo.save_configuration(str(filename))

    # Initial check should pass
    servo.check_configuration(str(filename))

    # Mutate table value
    mutated_val = 123456789
    table.set_value(0, mutated_val)
    assert table.get_value(0) == mutated_val

    # Now the servo-level check should detect the mismatch and raise
    with pytest.raises(ILConfigurationError) as ex:
        servo.check_configuration(str(filename))

    assert ex.value.args[0] == (
        "Configuration check failed for the following registers:\n"
        "Table MEM_USR address 0 --- Expected: 0 Found: 123456789\n"
    )

    # Restore configuration and verify check passes again
    servo.load_configuration(str(filename))
    servo.check_configuration(str(filename))


@pytest.mark.ethercat
def test_save_configuration_csv_with_tables(real_servo_with_tables, tmp_path: Path):
    """Save configuration as CSV and verify table index/value sequence is present.

    The CSV configuration generated by `save_configuration_csv` should contain
    pairs of rows for each table element: first the index register row, then
    the corresponding value register row. We write two known values to the
    table (addresses 0 and 1) and assert the exact formatted rows appear in
    the CSV in sequence.
    """
    servo, table = real_servo_with_tables

    # Populate a couple of table entries with simple values so we can hard-code
    # the expected CSV representation explicitly below.
    val0 = 1
    val1 = 2
    table.set_value(0, val0)
    table.set_value(1, val1)
    # Also write a value at a hardcoded max index to ensure boundary handling
    # (hardcoded per request)
    last_index = 255
    val_last = 3
    table.set_value(last_index, val_last)

    filename = tmp_path / "tables.csv"

    # Invoke the CSV save
    servo.save_configuration_csv(str(filename))
    assert filename.exists()

    with filename.open() as f:
        reader = csv.reader(f)
        # Header and CRC lines present
        _header = next(reader)
        _crc_line = next(reader)
        file_data_rows = list(reader)

    # All expected rows hardcoded (index/value pairs for addresses 0, 1 and last index 255)
    # Expected contiguous index/value pairs (hardcoded)
    expected_blocks = [
        (["0x5940", "0x00", "0x0000"], ["0x5941", "0x00", "0x00000001"]),
        (["0x5940", "0x00", "0x0001"], ["0x5941", "0x00", "0x00000002"]),
        (["0x5940", "0x00", "0x00FF"], ["0x5941", "0x00", "0x00000003"]),
    ]

    for idx_row, val_row in expected_blocks:
        for i, file_row in enumerate(file_data_rows):
            if file_row == idx_row:
                # Verify the next row is the corresponding value row
                assert file_data_rows[i + 1] == val_row
                break
        else:
            pytest.fail(f"Index row {idx_row} not found in CSV")
