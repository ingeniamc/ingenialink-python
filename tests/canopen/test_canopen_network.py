import platform

import pytest

from ingenialink.canopen.network import CanBaudrate, CanDevice, CanopenNetwork
from ingenialink.exceptions import ILError

test_bus = "virtual"
test_baudrate = 1000000
test_channel = 0


@pytest.fixture
def virtual_network():
    net = CanopenNetwork(
        device=CanDevice(test_bus), channel=test_channel, baudrate=CanBaudrate(test_baudrate)
    )
    return net


@pytest.mark.no_connection
def test_getters_canopen(virtual_network):
    assert virtual_network.device == test_bus
    assert virtual_network.channel == test_channel
    assert virtual_network.baudrate == test_baudrate
    assert virtual_network.network is None


@pytest.mark.canopen
def test_connect_to_slave(servo, net):
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    assert fw_version is not None and fw_version != ""


@pytest.mark.canopen
def test_connect_to_slave_target_not_in_nodes(setup_descriptor):
    net = CanopenNetwork(
        device=CanDevice(setup_descriptor.device),
        channel=setup_descriptor.channel,
        baudrate=CanBaudrate(setup_descriptor.baudrate),
    )

    with pytest.raises(ILError):
        net.connect_to_slave(target=1234, dictionary=setup_descriptor.dictionary)
    net._teardown_connection()


@pytest.mark.no_connection
def test_connect_to_slave_none_nodes(virtual_network):
    net = virtual_network
    with pytest.raises(ILError):
        net.connect_to_slave(target=1, dictionary="")


@pytest.mark.canopen
def test_scan_slaves(setup_descriptor):
    net = CanopenNetwork(
        device=CanDevice(setup_descriptor.device),
        channel=setup_descriptor.channel,
        baudrate=CanBaudrate(setup_descriptor.baudrate),
    )
    slaves = net.scan_slaves()
    assert len(slaves) > 0


@pytest.mark.no_connection
@pytest.mark.parametrize("can_device", [CanDevice.PCAN, CanDevice.KVASER, CanDevice.IXXAT])
def test_scan_slaves_missing_drivers(can_device):
    net = CanopenNetwork(
        device=can_device,
        channel=0,
        baudrate=CanBaudrate.Baudrate_1M,
    )
    with pytest.raises(ILError) as exc_info:
        net.scan_slaves()
    assert (
        str(exc_info.value) == f"The {can_device.value.upper()} transceiver is not detected. "
        f"Make sure that it's connected and"
        " its drivers are installed."
    )


@pytest.mark.canopen
def test_scan_slaves_info(setup_descriptor, get_drive_configuration_from_rack_service):
    net = CanopenNetwork(
        device=CanDevice(setup_descriptor.device),
        channel=setup_descriptor.channel,
        baudrate=CanBaudrate(setup_descriptor.baudrate),
    )
    slaves_info = net.scan_slaves_info()

    drive = get_drive_configuration_from_rack_service

    assert len(slaves_info) > 0
    assert setup_descriptor.node_id in slaves_info
    assert slaves_info[setup_descriptor.node_id].product_code == drive.product_code
    assert slaves_info[setup_descriptor.node_id].revision_number == drive.revision_number


@pytest.mark.canopen
def test_disconnect_from_slave(setup_descriptor):
    net = CanopenNetwork(
        device=CanDevice(setup_descriptor.device),
        channel=setup_descriptor.channel,
        baudrate=CanBaudrate(setup_descriptor.baudrate),
    )

    servo = net.connect_to_slave(
        target=setup_descriptor.node_id,
        dictionary=setup_descriptor.dictionary,
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
def test_load_firmware(servo, net, setup_descriptor):
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")

    net.load_firmware(setup_descriptor.node_id, setup_descriptor.fw_data.fw_file)
    new_fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")

    assert new_fw_version != fw_version
    net.disconnect_from_slave(servo)
