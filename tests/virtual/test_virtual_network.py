import os
import random

import pytest

from ingenialink.enums.register import REG_ACCESS, REG_DTYPE
from ingenialink.network import NET_STATE
from virtual_drive.core import VirtualDrive

RESOURCES_FOLDER = "virtual_drive/resources/"
TESTS_RESOURCES_FOLDER = "tests/resources/"


@pytest.mark.no_connection
def test_connect_to_virtual_drive(virtual_drive_custom_dict):
    dictionary = os.path.join(RESOURCES_FOLDER, "virtual_drive.xdf")
    server, net, servo = virtual_drive_custom_dict(dictionary)
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    assert fw_version is not None and fw_version != ""


@pytest.mark.no_connection
def test_virtual_drive_disconnection(virtual_drive_custom_dict):
    dictionary = os.path.join(RESOURCES_FOLDER, "virtual_drive.xdf")
    server, net, servo = virtual_drive_custom_dict(dictionary)
    net.disconnect_from_slave(servo)
    assert net.get_servo_state(VirtualDrive.IP_ADDRESS) == NET_STATE.DISCONNECTED
    assert len(net.servos) == 0
    assert servo.socket._closed


@pytest.mark.no_connection
def test_connect_virtual_custom_dictionaries(virtual_drive_custom_dict, read_config):
    config = read_config
    for protocol in ["ethernet", "canopen"]:
        dictionary = config[protocol]["dictionary"]
        if not os.path.exists(dictionary):
            continue
        server, net, servo = virtual_drive_custom_dict(dictionary)
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


@pytest.mark.no_connection
def test_connect_to_virtual_drive_old_disturbance(virtual_drive_custom_dict):
    dictionary = os.path.join(TESTS_RESOURCES_FOLDER, "ethercat/test_dict_ethercat_old_dist.xdf")
    server, net, servo = virtual_drive_custom_dict(dictionary)
    assert servo is not None and net is not None
    assert server._monitoring is None and server._disturbance is None
