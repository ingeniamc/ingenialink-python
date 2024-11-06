import platform

import pytest

from ingenialink.canopen.network import CAN_BAUDRATE, CAN_DEVICE, CanopenNetwork
from ingenialink.exceptions import ILError

test_bus = "virtual"
test_baudrate = 1000000
test_channel = 0


@pytest.fixture
def virtual_network():
    net = CanopenNetwork(
        device=CAN_DEVICE(test_bus), channel=test_channel, baudrate=CAN_BAUDRATE(test_baudrate)
    )
    return net


@pytest.mark.no_connection
def test_getters_canopen(virtual_network):
    assert virtual_network.device == test_bus
    assert virtual_network.channel == test_channel
    assert virtual_network.baudrate == test_baudrate
    assert virtual_network.network is None


@pytest.mark.canopen
def test_connect_to_slave(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    assert fw_version is not None and fw_version != ""


@pytest.mark.canopen
def test_connect_to_slave_target_not_in_nodes(read_config):
    protocol_contents = read_config["canopen"]
    net = CanopenNetwork(
        device=CAN_DEVICE(protocol_contents["device"]),
        channel=protocol_contents["channel"],
        baudrate=CAN_BAUDRATE(protocol_contents["baudrate"]),
    )

    with pytest.raises(ILError):
        net.connect_to_slave(target=1234, dictionary=protocol_contents["dictionary"])
    net._teardown_connection()


@pytest.mark.no_connection
def test_connect_to_slave_none_nodes(virtual_network, read_config):
    net = virtual_network
    protocol_contents = read_config["canopen"]
    with pytest.raises(ILError):
        net.connect_to_slave(target=1, dictionary=protocol_contents["dictionary"])


@pytest.mark.canopen
def test_scan_slaves(read_config):
    net = CanopenNetwork(
        device=CAN_DEVICE(read_config["canopen"]["device"]),
        channel=read_config["canopen"]["channel"],
        baudrate=CAN_BAUDRATE(read_config["canopen"]["baudrate"]),
    )
    slaves = net.scan_slaves()
    assert len(slaves) > 0


@pytest.mark.no_connection
@pytest.mark.parametrize("can_device", [CAN_DEVICE.PCAN, CAN_DEVICE.KVASER, CAN_DEVICE.IXXAT])
def test_scan_slaves_missing_drivers(can_device):
    net = CanopenNetwork(
        device=can_device,
        channel=0,
        baudrate=CAN_BAUDRATE.Baudrate_1M,
    )
    with pytest.raises(ILError) as exc_info:
        net.scan_slaves()
    assert (
        str(exc_info.value) == f"The {can_device.value.upper()} transceiver is not detected. "
        f"Make sure that it's connected and"
        " its drivers are installed."
    )


@pytest.mark.canopen
def test_scan_slaves_info(read_config, get_configuration_from_rack_service):
    net = CanopenNetwork(
        device=CAN_DEVICE(read_config["canopen"]["device"]),
        channel=read_config["canopen"]["channel"],
        baudrate=CAN_BAUDRATE(read_config["canopen"]["baudrate"]),
    )
    slaves_info = net.scan_slaves_info()

    drive_idx, config = get_configuration_from_rack_service
    drive = config[drive_idx]

    assert len(slaves_info) > 0
    assert read_config["canopen"]["node_id"] in slaves_info
    assert slaves_info[read_config["canopen"]["node_id"]].product_code == drive.product_code
    assert slaves_info[read_config["canopen"]["node_id"]].revision_number == drive.revision_number


@pytest.mark.canopen
def test_disconnect_from_slave(read_config):
    protocol_contents = read_config["canopen"]
    net = CanopenNetwork(
        device=CAN_DEVICE(protocol_contents["device"]),
        channel=protocol_contents["channel"],
        baudrate=CAN_BAUDRATE(protocol_contents["baudrate"]),
    )

    servo = net.connect_to_slave(
        target=protocol_contents["node_id"],
        dictionary=protocol_contents["dictionary"],
    )

    assert len(net.servos) == 1
    net.disconnect_from_slave(servo)
    assert len(net.servos) == 0


@pytest.mark.no_connection
def test_setup_and_teardown_connection(virtual_network):
    if platform.system() != "Windows":
        pytest.skip("Only for window machines")
    assert virtual_network._connection is None
    virtual_network._setup_connection()
    assert virtual_network._connection is not None
    virtual_network._teardown_connection()
    assert virtual_network._connection is None


@pytest.mark.skip
def test_load_firmware(connect_to_slave, read_config):
    # TODO: Fix load_firmware method to work independently of status listeners
    servo, net = connect_to_slave
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    protocol_contents = read_config["canopen"]

    net.load_firmware(protocol_contents["node_id"], protocol_contents["test_fw_file"])
    new_fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")

    assert new_fw_version != fw_version
    net.disconnect_from_slave(servo)
