import json
import pytest
import os
import socket
import time
from threading import Thread

import xml.etree.ElementTree as ET

from ingenialink.canopen.network import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE
from ingenialink.ethernet.network import EthernetNetwork, NET_TRANS_PROT
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.constants import ETH_BUF_SIZE
from ingenialink.utils.mcb import MCB


ALLOW_PROTOCOLS = ["no_connection", "ethernet", "ethercat", "canopen"]


def pytest_addoption(parser):
    parser.addoption("--protocol", action="store", default="no_connection",
                     help=",".join(ALLOW_PROTOCOLS), choices=ALLOW_PROTOCOLS)


@pytest.fixture
def read_config():
    config = 'tests/config.json'
    print('current config file:', config)
    with open(config, "r", encoding='utf-8') as fp:
        contents = json.load(fp)
    return contents


def pytest_collection_modifyitems(config, items):
    protocol = config.getoption("--protocol")
    negate_protocols = [x for x in ALLOW_PROTOCOLS if x != protocol]
    skip_by_protocol = pytest.mark.skip(reason="Protocol does not match")
    for item in items:
        if protocol in item.keywords:
            continue
        for not_protocol in negate_protocols:
            if not_protocol in item.keywords:
                item.add_marker(skip_by_protocol)


def connect_canopen(protocol_contents):
    net = CanopenNetwork(device=CAN_DEVICE(protocol_contents['device']),
                         channel=protocol_contents['channel'],
                         baudrate=CAN_BAUDRATE(protocol_contents['baudrate']))

    servo = net.connect_to_slave(
        target=protocol_contents['node_id'],
        dictionary=protocol_contents['dictionary'],
        eds=protocol_contents['eds'])
    return servo, net


def connect_ethernet(protocol_contents):
    net = EthernetNetwork()

    servo = net.connect_to_slave(
        protocol_contents['ip'],
        protocol_contents['dictionary'],
        protocol_contents['port'])
    return servo, net


def connect_ethercat(protocol_contents):
    net = EthercatNetwork(protocol_contents['ifname'])

    servo = net.connect_to_slave(
        target=protocol_contents['slave'],
        dictionary=protocol_contents['dictionary']
    )
    return servo, net


@pytest.fixture
def connect_to_slave(pytestconfig, read_config):
    servo = None
    net = None
    protocol = pytestconfig.getoption("--protocol")
    protocol_contents = read_config[protocol]
    if protocol == "ethernet":
        servo, net = connect_ethernet(protocol_contents)
    elif protocol == "ethercat":
        servo, net = connect_ethercat(protocol_contents)
    elif protocol == "canopen":
        servo, net = connect_canopen(protocol_contents)

    yield servo, net
    net.disconnect_from_slave(servo)


class VirtualDrive(Thread):
    ACK_CMD = 3

    def __init__(self, ip, port, config_file="./tests/resources/virtual_drive.xcf"):
        super(VirtualDrive, self).__init__()
        self.ip = ip
        self.port = port
        self.config_file = config_file
        self.socket = None
        self.__stop = False
        self.device_info = None
        self.registers = {}
        self._load_configuration_file()

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
                except:
                    self.stop()
                    break
                reg_add, subnode, cmd, data = MCB.read_mcb_frame(frame)
                access = self.registers[subnode][reg_add]["access"]
                if cmd == 2: # Write
                    response = MCB.build_mcb_frame(self.ACK_CMD, subnode, reg_add, data)
                    self.socket.sendto(response, add)
                    if access in ["rw", "w"]: # TODO: send error otherwise
                        self.registers[subnode][reg_add]["value"] = data
                elif cmd == 1: # Read
                    value = self.registers[subnode][reg_add]["value"]
                    response = MCB.build_mcb_frame(self.ACK_CMD, subnode, reg_add, value)
                    self.socket.sendto(response, add)
                    # TODO: send error if the register is WO
            
            time.sleep(0.1)

    def stop(self):
        ''' Stop socket '''
        if self.socket is not None:
            self.socket.close()
        self.__stop = True

    def _load_configuration_file(self):
        if not os.path.isfile(self.config_file):
            raise FileNotFoundError(f'Could not find {self.config_file}.')
        with open(self.config_file, 'r', encoding='utf-8') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()
        device = root.find('Body/Device')
        registers = root.findall('./Body/Device/Registers/Register')
        self.device_info = device
        for element in registers:
            subnode = int(element.attrib['subnode'])
            if subnode not in self.registers:
                self.registers[subnode] = {}
            address = int(element.attrib['address'], base=16)
            if "storage" in element.attrib:
                storage = element.attrib['storage']
            else:
                storage = None
            self.registers[subnode][address] = {
                "access": element.attrib['access'],
                "dtype": element.attrib['dtype'],
                "id": element.attrib['id'],
                "value": storage
            }
