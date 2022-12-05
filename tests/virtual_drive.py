import os
import socket
import time
from enum import Enum
from threading import Thread
import xml.etree.ElementTree as ET

from ingenialink.constants import ETH_BUF_SIZE
from ingenialink.utils.mcb import MCB

class MSG_TYPE(Enum):
    RECEIVED = "RECEIVED"
    SENT = "SENT"


class VirtualDrive(Thread):
    ACK_CMD = 3
    WRITE_CMD = 2
    READ_CMD = 1

    def __init__(self, ip, port, config_file="./tests/resources/virtual_drive.xcf"):
        super(VirtualDrive, self).__init__()
        self.ip = ip
        self.port = port
        self.config_file = config_file
        self.socket = None
        self.__stop = False
        self.device_info = None
        self.registers = {}
        self.__logger = []
        self._load_configuration_file()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def run(self):
        """ Open socket and listen messages """
        server_address = (self.ip, self.port)
        self.socket.bind(server_address)
        self.socket.settimeout(2)
        while not self.__stop:
            try:
                frame, add = self.socket.recvfrom(ETH_BUF_SIZE)
            except:
                self.stop()
                break
            reg_add, subnode, cmd, data = MCB.read_mcb_frame(frame)
            self.__log(add, frame, MSG_TYPE.RECEIVED)
            access = self.registers[subnode][reg_add]["access"]
            if cmd == self.WRITE_CMD:
                sent_cmd = self.ACK_CMD
                response = MCB.build_mcb_frame(sent_cmd, subnode, reg_add, data)
                if access in ["rw", "w"]: # TODO: send error otherwise
                    self.registers[subnode][reg_add]["value"] = data
            elif cmd == self.READ_CMD:
                value = self.registers[subnode][reg_add]["value"]
                sent_cmd = self.ACK_CMD
                response = MCB.build_mcb_frame(sent_cmd, subnode, reg_add, value)
                # TODO: send error if the register is WO
            else:
                continue
            self.__send(response, add)
            
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

    def __send(self, response, address):
        self.socket.sendto(response, address)
        self.__log(address, response, MSG_TYPE.SENT)        

    def __log(self, ip_port, message, msg_type):
        self.__logger.append(
            {
                "timestamp": time.time(),
                "ip_port": ip_port,
                "type": msg_type.value,
                "message": message
            }
        )

    @property
    def log(self):
        return self.__logger

    def clean_log(self):
        self.__logger = []

    