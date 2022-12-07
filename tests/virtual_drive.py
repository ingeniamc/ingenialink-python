import os
import socket
import time
from enum import Enum
from threading import Thread

import xml.etree.ElementTree as ET

from ingenialink.constants import ETH_BUF_SIZE, MONITORING_BUFFER_SIZE
from ingenialink.utils.mcb import MCB
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes
from ingenialink.dictionary import Dictionary
from ingenialink.ethernet.servo import EthernetServo
from ingenialink.enums.register import REG_DTYPE


class MSG_TYPE(Enum):
    RECEIVED = "RECEIVED"
    SENT = "SENT"


class VirtualMonitoring():
    FREQUENCY = 20000

    def __init__(self, drive):
        super(VirtualMonitoring, self).__init__()
        self.drive = drive
        self.__enabled = False
        self.__channels = {}
        self.start_time = None

    def enable(self):
        self.bytes_per_block = 0
        for channel in range(self.number_mapped_registers):
            subnode, address, dtype, size = self.get_mapped_register(channel)
            self.__channels[channel] = {
                "data": [],
                "dtype": REG_DTYPE(dtype),
                "address": address,
                "subnode": subnode,
                "size": size,
                "signal": []
            }
            self.bytes_per_block += size

        self.__create_signals()
        self.__enabled = True

    def disable(self):
        if self.__enabled is False or self.start_time is None:
            return
        sampling_rate = self.FREQUENCY / self.divider
        elapsed_time = time.time() - self.start_time
        elapsed_samples = int(elapsed_time * sampling_rate)
        n_samples = min(elapsed_samples, self.buffer_size)
        for channel in range(self.number_mapped_registers):
            self.__channels[channel]["data"] = self.__channels[channel]["signal"][:n_samples]
        self.__enabled = False
        self.available_bytes = n_samples * self.bytes_per_block
        self._store_data_bytes()
        self.start_time = None

    def trigger(self):
        if self.__enabled:
            self.start_time = time.time()

    def remove_data(self):
        for channel in range(self.number_mapped_registers):
            self.__channels[channel]["data"] = []
            self.drive.set_value_by_id(0, "MON_DATA", 0)

    def __create_signals(self):
        for channel in range(self.number_mapped_registers):
            start_value = self.__channels[channel]["address"] + self.__channels[channel]["subnode"]
            signal = [start_value + i for i in range(0, self.buffer_size*self.divider, self.divider)]
            self.__channels[channel]["signal"] = signal

    def _store_data_bytes(self):
        bytes = bytearray()
        n_samples = len(self.__channels[0]["data"])
        for sample in range(n_samples):
            for channel in range(self.number_mapped_registers):
                value = self.__channels[channel]["data"][sample]
                size = self.__channels[channel]["size"]
                sample_bytes = convert_dtype_to_bytes(value, self.__channels[channel]["dtype"])
                if len(sample_bytes) < size:
                    sample_bytes += (b"0")*(size - len(sample_bytes))
                bytes += sample_bytes
        self.drive.set_value_by_id(0, "MON_DATA", bytes)

    @property
    def divider(self):
        """ Frequency divider """
        return self.drive.get_value_by_id(0, "MON_DIST_FREQ_DIV")

    @property
    def trigger_type(self):
        """ Trigger type
            0: Auto, 1: Force, 2: Rising or Failing        
        """
        return self.drive.get_value_by_id(0, "MON_CFG_SOC_TYPE")

    @property
    def buffer_size(self):
        """ Monitoring buffer size """
        return self.drive.get_value_by_id(0, "MON_CFG_WINDOW_SAMP")

    @property
    def available_bytes(self):
        """ Actual number of monitoring bytes """
        return self.drive.get_value_by_id(0, "MON_CFG_BYTES_VALUE")

    @available_bytes.setter
    def available_bytes(self, n_bytes):
        self.drive.set_value_by_id(0, "MON_CFG_BYTES_VALUE", n_bytes)

    @property
    def bytes_per_block(self):
        """ Monitoring bytes per sample """
        return self.drive.get_value_by_id(0, "MON_CFG_BYTES_PER_BLOCK")

    @bytes_per_block.setter
    def bytes_per_block(self, n_bytes):
        self.drive.set_value_by_id(0, "MON_CFG_BYTES_PER_BLOCK", n_bytes)

    @property
    def number_mapped_registers(self):
        return self.drive.get_value_by_id(0, "MON_CFG_TOTAL_MAP")

    def get_mapped_register(self, channel):
        register_id = f'MON_CFG_REG{channel}_MAP'
        data = self.drive.get_value_by_id(0, register_id)
        data_h = data >> 16
        data_l = data & 0x0000FFFF
        subnode = data_h >> 12
        address = data_h & 0x0FFF
        dtype = data_l >> 8
        size = data_l & 0x00FF
        return subnode, address, dtype, size


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
        self.__reg_id_to_address = {}
        self._load_configuration_file()
        self._add_custom_registers()
        self.__monitoring = VirtualMonitoring(self)

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
                self.__log(add, frame, MSG_TYPE.RECEIVED)
                access = self.registers[subnode][reg_add]["access"]
                dtype = self.registers[subnode][reg_add]["dtype"]
                if cmd == self.WRITE_CMD:
                    sent_cmd = self.ACK_CMD
                    response = MCB.build_mcb_frame(sent_cmd, subnode, reg_add, data)
                    if access in ["rw", "w"]: # TODO: send error otherwise
                        value = convert_bytes_to_dtype(data, dtype)
                        self.registers[subnode][reg_add]["value"] = value
                        self.__decode_msg(reg_add, subnode, data)
                elif cmd == self.READ_CMD:
                    value = self.registers[subnode][reg_add]["value"]
                    data = convert_dtype_to_bytes(value, dtype)
                    sent_cmd = self.ACK_CMD
                    if reg_add == self.id_to_address(0, "MON_DATA"):
                        response = self._response_monitoring_data(data)
                    else:
                        response = MCB.build_mcb_frame(sent_cmd, subnode, reg_add, data)
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
        self.__monitoring.disable()

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
                self.__reg_id_to_address[subnode] = {}
            address = int(element.attrib['address'], base=16)
            if "storage" in element.attrib:
                storage = element.attrib['storage']
                if element.attrib['dtype'] == "str":
                    storage = storage
                elif element.attrib['dtype'] == "float":
                    storage = float(storage)
                else:
                    storage = int(storage)
            else:
                storage = None
            self.registers[subnode][address] = {
                "access": element.attrib['access'],
                "dtype": Dictionary.dtype_xdf_options[element.attrib['dtype']],
                "id": element.attrib['id'],
                "value": storage
            }
            self.__reg_id_to_address[subnode][element.attrib['id']] = address

    def _add_custom_registers(self):
        reg = EthernetServo.MONITORING_DATA
        id = "MON_DATA"
        self.registers[reg.subnode][reg.address] = {
            "access": reg.access,
            "dtype": REG_DTYPE.DOMAIN,
            "id": id,
            "value": None
        }
        self.__reg_id_to_address[reg.subnode][id] = reg.address
                    
    def __send(self, response, address):
        self.socket.sendto(response, address)
        self.__log(address, response, MSG_TYPE.SENT)     

    def _response_monitoring_data(self, data):
        sent_cmd = self.ACK_CMD
        reg_add = self.id_to_address(0, "MON_DATA")
        limit = min(len(data), MONITORING_BUFFER_SIZE)
        response = MCB.build_mcb_frame(sent_cmd, 0, reg_add, data[:limit])
        data_left = data[limit:]
        self.registers[0][reg_add]["value"] = data_left 
        self.__monitoring.available_bytes = len(data_left)
        return response
   

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

    def __decode_msg(self, reg_add, subnode, data):
        reg_id = self.registers[subnode][reg_add]["id"]
        dtype = self.registers[subnode][reg_add]["dtype"]
        data = convert_bytes_to_dtype(data, dtype)
        if reg_id == "MON_DIST_ENABLE" and subnode == 0 and data == 1:
            self.__monitoring.enable()
        if reg_id == "MON_DIST_ENABLE" and subnode == 0 and data == 0:
            self.__monitoring.disable()
        if reg_id == "MON_CMD_FORCE_TRIGGER" and subnode == 0 and data == 1:
            self.__monitoring.trigger()
        if reg_id == "MON_REMOVE_DATA" and subnode == 0 and data == 1:
            self.__monitoring.remove_data()

    def id_to_address(self, subnode, id):
        return self.__reg_id_to_address[subnode][id]

    def get_value_by_id(self, subnode, id):
        address = self.id_to_address(subnode, id)
        return self.registers[subnode][address]["value"]

    def set_value_by_id(self, subnode, id, value):
        address = self.id_to_address(subnode, id)
        self.registers[subnode][address]["value"] = value
