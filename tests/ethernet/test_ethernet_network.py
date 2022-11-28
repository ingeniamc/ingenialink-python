import socket
import time
from threading import Thread

import pytest

from ingenialink.ethernet.network import EthernetNetwork, NET_TRANS_PROT, \
    NET_PROT, NET_STATE, NET_DEV_EVT, NetStatusListener
from ingenialink.constants import ETH_BUF_SIZE
from ingenialink.utils.mcb import MCB
from ingenialink.exceptions import ILFirmwareLoadError


test_ip = "localhost"
test_port = 81

class VirtualDrive(Thread):
    def __init__(self, ip, port):
        super(VirtualDrive, self).__init__()
        self.ip = ip
        self.port = port
        self.socket = None
        self.__stop = False

    def run(self):
        ''' Open socket and listen messages '''
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_address = (self.ip, self.port)
        self.socket.bind(server_address)
        self.socket.settimeout(2)
        while not self.__stop:
            if self.socket is not None:
                try:
                    frame, add = self.socket.recvfrom(ETH_BUF_SIZE)
                    recv_add, subnode, cmd, data = self._read_frame(frame)
                    if cmd == 2: # Write
                        ack_cmd = 3
                        response = MCB.build_mcb_frame(ack_cmd, subnode, recv_add, data)
                        # TODO: write to local registers
                        self.socket.sendto(response, add)
                    elif cmd == 3: # Read
                        pass # TODO: read from local registers
                except:
                    self.stop()
            
            time.sleep(0.1)

    def stop(self):
        ''' Stop socket '''
        if self.socket is not None:
            self.socket.close()
        self.__stop = True

    def _read_frame(self, frame):
        '''Read address, subnode and data from the MCB frame'''
        header = frame[MCB.MCB_HEADER_L_SIZE:MCB.MCB_HEADER_SIZE]
        recv_add = (int.from_bytes(header, 'little')) >> 4
        subnode = (int.from_bytes(header, 'little')) >> 12
        
        header_l = frame[MCB.MCB_HEADER_L_SIZE]
        cmd = (header_l & 0xE) >> 1
        subnode = int.from_bytes(frame[:MCB.MCB_HEADER_L_SIZE], 'little') & 0xF
        extended = header_l & 1
        if extended:
            data_start_byte = MCB.EXTENDED_DATA_START_BYTE
            data_end_byte = MCB.EXTENDED_DATA_END_BYTE
        else:
            data_start_byte = MCB.DATA_START_BYTE
            data_end_byte = MCB.DATA_END_BYTE
        data = frame[data_start_byte:data_end_byte]   
        
        return recv_add, subnode, cmd, data


@pytest.fixture()
def virtual_drive():
    server = VirtualDrive(test_ip, test_port)
    server.start()
    yield server
    server.stop()


@pytest.fixture()
def connect(read_config):
    net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    servo = net.connect_to_slave(
        protocol_contents['ip'],
        protocol_contents['dictionary'],
        protocol_contents['port']
    )
    return servo, net


@pytest.mark.ethernet
def test_connect_to_slave(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    fw_version = servo.read('DRV_ID_SOFTWARE_VERSION')
    assert fw_version is not None and fw_version != ''


@pytest.mark.ethernet
def test_scan_slaves(read_config):
    # TODO: Not implemented
    # net = EthernetNetwork()
    # slaves = net.scan_slaves()
    # assert len(slaves) > 0
    pass


@pytest.mark.ethernet
def test_ethernet_connection(connect_to_slave, read_config):
    servo, net = connect_to_slave
    family = net.socket.family
    config_protocol = NET_TRANS_PROT[read_config['ethernet']['protocol']]
    ip, port = net.socket.getpeername()
    socket_protocol = {
        socket.SOCK_DGRAM: NET_TRANS_PROT.UDP,
        socket.SOCK_STREAM: NET_TRANS_PROT.TCP
    }
    assert net.status == NET_STATE.CONNECTED
    assert net.protocol == NET_PROT.ETH
    assert family == socket.AF_INET
    assert config_protocol == socket_protocol[net.socket.type]
    assert ip == read_config['ethernet']['ip']
    assert port == read_config['ethernet']['port']


@pytest.mark.ethernet
def test_ethernet_disconnection(connect):
    servo, net = connect
    net.disconnect_from_slave(servo)
    assert net.status == NET_STATE.DISCONNECTED
    assert len(net.servos) == 0
    assert net.socket._closed


@pytest.mark.no_connection
def test_connect_to_virtual(virtual_drive, read_config):
    server = virtual_drive
    time.sleep(1)
    net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    servo = net.connect_to_slave(
        test_ip,
        protocol_contents['dictionary'],
        test_port
    )
    servo.write('CL_AUX_FBK_SENSOR', 4)
    servo.write('DRV_DIAG_ERROR_LAST_COM', 4, 0)


@pytest.mark.ethernet
@pytest.mark.parametrize(
    "reg, value, subnode", 
    [
        ("CL_AUX_FBK_SENSOR", 4, 1),
        ("DRV_DIAG_ERROR_LAST_COM", 4, 0)
    ]
)
def test_virtual_drive_write(connect_to_slave, virtual_drive, read_config, reg, value, subnode):
    servo, net = connect_to_slave
    server = virtual_drive

    virtual_net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    virtual_servo = virtual_net.connect_to_slave(
        test_ip,
        protocol_contents['dictionary'],
        test_port
    )
    
    virtual_response = virtual_servo.write(reg, value, subnode)
    response = servo.write(reg, value, subnode)

    assert response == virtual_response


@pytest.mark.no_connection
def test_load_firmware_file_not_found():
    # target="192.168.2.22", ftp_user="", ftp_pwd=""
    virtual_net = EthernetNetwork()
    with pytest.raises(FileNotFoundError):
        virtual_net.load_firmware("no_file")


@pytest.mark.no_connection
def test_load_firmware_no_connection(read_config):
    protocol_contents = read_config['ethernet']
    virtual_net = EthernetNetwork()
    with pytest.raises(ILFirmwareLoadError):
        virtual_net.load_firmware(protocol_contents["fw_file"], target=test_ip, ftp_user="", ftp_pwd="")


@pytest.mark.skip
@pytest.mark.no_connection
def test_load_firmware_wrong_user_pwd():
    # TODO: implement
    pass

@pytest.mark.skip
@pytest.mark.no_connection
def test_load_firmware_error_during_loading():
    # TODO: implement
    pass


@pytest.mark.no_connection
def test_net_status_listener_connection(virtual_drive, read_config):
    server = virtual_drive
    net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    status_list = []
    net.subscribe_to_status(status_list.append)
    status_listener = NetStatusListener(net)

    assert len(status_list) == 0

    servo = net.connect_to_slave(
        test_ip,
        protocol_contents['dictionary'],
        test_port
    )

    # Emulate a disconnection. TODO: disconnect from the virtual drive
    status_listener._NetStatusListener__state = NET_STATE.DISCONNECTED
    status_listener.start()
    time.sleep(2)
    status_listener.stop()

    assert len(status_list) == 1
    assert status_list[0] == NET_DEV_EVT.ADDED

    
@pytest.mark.skip
@pytest.mark.no_connection
def test_net_status_listener_disconnection():
    # TODO: implement
    pass


@pytest.mark.no_connection
def test_unsubscribe_from_status(virtual_drive, read_config):
    server = virtual_drive
    net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    status_list = []
    net.subscribe_to_status(status_list.append)
    net.unsubscribe_from_status(status_list.append)

    status_listener = NetStatusListener(net)

    assert len(status_list) == 0

    servo = net.connect_to_slave(
        test_ip,
        protocol_contents['dictionary'],
        test_port
    )

    # Force disconnection. TODO: disconnect from the virtual drive
    status_listener._NetStatusListener__state = NET_STATE.DISCONNECTED
    status_listener.start()
    time.sleep(2)
    status_listener.stop()

    assert len(status_list) == 0
