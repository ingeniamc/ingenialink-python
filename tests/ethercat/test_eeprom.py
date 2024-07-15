import pytest


@pytest.mark.ethercat
def test_eeprom_read(connect_to_slave):
    servo, _ = connect_to_slave
    product_code_bytes = servo.read("DRV_ID_PRODUCT_CODE").to_bytes(4, "little")
    product_code_address = 10
    for length in range(1, 5):
        assert product_code_bytes[:length] == servo._read_esc_eeprom(
            product_code_address, length=length
        )


@pytest.mark.ethercat
def test_eeprom_read_wrong_size(connect_to_slave):
    servo, _ = connect_to_slave
    product_code_address = 10
    with pytest.raises(ValueError):
        servo._read_esc_eeprom(product_code_address, length=0)


@pytest.mark.ethercat
def test_eeprom_write(connect_to_slave):
    servo, _ = connect_to_slave
    serial_number_address = 14
    serial_number = int.from_bytes(servo._read_esc_eeprom(serial_number_address), "little")
    new_serial_number = serial_number + 1
    new_serial_number_bytes = new_serial_number.to_bytes(4, "little")
    servo._write_esc_eeprom(serial_number_address, new_serial_number_bytes)
    assert new_serial_number == int.from_bytes(
        servo._read_esc_eeprom(serial_number_address), "little"
    )
    servo._write_esc_eeprom(serial_number_address, serial_number.to_bytes(4, "little"))


@pytest.mark.ethercat
def test_eeprom_wrong_size(connect_to_slave):
    servo, _ = connect_to_slave
    serial_number_address = 14
    with pytest.raises(ValueError):
        servo._write_esc_eeprom(serial_number_address, int(0).to_bytes(3, "little"))
