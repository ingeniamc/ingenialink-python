import os
import random

import pytest

import tests.resources.ethercat
from ingenialink.enums.register import RegAccess, RegDtype
from ingenialink.exceptions import ILNACKError
from ingenialink.network import NetState
from virtual_drive import resources as virtual_drive_resources
from virtual_drive.core import VirtualDrive


@pytest.mark.no_connection
def test_connect_to_virtual_drive(virtual_drive_custom_dict):
    dictionary = virtual_drive_resources.VIRTUAL_DRIVE_V2_XDF
    _, net, servo = virtual_drive_custom_dict(dictionary)
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    assert fw_version is not None and fw_version != ""


@pytest.mark.no_connection
def test_virtual_drive_disconnection(virtual_drive_custom_dict):
    dictionary = virtual_drive_resources.VIRTUAL_DRIVE_V2_XDF
    _, net, servo = virtual_drive_custom_dict(dictionary)
    net.disconnect_from_slave(servo)
    assert net.get_servo_state(VirtualDrive.IP_ADDRESS) == NetState.DISCONNECTED
    assert len(net.servos) == 0
    assert servo.socket._closed


@pytest.mark.no_connection
def test_connect_virtual_custom_dictionaries(virtual_drive_custom_dict):
    dictionaries = [
        "//azr-srv-ingfs1/pool/distext/products/EVE-XCR/firmware/2.7.0/eve-xcr-c_eth_2.7.0.xdf",
        "//azr-srv-ingfs1/pool/distext/products/CAP-XCR/firmware/2.7.0/cap-xcr-c_eth_2.7.0.xdf",
        "//azr-srv-ingfs1/pool/distext/products/EVE-XCR/firmware/2.7.0/eve-xcr-c_can_2.7.0.xdf",
        "//azr-srv-ingfs1/pool/distext/products/CAP-XCR/firmware/2.7.0/cap-xcr-c_can_2.7.0.xdf",
    ]
    for dictionary in dictionaries:
        if not os.path.exists(dictionary):
            continue
        server, net, servo = virtual_drive_custom_dict(dictionary)
        assert servo is not None and net is not None
        assert len(net.servos) == 1
        fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
        assert fw_version is not None and fw_version != ""

        for reg_key, register in servo.dictionary.registers(1).items():
            if register.access in [RegAccess.RO, RegAccess.RW]:
                value = servo.read(reg_key)
                assert pytest.approx(server.get_value_by_id(1, reg_key), abs=0.02) == value

            if register.access in [RegAccess.WO, RegAccess.RW]:
                if register.enums_count > 0:
                    continue
                value = random.uniform(0, 100)
                if register.dtype != RegDtype.FLOAT:
                    value = int(value)
                servo.write(reg_key, value)
                assert pytest.approx(value) == server.get_value_by_id(1, reg_key)


@pytest.mark.no_connection
def test_connect_to_virtual_drive_old_disturbance(virtual_drive_custom_dict):
    dictionary = tests.resources.ethercat.TEST_DICT_ETHERCAT_OLD_DIST
    _, net, servo = virtual_drive_custom_dict(dictionary)
    assert servo is not None and net is not None
    with pytest.raises(ILNACKError):
        servo.read("MON_DIST_STATUS", subnode=0)
