import random
import socket
import time
from enum import Enum
from threading import Thread
from typing import Dict, List, Optional, Tuple, Union

from ingenialink.constants import ETH_BUF_SIZE, MONITORING_BUFFER_SIZE
from ingenialink.enums.register import REG_ACCESS, REG_DTYPE
from ingenialink.ethernet.dictionary import EthernetDictionary
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.ethernet.servo import EthernetServo
from ingenialink.utils import constants
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes
from ingenialink.utils.constants import IL_MC_CW_EO
from ingenialink.utils.mcb import MCB


class MSG_TYPE(Enum):
    RECEIVED = "RECEIVED"
    SENT = "SENT"


class VirtualMonDistBase:
    """Base class to implement VirtualMonitoring and VirtualDisturbance.

    Args:
        drive: Virtual drive instance.

    """

    FREQUENCY = 20000
    FREQ_DIVIDER_REG: str
    BUFFER_SIZE_REG: str
    NUMBER_MAP_REGS: str
    MAP_REG_CFG: str
    BYTES_PER_BLOCK_REG: str
    AVAILABLE_BYTES_REG: str
    DATA_REG: str
    STATUS_REGISTER: str

    def __init__(self, drive: "VirtualDrive") -> None:
        self.drive = drive
        self.enabled = False
        self.disable()
        self.number_mapped_registers = 0
        self.channels_data: Dict[int, List[Union[int, float]]] = {}
        self.channels_dtype: Dict[int, REG_DTYPE] = {}
        self.channels_address: Dict[int, int] = {}
        self.channels_subnode: Dict[int, int] = {}
        self.channels_size: Dict[int, int] = {}
        self.channels_signal: Dict[int, List[Union[int, float]]] = {}

    def enable(self) -> None:
        """Enable Monitoring/Disturbance."""
        self.enabled = True
        self.drive.set_value_by_id(0, self.STATUS_REGISTER, 1)

    def disable(self) -> None:
        """Disable Monitoring/Disturbance."""
        self.enabled = False
        self.drive.set_value_by_id(0, self.STATUS_REGISTER, 0)

    def remove_data(self) -> None:
        """Remove Monitoring/Disturbance data."""
        self.channels_data = {}
        self.drive.set_value_by_id(0, self.DATA_REG, 0)

    @property
    def divider(self) -> int:
        """Frequency divider."""
        value = self.drive.get_value_by_id(0, self.FREQ_DIVIDER_REG)
        if isinstance(value, int):
            return value
        else:
            return 0

    @property
    def buffer_size(self) -> int:
        """Monitoring buffer size."""
        value = self.drive.get_value_by_id(0, self.BUFFER_SIZE_REG)
        if isinstance(value, int):
            return value
        else:
            return 0

    @property
    def bytes_per_block(self) -> int:
        """Monitoring bytes per sample."""
        value = self.drive.get_value_by_id(0, self.BYTES_PER_BLOCK_REG)
        if isinstance(value, int):
            return value
        else:
            return 0

    @bytes_per_block.setter
    def bytes_per_block(self, n_bytes: int) -> None:
        self.drive.set_value_by_id(0, self.BYTES_PER_BLOCK_REG, n_bytes)

    @property
    def number_mapped_registers(self) -> int:
        """Number of mapped registers."""
        value = self.drive.get_value_by_id(0, self.NUMBER_MAP_REGS)
        if isinstance(value, int):
            return value
        else:
            return 0

    @number_mapped_registers.setter
    def number_mapped_registers(self, value: int) -> None:
        self.drive.set_value_by_id(0, self.NUMBER_MAP_REGS, value)

    @property
    def available_bytes(self) -> int:
        """Actual number of monitoring bytes."""
        value = self.drive.get_value_by_id(0, self.AVAILABLE_BYTES_REG)
        if isinstance(value, int):
            return value
        else:
            return 0

    @available_bytes.setter
    def available_bytes(self, n_bytes: int) -> None:
        self.drive.set_value_by_id(0, self.AVAILABLE_BYTES_REG, n_bytes)

    def get_mapped_register(self, channel: int) -> Tuple[int, int, int, int]:
        """Decodes the register with the information of a mapped register.

        Args:
            channel: Channel of the register to be decoded.

        Returns:
            Register subnode
            Register address
            Register dtype index
            Channel size

        """
        register_id = self.MAP_REG_CFG.format(channel)
        data = self.drive.get_value_by_id(0, register_id)
        if not isinstance(data, int):
            raise ValueError("Wrong register type")
        data_h = data >> 16
        data_l = data & 0x0000FFFF
        subnode = data_h >> 12
        address = data_h & 0x0FFF
        dtype = data_l >> 8
        size = data_l & 0x00FF
        return subnode, address, dtype, size

    def map_registers(self) -> None:
        """Creates the channels attribute based on mapped registers."""
        self.bytes_per_block = 0
        empty_list: List[float] = []
        for channel in range(self.number_mapped_registers):
            subnode, address, dtype, size = self.get_mapped_register(channel)
            self.channels_data[channel] = empty_list.copy()
            self.channels_dtype[channel] = REG_DTYPE(dtype)
            self.channels_address[channel] = address
            self.channels_subnode[channel] = subnode
            self.channels_size[channel] = size
            self.channels_signal[channel] = empty_list.copy()
            self.bytes_per_block += size


class VirtualMonitoring(VirtualMonDistBase):
    """Emulates monitoring at the VirtualDrive.

    Args:
        drive: Virtual drive instance.

    """

    FREQ_DIVIDER_REG = "MON_DIST_FREQ_DIV"
    BUFFER_SIZE_REG = "MON_CFG_WINDOW_SAMP"
    NUMBER_MAP_REGS = "MON_CFG_TOTAL_MAP"
    MAP_REG_CFG = "MON_CFG_REG{}_MAP"
    BYTES_PER_BLOCK_REG = "MON_CFG_BYTES_PER_BLOCK"
    DATA_REG = "MON_DATA"
    TRIGGER_TYPE_REG = "MON_CFG_SOC_TYPE"
    AVAILABLE_BYTES_REG = "MON_CFG_BYTES_VALUE"
    STATUS_REGISTER = "MON_DIST_STATUS"

    def __init__(self, drive: "VirtualDrive") -> None:
        self.start_time = 0.0
        super().__init__(drive)

    def enable(self) -> None:
        super().map_registers()
        super().enable()
        self.__create_signals()

        # Set monitoring end and frame available
        self.drive.set_value_by_id(0, self.STATUS_REGISTER, 0x10 | (0x8 + 1))

        # Store data
        sampling_rate = self.FREQUENCY / self.divider
        elapsed_time = time.time() - self.start_time
        elapsed_samples = int(elapsed_time * sampling_rate)
        n_samples = min(elapsed_samples, self.buffer_size)
        for channel in range(self.number_mapped_registers):
            self.channels_data[channel] = self.channels_signal[channel][:n_samples]
        self.available_bytes = n_samples * self.bytes_per_block
        self._store_data_bytes()
        self.start_time = 0.0

    def trigger(self) -> None:
        """Triggers monitoring."""
        if self.enabled:
            self.start_time = time.time()

    def rearm(self) -> None:
        """Rearm monitoring."""
        self.map_registers()
        self.disable()
        self.enable()

    def __create_signals(self) -> None:
        """Creates emulated monitoring signals."""
        for channel in range(self.number_mapped_registers):
            start_value = self.channels_address[channel] + self.channels_subnode[channel]
            if self.channels_dtype[channel] == REG_DTYPE.FLOAT:
                signal = [
                    float(start_value + i)
                    for i in range(0, self.buffer_size * self.divider, self.divider)
                ]
            else:
                signal = [
                    start_value + i for i in range(0, self.buffer_size * self.divider, self.divider)
                ]
            self.channels_signal[channel] = signal

    def _store_data_bytes(self) -> None:
        """Convert signals into a bytes and store it at MON_DATA register."""
        byte_array = bytes()
        n_samples = len(self.channels_data[0])
        for sample in range(n_samples):
            for channel in range(self.number_mapped_registers):
                value = self.channels_data[channel][sample]
                size = self.channels_size[channel]
                sample_bytes = convert_dtype_to_bytes(value, self.channels_dtype[channel])
                if len(sample_bytes) < size:
                    sample_bytes += b"0" * (size - len(sample_bytes))
                byte_array += sample_bytes
        self.drive.set_value_by_id(0, "MON_DATA", byte_array)

    @property
    def trigger_type(self) -> int:
        """Trigger type Auto(0), Force (1) or Rising or Failing (2)."""
        value = self.drive.get_value_by_id(0, self.TRIGGER_TYPE_REG)
        if isinstance(value, int):
            return value
        else:
            return 0


class VirtualDisturbance(VirtualMonDistBase):
    """Emulates disturbance at the VirtualDrive.

    Args:
        drive: Virtual drive instance.

    """

    FREQ_DIVIDER_REG = "DIST_FREQ_DIV"
    BUFFER_SIZE_REG = "DIST_CFG_SAMPLES"
    NUMBER_MAP_REGS = "DIST_CFG_MAP_REGS"
    MAP_REG_CFG = "DIST_CFG_REG{}_MAP"
    BYTES_PER_BLOCK_REG = "DIST_CFG_BYTES_PER_BLOCK"
    AVAILABLE_BYTES_REG = "DIST_CFG_BYTES"
    DATA_REG = "DIST_DATA"
    STATUS_REGISTER = "DIST_STATUS"

    def __init__(self, drive: "VirtualDrive") -> None:
        self.start_time = 0.0
        self.received_bytes = bytes()
        super().__init__(drive)

    def enable(self) -> None:
        super().enable()

    def append_data(self, data: bytes) -> None:
        """Append received disturbance data until the buffer is full.

        Args:
            data: Received data.
        """
        if len(self.channels_data) == 0:
            super().map_registers()
        self.received_bytes += data
        self.available_bytes = len(self.received_bytes)
        if self.available_bytes == self.buffer_size_bytes:
            self.write_data()

    def write_data(self) -> None:
        """Convert received data and store it at the channels attribute."""
        n_samples = self.buffer_size
        buffer = self.received_bytes
        for sample in range(n_samples):
            for channel in range(self.number_mapped_registers):
                size = self.channels_size[channel]
                dtype = self.channels_dtype[channel]
                bytes = buffer[:size]
                value = convert_bytes_to_dtype(bytes, dtype)
                if isinstance(value, (int, float)):
                    self.channels_data[channel].append(value)
                buffer = buffer[size:]

    @property
    def buffer_size_bytes(self) -> int:
        """Buffer size in bytes."""
        buffer_size_bytes = 0
        n_samples = self.buffer_size
        for channel in range(self.number_mapped_registers):
            buffer_size_bytes += self.channels_size[channel] * n_samples
        return buffer_size_bytes


class VirtualDrive(Thread):
    """Emulates a drive by creating a UDP server that sends and receives MCB messages.

    Args:
        ip: Server IP address.
        port: Server port number.
        dictionary_path: Path to the dictionary.

    """

    ACK_CMD = 3
    WRITE_CMD = 2
    READ_CMD = 1

    def __init__(
        self, ip: str, port: int, dictionary_path: str = "./tests/resources/virtual_drive.xdf"
    ) -> None:
        super(VirtualDrive, self).__init__()
        self.ip = ip
        self.port = port
        self.dictionary_path = dictionary_path
        self.__stop = False
        self.device_info = None
        self.__logger: List[Dict[str, Union[float, bytes, str, Tuple[str, int]]]] = []
        self.__reg_address_to_id: Dict[int, Dict[int, str]] = {}
        self.__dictionary = EthernetDictionary(dictionary_path)
        self._init_registers()
        self._update_registers()
        self.__monitoring = VirtualMonitoring(self)
        self.__disturbance = VirtualDisturbance(self)
        self.__set_motor_ready_to_switch_on()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def run(self) -> None:
        """Open socket, listen and decode messages."""
        server_address = (self.ip, self.port)
        self.socket.bind(server_address)
        self.socket.settimeout(2)
        value: Union[int, float, bytes, str]
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
                    self.set_value_by_id(subnode, str(register.identifier), value)
                    self.__decode_msg(reg_add, subnode, data)
            elif cmd == self.READ_CMD:
                value = self.get_value_by_id(subnode, str(register.identifier))
                sent_cmd = self.ACK_CMD
                if reg_add == self.id_to_address(0, "MON_DATA") and isinstance(value, bytes):
                    response = self._response_monitoring_data(value)
                else:
                    data = convert_dtype_to_bytes(value, register.dtype)
                    response = MCB.build_mcb_frame(sent_cmd, subnode, reg_add, data)
                # TODO: send error if the register is WO
            else:
                continue
            self.__send(response, add)

        time.sleep(0.1)

    def stop(self) -> None:
        """Stop socket."""
        if self.socket is not None:
            self.socket.close()
        self.__stop = True
        self.__monitoring.disable()

    def _init_registers(self) -> None:
        """Initialize some relevant registers."""
        self.set_value_by_id(0, "DRV_ID_PRODUCT_CODE_COCO", 123456)
        self.set_value_by_id(1, "DRV_ID_PRODUCT_CODE", 123456)
        self.set_value_by_id(0, "DRV_ID_REVISION_NUMBER_COCO", 654321)
        self.set_value_by_id(1, "DRV_ID_REVISION_NUMBER", 654321)
        self.set_value_by_id(0, "DRV_APP_COCO_VERSION", "0.1.0")
        self.set_value_by_id(1, "DRV_ID_SOFTWARE_VERSION", "0.1.0")
        self.set_value_by_id(0, "DRV_ID_SERIAL_NUMBER_COCO", 123456789)
        self.set_value_by_id(1, "DRV_ID_SERIAL_NUMBER", 123456789)
        self.set_value_by_id(0, "DRV_ID_VENDOR_ID_COCO", 987654321)
        self.set_value_by_id(1, "DRV_ID_VENDOR_ID", 987654321)
        self.set_value_by_id(1, "COMMU_ANGLE_REF_SENSOR", 4)
        self.set_value_by_id(1, "COMMU_ANGLE_SENSOR", 4)
        self.set_value_by_id(1, "CL_VEL_FBK_SENSOR", 4)
        self.set_value_by_id(1, "CL_POS_FBK_SENSOR", 4)
        self.set_value_by_id(1, "CL_AUX_FBK_SENSOR", 4)
        self.set_value_by_id(1, "PROF_POS_VEL_RATIO", 1.0)
        self.set_value_by_id(1, "FBK_BISS_CHAIN", 1)
        self.set_value_by_id(1, "DRV_PS_FREQ_SELECTION", 0)
        self.set_value_by_id(1, "DRV_POS_VEL_RATE", 20000)
        self.set_value_by_id(0, "DIST_MAX_SIZE", 8192)
        self.set_value_by_id(0, "MON_MAX_SIZE", 8192)
        self.set_value_by_id(0, VirtualMonitoring.STATUS_REGISTER, 0)
        self.set_value_by_id(0, VirtualDisturbance.STATUS_REGISTER, 0)

    def _update_registers(self) -> None:
        """Force storage_valid at each register and add registers that are not in the dictionary."""
        for subnode in range(self.__dictionary.subnodes):
            self.__reg_address_to_id[subnode] = {}
            for reg_id, reg in self.__dictionary.registers(subnode).items():
                self.__reg_address_to_id[subnode][reg.address] = reg_id
                self.__dictionary.registers(subnode)[reg_id].storage_valid = True

        custom_regs = {
            "MON_DATA": EthernetServo.MONITORING_DATA,
            "DIST_DATA": EthernetServo.DIST_DATA,
        }
        for id, reg in custom_regs.items():
            register = EthernetRegister(
                reg.address, REG_DTYPE.DOMAIN, reg.access, identifier=id, subnode=reg.subnode
            )
            self.__dictionary._add_register_list(register)
            self.__dictionary.registers(reg.subnode)[id].storage_valid = True

            self.__reg_address_to_id[reg.subnode][reg.address] = id

    def __send(self, response: bytes, address: Tuple[str, int]) -> None:
        """Send a message and update log.

        Args:
            response: Message to be sent.
            address: IP address and port.
        """
        time.sleep(0.01)  # Emulate latency of 10 ms
        self.socket.sendto(response, address)
        self.__log(address, response, MSG_TYPE.SENT)

    def _response_monitoring_data(self, data: bytes) -> bytes:
        """Creates a response for monitoring data.

        Args:
            data: Data to be sent.

        Returns:
            MCB frame.
        """
        sent_cmd = self.ACK_CMD
        reg_add = self.id_to_address(0, "MON_DATA")
        limit = min(len(data), MONITORING_BUFFER_SIZE)
        response = MCB.build_mcb_frame(sent_cmd, 0, reg_add, data[:limit])
        data_left = data[limit:]
        self.set_value_by_id(0, "MON_DATA", data_left)
        self.__monitoring.available_bytes = len(data_left)
        return response

    def __log(self, ip_port: Tuple[str, int], message: bytes, msg_type: MSG_TYPE) -> None:
        """Updates log.

        Args:
            ip_port: IP address and port.
            message: Received or sent message.
            msg_type: Sent or Received.
        """
        self.__logger.append(
            {
                "timestamp": time.time(),
                "ip_port": ip_port,
                "type": msg_type.value,
                "message": message,
            }
        )

    @property
    def log(self) -> List[Dict[str, Union[float, bytes, str, Tuple[str, int]]]]:
        """Dictionary containing log information."""
        return self.__logger

    def clean_log(self) -> None:
        """Cleans log."""
        self.__logger = []

    def __decode_msg(self, reg_add: int, subnode: int, data: bytes) -> None:
        """Decodes received messages and run specific methods if needed.

        Args:
            reg_add: Register address.
            subnode: Subnode.
            data: Received data.
        """
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
        if reg_id == "MON_REARM" and subnode == 0 and value == 1:
            self.__monitoring.rearm()
        if reg_id == "DIST_ENABLE" and subnode == 0 and value == 1:
            self.__disturbance.enable()
        if reg_id == "DIST_ENABLE" and subnode == 0 and value == 0:
            self.__disturbance.disable()
        if reg_id == "DIST_REMOVE_DATA" and subnode == 0 and value == 1:
            self.__disturbance.remove_data()
        if reg_id == "DIST_DATA" and subnode == 0:
            self.__disturbance.append_data(data)
        if reg_id == "DRV_STATE_CONTROL" and subnode == 1 and (int(value) & IL_MC_CW_EO):
            self.__set_motor_enable()
        if reg_id == "DRV_STATE_CONTROL" and subnode == 1 and (value == constants.IL_MC_PDS_CMD_DV):
            self.__set_motor_disable()
        if reg_id == "DRV_STATE_CONTROL" and subnode == 1 and (value == constants.IL_MC_PDS_CMD_SD):
            self.__set_motor_ready_to_switch_on()

    def address_to_id(self, subnode: int, address: int) -> str:
        """Converts a register address into its ID.

        Args:
            subnode: Subnode.
            address: Register address.

        Returns:
            Register ID.
        """
        return self.__reg_address_to_id[subnode][address]

    def id_to_address(self, subnode: int, id: str) -> int:
        """Converts a register address into an ID.

        Args:
            subnode: Subnode.
            id: Register ID.

        Returns:
            Register address.
        """
        register = self.__dictionary.registers(subnode)[id]
        return register.address

    def get_value_by_id(self, subnode: int, id: str) -> Union[int, float, str, bytes]:
        """Returns a register value by its ID.

        Args:
            subnode: Subnode.
            id: Register ID.

        Returns:
            Register value.
        """
        register = self.__dictionary.registers(subnode)[id]
        value: Union[int, float, str]
        if register._storage is None:
            range_value = register.range
            if not register.range[0]:
                range_value = (1, 10)
            value = random.uniform(*range_value)
            if register.dtype != REG_DTYPE.FLOAT:
                value = int(value)
                if register.dtype == REG_DTYPE.STR:
                    value = ""
            self.set_value_by_id(subnode, id, value)
        storage_value = self.__dictionary.registers(subnode)[id]._storage
        if isinstance(storage_value, (int, float, str, bytes)):
            return storage_value
        else:
            return 0

    def set_value_by_id(self, subnode: int, id: str, value: Union[float, int, str, bytes]) -> None:
        """Set a register value by its ID.

        Args:
            subnode: Subnode.
            id: Register ID.
            value: Value to be set.
        """
        self.__dictionary.registers(subnode)[id].storage = value

    def get_register(
        self, subnode: int, address: Optional[int] = None, id: Optional[str] = None
    ) -> EthernetRegister:
        """Returns a register by its address or ID.

        Args:
            subnode: Subnode.
            address: Register address. Default to None.
            id: Register ID. Default to None.

        Returns:
            Register instance.

        Raises:
            ValueError: If both address and id are None.
        """
        if address is not None:
            id = self.address_to_id(subnode, address)
        else:
            if id is None:
                raise ValueError("Register address or id should be passed")
        return self.__dictionary.registers(subnode)[id]

    def __set_motor_enable(self) -> None:
        """Set the enabled state."""
        self.set_value_by_id(1, "DRV_STATE_STATUS", constants.IL_MC_PDS_STA_OE)

    def __set_motor_disable(self) -> None:
        """Set the disabled state."""
        self.set_value_by_id(1, "DRV_STATE_STATUS", constants.IL_MC_PDS_STA_SOD)

    def __set_motor_ready_to_switch_on(self) -> None:
        """Set the ready-to-switch-on state."""
        self.set_value_by_id(1, "DRV_STATE_STATUS", constants.IL_MC_PDS_STA_RTSO)
