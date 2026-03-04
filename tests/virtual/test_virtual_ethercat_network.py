import time

from virtual_drive.core import VirtualDrive

import tests.resources.ethercat
from ingenialink.dictionary import Interface
from ingenialink.network import NetState
from ingenialink.servo import ServoState
from ingenialink.virtual.ethercat.network import VirtualEthercatNetwork


def test_connect_to_virtual_drive_ethercat(virtual_drive_ethercat_custom_dict):
    dictionary = tests.resources.ethercat.TEST_DICT_ETHERCAT_OLD_DIST
    _, net, servo = virtual_drive_ethercat_custom_dict(dictionary)
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    assert net.scan_slaves() == [servo.slave_id]


def test_virtual_drive_ethercat_disconnection(virtual_drive_ethercat_custom_dict):
    dictionary = tests.resources.ethercat.TEST_DICT_ETHERCAT_OLD_DIST
    _, net, servo = virtual_drive_ethercat_custom_dict(dictionary)
    net.disconnect_from_slave(servo)
    assert net.get_servo_state(servo.slave_id) == NetState.DISCONNECTED
    assert len(net.servos) == 0
    assert servo.socket._closed


def test_virtual_ethercat_servo_and_network_status_listeners(mocker):
    dictionary = tests.resources.ethercat.TEST_DICT_ETHERCAT_OLD_DIST
    server = VirtualDrive(dictionary_path=dictionary, protocol=Interface.ECAT)
    server.start()
    net = VirtualEthercatNetwork()

    try:
        servo = net.connect_to_slave(
            1,
            dictionary,
            server.port,
            servo_status_listener=True,
            net_status_listener=True,
        )

        servo_events: list[tuple[ServoState, int]] = []
        net_events: list[object] = []
        servo.subscribe_to_status(lambda state, subnode: servo_events.append((state, subnode)))
        net.subscribe_to_status(servo.slave_id, net_events.append)

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
