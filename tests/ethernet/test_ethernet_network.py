import os
import socket
import time
from threading import Thread

import pytest
from twisted.cred.checkers import (
    AllowAnonymousAccess,
    InMemoryUsernamePasswordDatabaseDontUse,
)
from twisted.cred.portal import Portal
from twisted.internet import reactor
from twisted.protocols.ftp import FTPFactory, FTPRealm

from ingenialink.ethernet.network import EthernetNetwork, NetDevEvt, NetProt, NetState
from ingenialink.exceptions import ILError, ILFirmwareLoadError


class FTPServer(Thread):
    def __init__(
        self, folder_path: str = "./", new_user: str = "user", new_password: str = "password"
    ):
        super().__init__()
        self.fpt_checker = InMemoryUsernamePasswordDatabaseDontUse()
        self.fpt_checker.addUser(new_user, new_password)
        self.ftp_portal = Portal(
            FTPRealm(folder_path, folder_path), [AllowAnonymousAccess(), self.fpt_checker]
        )
        self.ftp_factory = FTPFactory(self.ftp_portal)
        reactor.listenTCP(21, self.ftp_factory)

    def run(self) -> None:
        """Run FTP server."""
        reactor.run()

    def stop(self) -> None:
        """Stop FTP server."""
        reactor.stop()


@pytest.fixture()
def connect(read_config):
    net = EthernetNetwork()
    protocol_contents = read_config["ethernet"]
    servo = net.connect_to_slave(
        protocol_contents["ip"], protocol_contents["dictionary"], protocol_contents["port"]
    )
    return servo, net


@pytest.mark.ethernet
def test_connect_to_slave(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    assert fw_version is not None and fw_version != ""


@pytest.mark.ethernet
def test_can_not_connect_to_salve(read_config):
    net = EthernetNetwork()
    wrong_ip = "34.56.125.234"
    protocol_contents = read_config["ethernet"]
    with pytest.raises(ILError):
        net.connect_to_slave(wrong_ip, protocol_contents["dictionary"], protocol_contents["port"])


@pytest.mark.ethernet
def test_net_invalid_subnet():
    with pytest.raises(ValueError):
        EthernetNetwork("12345")


@pytest.mark.ethernet
def test_scan_slaves_no_subnet():
    net = EthernetNetwork()
    assert len(net.scan_slaves()) == 0


@pytest.mark.ethernet
def test_scan_slaves(read_config):
    drive_ip = read_config["ethernet"]["ip"]
    subnet = drive_ip + "/24"
    net = EthernetNetwork(subnet)
    detected_slaves = net.scan_slaves()
    assert len(detected_slaves) > 0
    assert drive_ip in detected_slaves


@pytest.mark.ethernet
def test_scan_slaves_info(read_config, get_configuration_from_rack_service):
    drive_ip = read_config["ethernet"]["ip"]
    subnet = drive_ip + "/24"
    net = EthernetNetwork(subnet)
    slaves_info = net.scan_slaves_info()

    drive_idx, config = get_configuration_from_rack_service
    drive = config[drive_idx]

    assert len(slaves_info) > 0
    assert drive_ip in slaves_info
    assert slaves_info[drive_ip].product_code == drive.product_code
    assert slaves_info[drive_ip].revision_number == drive.revision_number


@pytest.mark.ethernet
def test_ethernet_connection(connect_to_slave, read_config):
    servo, net = connect_to_slave
    family = servo.socket.family
    ip, port = servo.socket.getpeername()
    assert net.get_servo_state(read_config["ethernet"]["ip"]) == NetState.CONNECTED
    assert net.protocol == NetProt.ETH
    assert family == socket.AF_INET
    assert servo.socket.type == socket.SOCK_DGRAM
    assert ip == read_config["ethernet"]["ip"]
    assert port == read_config["ethernet"]["port"]


@pytest.mark.ethernet
def test_ethernet_disconnection(connect, read_config):
    servo, net = connect
    net.disconnect_from_slave(servo)
    assert net.get_servo_state(read_config["ethernet"]["ip"]) == NetState.DISCONNECTED
    assert len(net.servos) == 0
    assert servo.socket._closed


@pytest.mark.no_connection
def test_load_firmware_file_not_found():
    virtual_net = EthernetNetwork()
    with pytest.raises(FileNotFoundError):
        virtual_net.load_firmware("no_file")


@pytest.mark.no_connection
def test_load_firmware_no_connection():
    fw_file = "temp_file.lfu"
    with open(fw_file, "w"):
        pass
    virtual_net = EthernetNetwork()
    with pytest.raises(ILFirmwareLoadError):
        virtual_net.load_firmware(fw_file, target="127.0.0.1", ftp_user="", ftp_pwd="")
    os.remove(fw_file)


@pytest.mark.no_connection
def test_load_firmware_right_user_pwd():
    """Testing correct ftp firmware load with fake FTP server."""
    fw_file = "temp_file.lfu"
    with open(fw_file, "w"):
        pass
    # User and password
    fake_user = "user1"
    fake_password = "1234"
    fake_folder = os.getcwd()
    # Create FTP server
    server = FTPServer(folder_path=fake_folder, new_user=fake_user, new_password=fake_password)
    server.start()
    # Create Network
    net = EthernetNetwork()
    net.load_firmware(fw_file, target="localhost", ftp_user=fake_user, ftp_pwd=fake_password)
    server.stop()
    server.join()
    os.remove(fw_file)


@pytest.mark.skip
@pytest.mark.no_connection
def test_load_firmware_error_during_loading():
    pass


@pytest.mark.no_connection
def test_net_status_listener(virtual_drive, mocker):
    server, _ = virtual_drive
    net = EthernetNetwork()
    net.connect_to_slave(server.ip, dictionary=server.dictionary_path, port=server.port)

    status_list = []
    net.subscribe_to_status(server.ip, status_list.append)
    net.start_status_listener()

    # Mock a disconnection
    mocker.patch("ingenialink.servo.Servo.is_alive", return_value=False)
    time.sleep(1)

    # Assert that the net status callback is notified of net status change event
    assert len(status_list) == 1
    assert status_list[0] == NetDevEvt.REMOVED

    # Mock a reconnection
    mocker.patch("ingenialink.servo.Servo.is_alive", return_value=True)
    time.sleep(1)
    net.stop_status_listener()

    # Assert that the net status callback is notified of net status change event
    assert len(status_list) == 2
    assert status_list[1] == NetDevEvt.ADDED


@pytest.mark.no_connection
def test_unsubscribe_from_status(virtual_drive, mocker):
    server, _ = virtual_drive
    net = EthernetNetwork()
    net.connect_to_slave(server.ip, dictionary=server.dictionary_path, port=server.port)

    status_list = []
    net.subscribe_to_status(server.ip, status_list.append)
    net.start_status_listener()
    net.unsubscribe_from_status(server.ip, status_list.append)

    # Mock a disconnection
    mocker.patch("ingenialink.servo.Servo.is_alive", return_value=False)
    time.sleep(1)
    net.stop_status_listener()

    # Assert that the net status callback is not notified of net status change event
    assert len(status_list) == 0
