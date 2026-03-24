import time

from virtual_drive.core import VirtualDrive
from virtual_drive.resources import VIRTUAL_DRIVE_CAN_V2_XDF

from ingenialink.dictionary import Interface
from ingenialink.network import NetState
from ingenialink.servo import ServoState
from ingenialink.virtual.canopen.network import VirtualCanopenNetwork


def test_connect_to_virtual_drive_canopen(virtual_drive_canopen):
    _, net, servo = virtual_drive_canopen
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    assert net.scan_slaves() == [servo.target]


def test_virtual_drive_canopen_disconnection(virtual_drive_canopen):
    _, net, servo = virtual_drive_canopen
    net.disconnect_from_slave(servo)
    assert net.get_servo_state(servo.target) == NetState.DISCONNECTED
    assert len(net.servos) == 0
    assert servo.socket._closed


def test_virtual_canopen_servo_and_network_status_listeners(mocker):
    server = VirtualDrive(dictionary_path=VIRTUAL_DRIVE_CAN_V2_XDF, protocol=Interface.CAN)
    server.start()
    net = VirtualCanopenNetwork()

    try:
        servo = net.connect_to_slave(
            1,
            VIRTUAL_DRIVE_CAN_V2_XDF,
            server.port,
            servo_status_listener=True,
            net_status_listener=True,
        )

        servo_events: list[tuple[ServoState, int]] = []
        net_events: list[object] = []
        servo.subscribe_to_status(lambda state, subnode: servo_events.append((state, subnode)))
        net.subscribe_to_status(servo.target, net_events.append)

        state_sequence = iter([ServoState.DISABLED, ServoState.ENABLED, ServoState.ENABLED])

        def mocked_get_state(_subnode=1):
            return next(state_sequence)

        mocker.patch.object(servo, "get_state", side_effect=mocked_get_state)

        # Wait until the servo listener has reported the first disabled
        # and subsequent enabled events.
        timeout = time.time() + 4
        while len(servo_events) < 2 and time.time() < timeout:
            time.sleep(0.1)
        assert len(servo_events) >= 2
        assert servo_events[0][0] == ServoState.DISABLED
        assert servo_events[1][0] == ServoState.ENABLED

        # Force the servo to appear offline so the network listener emits a disconnection event.
        mocker.patch.object(servo, "is_alive", return_value=False)
        timeout = time.time() + 2
        while len(net_events) < 1 and time.time() < timeout:
            time.sleep(0.1)
        assert len(net_events) >= 1

        # Bring the servo back and wait for the next network status update.
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
