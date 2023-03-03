import socket
import time
from enum import Enum
from threading import Thread
import random

from ingenialink.constants import ETH_BUF_SIZE, MONITORING_BUFFER_SIZE
from ingenialink.utils.mcb import MCB
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes
from ingenialink.ethernet.servo import EthernetServo
from ingenialink.ethernet.dictionary import EthernetDictionary
from ingenialink.enums.register import REG_DTYPE, REG_ACCESS
from ingenialink.utils import constants


class MSG_TYPE(Enum):
    RECEIVED = "RECEIVED"
    SENT = "SENT"


class VirtualMonDistBase:
    """Base class to implement VirtualMonitoring and VirtualDisturbance.

    Args:
        drive (VirtualDrive): Virtual drive instance.

    """

    FREQUENCY = 20000
    FREQ_DIVIDER_REG = None
    BUFFER_SIZE_REG = None
    NUMBER_MAP_REGS = None
    MAP_REG_CFG = None
    BYTES_PER_BLOCK_REG = None
    AVAILABLE_BYTES_REG = None
    DATA_REG = None

    def __init__(self, drive):
        self.drive = drive
        self.enabled = False
        self.channels = {}
        self.number_mapped_registers = 0

    def enable(self):
        """Enable Monitoring/Disturbance."""
        self.enabled = True

    def disable(self):
        """Disable Monitoring/Disturbance."""
        self.enabled = False

    def remove_data(self):
        """Remove Monitoring/Disturbance data."""
        for channel in range(self.number_mapped_registers):
            self.channels[channel]["data"] = []
            self.drive.set_value_by_id(0, self.DATA_REG, 0)

    @property
    def divider(self):
        """int: Frequency divider."""
        return self.drive.get_value_by_id(0, self.FREQ_DIVIDER_REG)

    @property
    def buffer_size(self):
        """int: Monitoring buffer size."""
        return self.drive.get_value_by_id(0, self.BUFFER_SIZE_REG)

    @property
    def bytes_per_block(self):
        """int: Monitoring bytes per sample."""
        return self.drive.get_value_by_id(0, self.BYTES_PER_BLOCK_REG)

    @bytes_per_block.setter
    def bytes_per_block(self, n_bytes):
        self.drive.set_value_by_id(0, self.BYTES_PER_BLOCK_REG, n_bytes)

    @property
    def number_mapped_registers(self):
        """int: Number of mapped registers."""
        return self.drive.get_value_by_id(0, self.NUMBER_MAP_REGS)

    @number_mapped_registers.setter
    def number_mapped_registers(self, value):
        return self.drive.set_value_by_id(0, self.NUMBER_MAP_REGS, value)

    @property
    def available_bytes(self):
        """int: Actual number of monitoring bytes."""
        return self.drive.get_value_by_id(0, self.AVAILABLE_BYTES_REG)

    @available_bytes.setter
    def available_bytes(self, n_bytes):
        self.drive.set_value_by_id(0, self.AVAILABLE_BYTES_REG, n_bytes)

    def get_mapped_register(self, channel):
        """Decodes the register with the information of a mapped register.

        Args:
            channel (int): Channel of the register to be decoded.

        Returns:
            int: Register subnode
            int: Register address
            int: Register dtype index
            int: Channel size

        """
        register_id = self.MAP_REG_CFG.format(channel)
        data = self.drive.get_value_by_id(0, register_id)
        data_h = data >> 16
        data_l = data & 0x0000FFFF
        subnode = data_h >> 12
        address = data_h & 0x0FFF
        dtype = data_l >> 8
        size = data_l & 0x00FF
        return subnode, address, dtype, size

    def map_registers(self):
        """Creates the channels attribute based on mapped registers."""
        self.bytes_per_block = 0
        for channel in range(self.number_mapped_registers):
            subnode, address, dtype, size = self.get_mapped_register(channel)
            self.channels[channel] = {
                "data": [],
                "dtype": REG_DTYPE(dtype),
                "address": address,
                "subnode": subnode,
                "size": size,
                "signal": [],
            }
            self.bytes_per_block += size


class VirtualMonitoring(VirtualMonDistBase):
    """Emulates monitoring at the VirtualDrive.

    Args:
        drive (Virtual Drive): Virtual drive instance.

    """

    FREQ_DIVIDER_REG = "MON_DIST_FREQ_DIV"
    BUFFER_SIZE_REG = "MON_CFG_WINDOW_SAMP"
    NUMBER_MAP_REGS = "MON_CFG_TOTAL_MAP"
    MAP_REG_CFG = "MON_CFG_REG{}_MAP"
    BYTES_PER_BLOCK_REG = "MON_CFG_BYTES_PER_BLOCK"
    DATA_REG = "MON_DATA"
    TRIGGER_TYPE_REG = "MON_CFG_SOC_TYPE"
    AVAILABLE_BYTES_REG = "MON_CFG_BYTES_VALUE"

    def __init__(self, drive):
        self.start_time = None
        super().__init__(drive)

    def enable(self):
        super().map_registers()
        super().enable()
        self.__create_signals()

    def disable(self):
        if self.enabled is False or self.start_time is None:
            return
        sampling_rate = self.FREQUENCY / self.divider
        elapsed_time = time.time() - self.start_time
        elapsed_samples = int(elapsed_time * sampling_rate)
        n_samples = min(elapsed_samples, self.buffer_size)
        for channel in range(self.number_mapped_registers):
            self.channels[channel]["data"] = self.channels[channel]["signal"][:n_samples]
        self.available_bytes = n_samples * self.bytes_per_block
        self._store_data_bytes()
        self.start_time = None
        super().disable()

    def trigger(self):
        """Triggers monitoring."""
        if self.enabled:
            self.start_time = time.time()

    def __create_signals(self):
        """Creates emulated monitoring signals."""
        for channel in range(self.number_mapped_registers):
            start_value = self.channels[channel]["address"] + self.channels[channel]["subnode"]
            signal = [
                start_value + i for i in range(0, self.buffer_size * self.divider, self.divider)
            ]
            self.channels[channel]["signal"] = signal

    def _store_data_bytes(self):
        """Convert signals into a bytearray and store it at MON_DATA register."""
        bytes = bytearray()
        n_samples = len(self.channels[0]["data"])
        for sample in range(n_samples):
            for channel in range(self.number_mapped_registers):
                value = self.channels[channel]["data"][sample]
                size = self.channels[channel]["size"]
                sample_bytes = convert_dtype_to_bytes(value, self.channels[channel]["dtype"])
                if len(sample_bytes) < size:
                    sample_bytes += b"0" * (size - len(sample_bytes))
                bytes += sample_bytes
        self.drive.set_value_by_id(0, "MON_DATA", bytes)

    @property
    def trigger_type(self):
        """int: Trigger type Auto(0), Force (1) or Rising or Failing (2)."""
        return self.drive.get_value_by_id(0, self.TRIGGER_TYPE_REG)


class VirtualDisturbance(VirtualMonDistBase):
    """Emulates disturbance at the VirtualDrive.

    Args:
        drive (VirtualDrive): Virtual drive instance.

    """

    FREQ_DIVIDER_REG = "DIST_FREQ_DIV"
    BUFFER_SIZE_REG = "DIST_CFG_SAMPLES"
    NUMBER_MAP_REGS = "DIST_CFG_MAP_REGS"
    MAP_REG_CFG = "DIST_CFG_REG{}_MAP"
    BYTES_PER_BLOCK_REG = "DIST_CFG_BYTES_PER_BLOCK"
    AVAILABLE_BYTES_REG = "DIST_CFG_BYTES"
    DATA_REG = "DIST_DATA"

    def __init__(self, drive):
        self.start_time = None
        self.received_bytes = bytearray()
        super().__init__(drive)

    def enable(self):
        super().enable()

    def append_data(self, data):
        """Append received disturbance data until the buffer is full."""
        if len(self.channels) == 0:
            super().map_registers()
        self.received_bytes += data
        self.available_bytes = len(self.received_bytes)
        if self.available_bytes == self.buffer_size_bytes:
            self.write_data()

    def write_data(self):
        """Convert received data and store it at the channels attribute."""
        n_samples = self.buffer_size
        buffer = self.received_bytes
        for sample in range(n_samples):
            for channel in range(self.number_mapped_registers):
                size = self.channels[channel]["size"]
                dtype = self.channels[channel]["dtype"]
                bytes = buffer[:size]
                value = convert_bytes_to_dtype(bytes, dtype)
                self.channels[channel]["data"].append(value)
                buffer = buffer[size:]

    @property
    def buffer_size_bytes(self):
        """int: Buffer size in bytes."""
        buffer_size_bytes = 0
        n_samples = self.buffer_size
        for channel in range(self.number_mapped_registers):
            buffer_size_bytes += self.channels[channel]["size"] * n_samples
        return buffer_size_bytes


class VirtualDrive(Thread):
    """Emulates a drive by creating a UDP server that sends and receives MCB messages.

    Args:
        ip (int): Server IP address.
        port (int): Server port number.
        dictionary_path (str): Path to the dictionary.

    """

    ACK_CMD = 3
    WRITE_CMD = 2
    READ_CMD = 1

    def __init__(self, ip, port, dictionary_path="./tests/resources/virtual_drive.xdf"):
        super(VirtualDrive, self).__init__()
        self.ip = ip
        self.port = port
        self.dictionary_path = dictionary_path
        self.socket = None
        self.__stop = False
        self.device_info = None
        self.__logger = []
        self.__reg_address_to_id = {}
        self.__dictionary = EthernetDictionary(dictionary_path)
        self._init_registers()
        self._update_registers()
        self.__monitoring = VirtualMonitoring(self)
        self.__disturbance = VirtualDisturbance(self)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def run(self):
        """Open socket and listen messages."""
        server_address = (self.ip, self.port)
        self.socket.bind(server_address)
        self.socket.settimeout(2)
        while not self.__stop:
            try:
                frame, add = self.socket.recvfrom(ETH_BUF_SIZE)
            except:
                continue
            reg_add, subnode, cmd, data = MCB.read_mcb_frame(frame)
            self.__log(add, frame, MSG_TYPE.RECEIVED)
            register = self.get_register(subnode, reg_add)
            if cmd == self.WRITE_CMD:
                sent_cmd = self.ACK_CMD
                response = MCB.build_mcb_frame(sent_cmd, subnode, reg_add, data[:8])
                if register.access in [REG_ACCESS.RW, REG_ACCESS.WO]:  # TODO: send error otherwise
                    value = convert_bytes_to_dtype(data, register.dtype)
                    self.set_value_by_id(subnode, register.identifier, value)
                    self.__decode_msg(reg_add, subnode, data)
            elif cmd == self.READ_CMD:
                value = self.get_value_by_id(subnode, register.identifier)
                data = convert_dtype_to_bytes(value, register.dtype)
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
        """Stop socket."""
        if self.socket is not None:
            self.socket.close()
        self.__stop = True
        self.__monitoring.disable()

    def _init_registers(self):
        """Initialize some relevant registers."""
        self.set_value_by_id(0, "DRV_ID_PRODUCT_CODE_COCO", 123456)
        self.set_value_by_id(1, "DRV_ID_PRODUCT_CODE", 123456)
        self.set_value_by_id(0, "DRV_ID_REVISION_NUMBER_COCO", 654321)
        self.set_value_by_id(1, "DRV_ID_REVISION_NUMBER", 654321)
        self.set_value_by_id(0, "DRV_APP_COCO_VERSION", "0.1.0")
        self.set_value_by_id(1, "DRV_ID_SOFTWARE_VERSION", "0.1.0")
        self.set_value_by_id(1, "DRV_ID_SOFTWARE_VERSION", "0.1.0")
        self.set_value_by_id(1, "DRV_STATE_STATUS", constants.IL_MC_PDS_STA_RTSO)

    def _update_registers(self):
        """Force storage_valid at each register and add registers that are not in the dictionary."""
        for subnode in range(self.__dictionary.subnodes):
            self.__reg_address_to_id[subnode] = {}
            for reg_id, reg in self.__dictionary.registers(subnode).items():
                self.__reg_address_to_id[subnode][reg.address] = reg_id
                self.__dictionary.registers(subnode)[reg_id].storage_valid = 1

        custom_regs = {
            "MON_DATA": EthernetServo.MONITORING_DATA,
            "DIST_DATA": EthernetServo.DIST_DATA,
        }
        for id, reg in custom_regs.items():
            register = {
                "address": reg.address,
                "access": reg.access,
                "dtype": REG_DTYPE.DOMAIN,
                "identifier": id,
                "subnode": reg.subnode,
            }
            self.__dictionary._add_register_list(register)
            self.__dictionary.registers(reg.subnode)[id].storage_valid = 1

            self.__reg_address_to_id[reg.subnode][reg.address] = id

    def __send(self, response, address):
        """Send a message and update log."""
        time.sleep(0.01)  # Emulate latency of 10 ms
        self.socket.sendto(response, address)
        self.__log(address, response, MSG_TYPE.SENT)

    def _response_monitoring_data(self, data):
        """Creates a response for monitoring data."""
        sent_cmd = self.ACK_CMD
        reg_add = self.id_to_address(0, "MON_DATA")
        limit = min(len(data), MONITORING_BUFFER_SIZE)
        response = MCB.build_mcb_frame(sent_cmd, 0, reg_add, data[:limit])
        data_left = data[limit:]
        self.set_value_by_id(0, "MON_DATA", data_left)
        self.__monitoring.available_bytes = len(data_left)
        return response

    def __log(self, ip_port, message, msg_type):
        """Updates log."""
        self.__logger.append(
            {
                "timestamp": time.time(),
                "ip_port": ip_port,
                "type": msg_type.value,
                "message": message,
            }
        )

    @property
    def log(self):
        """dict: Dictionary containing log information."""
        return self.__logger

    def clean_log(self):
        """Cleans log."""
        self.__logger = []

    def __decode_msg(self, reg_add, subnode, data):
        """Decodes received messages and run specific methods if needed."""
        register = self.get_register(subnode, reg_add)
        reg_id = register.identifier
        dtype = register.dtype
        value = convert_bytes_to_dtype(data, dtype)
        if reg_id == "MON_DIST_ENABLE" and subnode == 0 and value == 1:
            self.__monitoring.enable()
        if reg_id == "MON_DIST_ENABLE" and subnode == 0 and value == 0:
            self.__monitoring.disable()
        if reg_id == "MON_CMD_FORCE_TRIGGER" and subnode == 0 and value == 1:
            self.__monitoring.trigger()
        if reg_id == "MON_REMOVE_DATA" and subnode == 0 and value == 1:
            self.__monitoring.remove_data()
        if reg_id == "DIST_ENABLE" and subnode == 0 and value == 1:
            self.__disturbance.enable()
        if reg_id == "DIST_ENABLE" and subnode == 0 and value == 0:
            self.__disturbance.disable()
        if reg_id == "DIST_REMOVE_DATA" and subnode == 0 and value == 1:
            self.__disturbance.remove_data()
        if reg_id == "DIST_DATA" and subnode == 0:
            self.__disturbance.append_data(data)

    def address_to_id(self, subnode, address):
        """Converts a register address into its ID."""
        return self.__reg_address_to_id[subnode][address]

    def id_to_address(self, subnode, id):
        """Converts a register address into an ID."""
        register = self.__dictionary.registers(subnode)[id]
        return register.address

    def get_value_by_id(self, subnode, id):
        """Returns a register value by its ID."""
        register = self.__dictionary.registers(subnode)[id]
        if not register._storage:
            range_value = register.range
            if not register.range[0]:
                range_value = (1, 10)
            value = random.uniform(*range_value)
            if register.dtype != REG_DTYPE.FLOAT:
                value = int(value)
                if register.dtype == REG_DTYPE.STR:
                    value = ""
        return self.__dictionary.registers(subnode)[id]._storage

    def set_value_by_id(self, subnode, id, value):
        """Set a register value by its ID."""
        self.__dictionary.registers(subnode)[id].storage = value

    def get_register(self, subnode, address=None, id=None):
        """Returns a register by its address or ID."""
        if address is not None:
            id = self.address_to_id(subnode, address)
        else:
            if id is None:
                raise ValueError("Register address or id should be passed")
        return self.__dictionary.registers(subnode)[id]
