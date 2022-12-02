import os
import socket
import time
from threading import Thread

import xml.etree.ElementTree as ET

from ingenialink.constants import ETH_BUF_SIZE
from ingenialink.utils.mcb import MCB


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
