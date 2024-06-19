import pytest


@pytest.mark.ethercat
def test_eeprom_read(connect_to_slave):
    servo, _ = connect_to_slave
    product_code_address = 10
    assert servo.read_eeprom(product_code_address, length=4) == servo.read(
        "DRV_ID_PRODUCT_CODE"
    ).to_bytes(4, "little")


@pytest.mark.ethercat
def test_eeprom_write(connect_to_slave):
    servo, _ = connect_to_slave
    serial_number_address = 14
    serial_number = int.from_bytes(servo.read_eeprom(serial_number_address), "little")
    new_serial_number = serial_number + 1
    new_serial_number_bytes = new_serial_number.to_bytes(4, "little")
    servo.write_eeprom(serial_number_address, new_serial_number_bytes)
    assert new_serial_number == int.from_bytes(servo.read_eeprom(serial_number_address), "little")
    servo.write_eeprom(serial_number_address, serial_number.to_bytes(4, "little"))
