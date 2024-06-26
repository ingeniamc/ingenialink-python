import os
import random

import pytest

from ingenialink.enums.register import REG_ACCESS, REG_DTYPE
from ingenialink.network import NET_STATE
from ingenialink.virtual.network import VirtualNetwork
from virtual_drive.core import VirtualDrive

RESOURCES_FOLDER = "virtual_drive/resources/"
TEST_PORT = 82

server = VirtualDrive(TEST_PORT)


@pytest.fixture(autouse=True, scope="function")
def stop_virtual_drive():
    yield
    server.stop()


@pytest.fixture
def connect_virtual_drive():
    def connect(dictionary):
        global server
        server.stop()
        server = VirtualDrive(TEST_PORT, dictionary)
        server.start()
        net = VirtualNetwork()
        servo = net.connect_to_slave(dictionary, TEST_PORT)
        return servo, net

    return connect


@pytest.mark.no_connection
def test_connect_to_virtual_drive(connect_virtual_drive):
    dictionary = os.path.join(RESOURCES_FOLDER, "virtual_drive.xdf")
    connect = connect_virtual_drive
    servo, net = connect(dictionary)
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    assert fw_version is not None and fw_version != ""


@pytest.mark.no_connection
def test_virtual_drive_disconnection(connect_virtual_drive):
    dictionary = os.path.join(RESOURCES_FOLDER, "virtual_drive.xdf")
    servo, net = connect_virtual_drive(dictionary)
    net.disconnect_from_slave(servo)
    assert net._get_servo_state(VirtualDrive.IP_ADDRESS) == NET_STATE.DISCONNECTED
    assert len(net.servos) == 0
    assert servo.socket._closed


@pytest.mark.no_connection
def test_connect_virtual_custom_dictionaries(connect_virtual_drive, read_config):
    config = read_config
    for protocol in ["ethernet", "canopen"]:
        dictionary = config[protocol]["dictionary"]
        if not os.path.exists(dictionary):
            continue
        servo, net = connect_virtual_drive(dictionary)
        assert servo is not None and net is not None
        assert len(net.servos) == 1
        fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
        assert fw_version is not None and fw_version != ""

        for reg_key, register in servo.dictionary.registers(1).items():
            if register.access in [REG_ACCESS.RO, REG_ACCESS.RW]:
                value = servo.read(reg_key)
                assert pytest.approx(server.get_value_by_id(1, reg_key), abs=0.02) == value

            if register.access in [REG_ACCESS.WO, REG_ACCESS.RW]:
                if register.enums_count > 0:
                    continue
                value = random.uniform(0, 100)
                if register.dtype != REG_DTYPE.FLOAT:
                    value = int(value)
                servo.write(reg_key, value)
                assert pytest.approx(value) == server.get_value_by_id(1, reg_key)
