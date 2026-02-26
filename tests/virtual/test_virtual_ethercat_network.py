import tests.resources.ethercat
from ingenialink.network import NetState


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
