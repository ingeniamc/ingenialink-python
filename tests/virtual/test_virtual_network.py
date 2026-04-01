import os
import random
import time

import pytest
from virtual_drive import resources as virtual_drive_resources
from virtual_drive.core import VirtualDrive

import tests.resources.ethercat
from ingenialink.dictionary import Interface
from ingenialink.enums.register import RegAccess, RegDtype
from ingenialink.exceptions import ILNACKError
from ingenialink.network import NetState
from ingenialink.servo import ServoState
from ingenialink.virtual.ethernet.network import VirtualEthernetNetwork


@pytest.mark.virtual
def test_connect_to_virtual_drive(virtual_drive_custom_dict):
    dictionary = virtual_drive_resources.VIRTUAL_DRIVE_V2_XDF
    _, net, servo = virtual_drive_custom_dict(dictionary, Interface.ETH)
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    assert fw_version is not None and fw_version != ""


@pytest.mark.virtual
def test_virtual_drive_disconnection(virtual_drive_custom_dict):
    dictionary = virtual_drive_resources.VIRTUAL_DRIVE_V2_XDF
    _, net, servo = virtual_drive_custom_dict(dictionary, Interface.ETH)
    net.disconnect_from_slave(servo)
    assert net.get_servo_state(VirtualDrive.IP_ADDRESS) == NetState.DISCONNECTED
    assert len(net.servos) == 0
    assert servo.socket._closed


@pytest.mark.virtual
def test_connect_virtual_custom_dictionaries(virtual_drive_custom_dict):
    dictionaries = [
        (
            "//azr-srv-ingfs1/pool/distext/products/EVE-XCR/firmware/2.7.0/eve-xcr-c_eth_2.7.0.xdf",
            Interface.ETH,
        ),
        (
            "//azr-srv-ingfs1/pool/distext/products/CAP-XCR/firmware/2.7.0/cap-xcr-c_eth_2.7.0.xdf",
            Interface.ETH,
        ),
        (
            "//azr-srv-ingfs1/pool/distext/products/EVE-XCR/firmware/2.7.0/eve-xcr-c_can_2.7.0.xdf",
            Interface.CAN,
        ),
        (
            "//azr-srv-ingfs1/pool/distext/products/CAP-XCR/firmware/2.7.0/cap-xcr-c_can_2.7.0.xdf",
            Interface.CAN,
        ),
    ]
    for dictionary, protocol in dictionaries:
        if not os.path.exists(dictionary):
            continue
        server, net, servo = virtual_drive_custom_dict(dictionary, protocol)
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


@pytest.mark.virtual
def test_connect_to_virtual_drive_old_disturbance(virtual_drive_custom_dict):
    dictionary = tests.resources.ethercat.TEST_DICT_ETHERCAT_OLD_DIST
    _, net, servo = virtual_drive_custom_dict(dictionary, Interface.ETH)
    assert servo is not None and net is not None
    with pytest.raises(ILNACKError):
        servo.read("MON_DIST_STATUS", subnode=0)


@pytest.mark.virtual
def test_virtual_ethernet_servo_and_network_status_listeners(mocker):
    dictionary = virtual_drive_resources.VIRTUAL_DRIVE_V2_XDF
    server = VirtualDrive(dictionary_path=dictionary)
    server.start()
    net = VirtualEthernetNetwork()

    try:
        servo = net.connect_to_slave(
            dictionary,
            server.port,
            servo_status_listener=True,
            net_status_listener=True,
        )

        servo_events = []
        net_events = []
        servo.subscribe_to_status(lambda state, subnode: servo_events.append((state, subnode)))
        net.subscribe_to_status(server.ip, net_events.append)

        state_sequence = iter([ServoState.DISABLED, ServoState.ENABLED, ServoState.ENABLED])

        def mocked_get_state(_subnode=1):
            return next(state_sequence)

        mocker.patch.object(servo, "get_state", side_effect=mocked_get_state)

        timeout = time.time() + 4
        while len(servo_events) < 2 and time.time() < timeout:
            time.sleep(0.1)
        assert len(servo_events) >= 2
        assert servo_events[0][0] == ServoState.DISABLED
        assert servo_events[1][0] == ServoState.ENABLED

        mocker.patch.object(servo, "is_alive", return_value=False)
        timeout = time.time() + 2
        while len(net_events) < 1 and time.time() < timeout:
            time.sleep(0.1)
        assert len(net_events) >= 1

        mocker.patch.object(servo, "is_alive", return_value=True)
        timeout = time.time() + 2
        while len(net_events) < 2 and time.time() < timeout:
            time.sleep(0.1)
        assert len(net_events) >= 2
    finally:
        net.stop_status_listener()
        if net.servos:
            net.disconnect_from_slave(net.servos[0])
        if server.is_alive():
            server.stop()
