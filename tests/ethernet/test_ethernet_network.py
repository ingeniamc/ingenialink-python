import os
import socket
import subprocess
import time
from ftplib import error_temp
from threading import Thread

import pytest
from ingenialogger import get_logger
from twisted.cred.checkers import (
    AllowAnonymousAccess,
    InMemoryUsernamePasswordDatabaseDontUse,
)
from twisted.cred.portal import Portal
from twisted.internet import reactor
from twisted.protocols.ftp import FTPFactory, FTPRealm

from ingenialink.ethernet.network import EthernetNetwork, NetDevEvt, NetProt, NetState
from ingenialink.exceptions import ILError, ILFirmwareLoadError

logger = get_logger(__name__)


def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        result = sock.connect_ex(("localhost", port))
        return result == 0  # Returns True if port is open, False otherwise


def force_close_port(port):
    # Find the PID of the process using the port
    result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if f":{port}" in line:
            pid = line.split()[-1]
            # Kill the process using the PID
            subprocess.run(["taskkill", "/PID", pid, "/F"])
            logger.warning(f"Forcefully closed port {port} (PID: {pid})")
            return
    logger.warning(f"No process found using port {port}")


class FTPServer(Thread):
    """FTP Server.

    Args:
        folder_path: Path to FTP server files
        new_user: User for FTP server access
        new_password: Password for FTP server access
    """

    def __init__(
        self,
        folder_path: str = "./",
        new_user: str = "user",
        new_password: str = "password",
        port: int = 21,
    ):
        super().__init__()
        self.ftp_port = port
        self.fpt_checker = InMemoryUsernamePasswordDatabaseDontUse()
        self.fpt_checker.addUser(new_user, new_password)
        self.ftp_portal = Portal(
            FTPRealm(folder_path, folder_path), [AllowAnonymousAccess(), self.fpt_checker]
        )
        self.ftp_factory = FTPFactory(self.ftp_portal)
        self.reactor = reactor
        self.__stopped = False
        self.reactor.callFromThread(self._listen)

    def _listen(self) -> None:
        self.reactor.listenTCP(self.ftp_port, self.ftp_factory)

    def run(self) -> None:
        """Run FTP server."""
        self.reactor.run(installSignalHandlers=False)

    def stop(self) -> None:
        """Stop FTP server."""
        if self.__stopped:
            return
        self.__stopped = True
        self.reactor.callFromThread(self.reactor.stop)
        del self.ftp_factory
        del self.ftp_portal
        del self.fpt_checker
        if is_port_open(self.ftp_port):
            logger.warning("Port was left opened! Closing...")
            force_close_port(self.ftp_port)

    def join(self, timeout=None):
        self.stop()
        return super().join(timeout)


@pytest.fixture(scope="module")
def ftp_server_manager():
    # Get configuration
    ftp_user = "user"
    ftp_password = "password"
    # Create FTP server
    server = FTPServer(folder_path="./", new_user=ftp_user, new_password=ftp_password, port=21)
    server.start()
    yield ftp_user, ftp_password
    server.join()
    assert not server.is_alive()


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
def test_scan_slaves_info(read_config, get_drive_configuration_from_rack_service):
    drive_ip = read_config["ethernet"]["ip"]
    subnet = drive_ip + "/24"
    net = EthernetNetwork(subnet)
    slaves_info = net.scan_slaves_info()

    drive = get_drive_configuration_from_rack_service

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
def test_load_firmware_wrong_user_pwd(ftp_server_manager):
    """Testing failed ftp firmware load with fake FTP server."""
    fw_file = "temp_file.lfu"
    with open(fw_file, "w"):
        pass
    ftp_user, ftp_password = ftp_server_manager
    # Wrong user and password
    fake_user = "mamma"
    fake_password = "mia"
    # Create Network
    net = EthernetNetwork()
    with pytest.raises(ILFirmwareLoadError) as excinfo:
        net.load_firmware(
            fw_file,
            target="localhost",
            ftp_user=fake_user,
            ftp_pwd=fake_password,
        )
    assert str(excinfo.value) == "Unable to login the FTP session"
    os.remove(fw_file)


@pytest.mark.no_connection
def test_load_firmware_error_during_loading(mocker, ftp_server_manager):
    """Testing failed ftp firmware load with fake FTP server."""
    fw_file = "temp_file.lfu"
    with open(fw_file, "w"):
        pass
    ftp_user, ftp_password = ftp_server_manager
    net = EthernetNetwork()
    # Mock ftp error for ftp.stobinary call
    mocker.patch(
        "ftplib.FTP.storbinary",
        side_effect=error_temp("Failed to establish connection."),
    )
    with pytest.raises(ILFirmwareLoadError) as excinfo:
        net.load_firmware(fw_file, target="localhost", ftp_user=ftp_user, ftp_pwd=ftp_password)
    assert str(excinfo.value) == "Unable to load the FW file through FTP."
    assert isinstance(excinfo.value.__cause__, error_temp)
    os.remove(fw_file)


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
