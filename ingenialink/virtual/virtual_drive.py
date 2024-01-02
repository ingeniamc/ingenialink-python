import random
import socket
import time
from enum import Enum, IntEnum
from threading import Thread
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import signal

from ingenialink.constants import ETH_BUF_SIZE, MONITORING_BUFFER_SIZE
from ingenialink.enums.register import REG_ACCESS, REG_DTYPE
from ingenialink.ethernet.dictionary import EthernetDictionary
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.ethernet.servo import EthernetServo
from ingenialink.utils import constants
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes
from ingenialink.utils.mcb import MCB


class MSG_TYPE(Enum):
    RECEIVED = "RECEIVED"
    SENT = "SENT"


class OperationMode(IntEnum):
    """Operation Mode Enum"""

    VOLTAGE = 0x00
    CURRENT_AMPLIFIER = 0x01
    CURRENT = 0x02
    CYCLIC_CURRENT = 0x22
    VELOCITY = 0x03
    PROFILE_VELOCITY = 0x13
    CYCLIC_VELOCITY = 0x23
    POSITION = 0x04
    PROFILE_POSITION = 0x14
    CYCLIC_POSITION = 0x24
    PROFILE_POSITION_S_CURVE = 0x44
    INTERPOLATED_POSITION = 0xA4
    PVT = 0xB4
    HOMING = 0x113
    TORQUE = 0x05
    CYCLIC_TORQUE = 0x25


class BasePlant:
    REGISTER_SET_POINT: str
    REGISTER_COMMAND: str
    REGISTER_VALUE: str

    def __init__(self, drive: "VirtualDrive") -> None:
        self.drive = drive
        self.monitoring_frequency = self.drive._monitoring.FREQUENCY
        self.plant: signal.TransferFunction
        self.set_point_register = self.drive.get_register(1, id=self.REGISTER_SET_POINT)
        self.command_register = self.drive.get_register(1, id=self.REGISTER_COMMAND)
        self.value_register = self.drive.get_register(1, id=self.REGISTER_VALUE)

    def emulate_plant(self, from_disturbance=True):
        dist_signal = self.set_point_register.signal
        if len(dist_signal) == 0:
            return

        if from_disturbance:
            monitoring_size = self.drive._monitoring.buffer_size * self.drive._monitoring.divider
            if monitoring_size > len(dist_signal):
                repetitions = monitoring_size // len(dist_signal) + 1
                dist_signal = np.tile(dist_signal, repetitions)
            # dist_signal = dist_signal[:monitoring_size]

        mon_signal = signal.lfilter(self.plant.num, self.plant.den, dist_signal)

        self.command_register.signal = dist_signal
        self.value_register.signal = mon_signal
        self.command_register.time = self.set_point_register.time
        self.value_register.time = self.set_point_register.time

    def jog(self, new_value: float) -> None:
        time_of_change = time.time()
        start_time = time_of_change - 1
        end_time = start_time + 5
        time_vector = np.arange(start_time, end_time, 1 / self.drive.current_loop_rate)
        index_change = np.argmin(np.abs(time_vector - time_of_change))
        jog_signal = np.zeros(len(time_vector))
        current_value = self.set_point_register.storage
        jog_signal[:index_change] = current_value
        jog_signal[index_change:] = new_value
        self.set_point_register.time = time_vector
        self.set_point_register.signal = jog_signal
        self.emulate_plant(from_disturbance=False)

    def clean_signals(self):
        self.command_register.signal = np.array([])
        self.command_register.time = np.array([])
        self.value_register.signal = np.array([])
        self.value_register.time = np.array([])
        self.set_point_register.signal = np.array([])
        self.set_point_register.time = np.array([])


class BaseOpenLoopPlant(BasePlant):
    def __init__(self, drive: "VirtualDrive", num: List[float], den: List[float]) -> None:
        super().__init__(drive)
        self.plant = signal.TransferFunction(num, den).to_discrete(dt=1 / self.monitoring_frequency)
        self.value_register.noise_amplitude = 0.01


class BaseClosedLoopPlant(BasePlant):

    KI_REG: str
    KP_REG: str

    def __init__(self, drive: "VirtualDrive", open_loop_plant: signal.TransferFunction) -> None:
        super().__init__(drive)
        self.open_loop_plant = open_loop_plant
        self.create_closed_loop_plant()

    def create_closed_loop_plant(self):
        discrete_controller = signal.TransferFunction(
            [self.kp + self.kp * self.ki * 1 / self.monitoring_frequency, -self.kp],
            [1, -1],
            dt=1 / self.monitoring_frequency,
        )

        num = np.polymul(self.open_loop_plant.num, discrete_controller.num)
        den = np.polymul(self.open_loop_plant.den, discrete_controller.den)
        open_loop_control = signal.TransferFunction(num, den, dt=1 / self.monitoring_frequency)

        feedback = signal.TransferFunction([1], [1], dt=1 / self.monitoring_frequency)

        num = np.polymul(open_loop_control.num, feedback.den)
        den = np.polyadd(
            np.polymul(open_loop_control.num, feedback.num),
            np.polymul(open_loop_control.den, feedback.den),
        )

        self.plant = signal.TransferFunction(num, den, dt=1 / self.monitoring_frequency)

    def emulate_plant(self, from_disturbance=True):
        self.create_closed_loop_plant()
        return super().emulate_plant(from_disturbance=from_disturbance)

    @property
    def kp(self):
        return self.drive.get_value_by_id(1, self.KP_REG)

    @property
    def ki(self):
        return self.drive.get_value_by_id(1, self.KI_REG)


class PlantOpenLoopRL(BaseOpenLoopPlant):
    """Emulator of a open-loop RL plant."""

    REGISTER_SET_POINT = "CL_VOL_D_SET_POINT"
    REGISTER_COMMAND = "CL_VOL_D_CMD"
    REGISTER_VALUE = "CL_CUR_D_VALUE"

    def __init__(self, drive: "VirtualDrive") -> None:
        self.l_henry = 0.39e-3
        self.r_ohm = 1.1
        super().__init__(drive, [1], [self.l_henry, self.r_ohm])


class PlantClosedLoopRL(BaseClosedLoopPlant):
    """Emulator of a closed-loop RL plant."""

    REGISTER_SET_POINT = "CL_CUR_D_SET_POINT"
    REGISTER_COMMAND = "CL_CUR_D_REF_VALUE"
    REGISTER_VALUE = "CL_CUR_D_VALUE"

    KI_REG = "CL_CUR_D_KI"
    KP_REG = "CL_CUR_D_KP"


class PlantOpenLoopRLQuadrature(BaseOpenLoopPlant):
    """Emulator of a open-loop RL quadrature plant."""

    REGISTER_SET_POINT = "CL_VOL_Q_SET_POINT"
    REGISTER_COMMAND = "CL_VOL_Q_CMD"
    REGISTER_VALUE = "CL_CUR_Q_VALUE"

    def __init__(self, drive: "VirtualDrive") -> None:
        self.l_henry = 0.39e-3
        self.r_ohm = 1.1
        super().__init__(drive, [1], [self.l_henry, self.r_ohm])


class PlantClosedLoopRLQuadrature(BaseClosedLoopPlant):
    """Emulator of a closed-loop RL quadrature plant."""

    REGISTER_SET_POINT = "CL_CUR_Q_SET_POINT"
    REGISTER_COMMAND = "CL_CUR_Q_REF_VALUE"
    REGISTER_VALUE = "CL_CUR_Q_VALUE"

    KI_REG = "CL_CUR_Q_KI"
    KP_REG = "CL_CUR_Q_KP"


class PlantOpenLoopJB(BaseOpenLoopPlant):
    """Emulator of a open-loop JB plant."""

    REGISTER_SET_POINT = "CL_CUR_Q_SET_POINT"
    REGISTER_COMMAND = "CL_CUR_Q_VALUE"
    REGISTER_VALUE = "CL_VEL_FBK_VALUE"

    def __init__(self, drive: "VirtualDrive") -> None:
        self.j_value = 0.012
        self.b_value = 0.027
        super().__init__(drive, [1], [self.j_value, self.b_value])


class PlantClosedLoopJB(BaseClosedLoopPlant):
    """Emulator of a closed-loop JB plant."""

    REGISTER_SET_POINT = "CL_VEL_SET_POINT_VALUE"
    REGISTER_COMMAND = "CL_VEL_REF_VALUE"
    REGISTER_VALUE = "CL_VEL_FBK_VALUE"

    KI_REG = "CL_VEL_PID_KI"
    KP_REG = "CL_VEL_PID_KP"


class PlantOpenLoopPosition(BaseOpenLoopPlant):
    """Emulator of a open-loop position plant."""

    REGISTER_SET_POINT = "CL_VEL_SET_POINT_VALUE"
    REGISTER_COMMAND = "CL_VEL_FBK_VALUE"
    REGISTER_VALUE = "CL_POS_FBK_VALUE"

    def __init__(self, drive: "VirtualDrive") -> None:
        pos_to_vel_ratio = int(drive.get_value_by_id(1, "PROF_POS_VEL_RATIO"))
        resolution = int(drive.get_value_by_id(1, "FBK_DIGENC1_RESOLUTION"))
        super().__init__(drive, [pos_to_vel_ratio * resolution], [1, 0])


class PlantClosedLoopPosition(BaseClosedLoopPlant):
    """Emulator of a closed-loop position plant."""

    REGISTER_SET_POINT = "CL_POS_SET_POINT_VALUE"
    REGISTER_COMMAND = "CL_POS_REF_VALUE"
    REGISTER_VALUE = "CL_POS_FBK_VALUE"

    KI_REG = "CL_POS_PID_KI"
    KP_REG = "CL_POS_PID_KP"


class PlantOpenLoopVoltageToVelocity(BaseOpenLoopPlant):
    """Emulator of a open-loop voltage-to-velocity plant."""

    REGISTER_SET_POINT = "CL_VOL_Q_SET_POINT"
    REGISTER_COMMAND = "CL_VOL_Q_REF_VALUE"
    REGISTER_VALUE = "CL_VEL_FBK_VALUE"

    def __init__(
        self,
        drive: "VirtualDrive",
    ) -> None:
        super().__init__(drive, [1.7], [1])


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
        self.remove_data()

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
    def buffer_time(self) -> int:
        """Monitoring buffer size in seconds."""
        return self.buffer_size * self.divider / self.FREQUENCY

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

    def get_channel_index(self, reg_id) -> Optional[int]:
        channel_index = None
        for channel in range(self.number_mapped_registers):
            subnode, address, _, _ = self.get_mapped_register(channel)
            mapped_register = self.drive.get_register(subnode, address)
            if mapped_register.identifier == reg_id:
                channel_index = channel
                break

        return channel_index


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

        # Set monitoring end and frame available
        self.drive.set_value_by_id(0, self.STATUS_REGISTER, 0x10 | (0x8 + 1))
        self.update_data()

    def update_data(self) -> None:

        self.__create_signals()

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
            subnode = self.channels_subnode[channel]
            address = self.channels_address[channel]
            reg = self.drive.get_register(subnode, address)
            if len(reg.signal) > 0:
                indexes = np.arange(0, self.buffer_size * self.divider - 1, self.divider, dtype=int)
                self.channels_signal[channel] = reg.signal[indexes]
                if reg.noise_amplitude > 0:
                    noise = reg.noise_amplitude * np.random.normal(
                        size=self.channels_signal[channel].size
                    )
                    self.channels_signal[channel] = self.channels_signal[channel] + noise
                continue

            start_value = address + subnode
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
                if self.channels_dtype[channel] != REG_DTYPE.FLOAT:
                    value = int(value)
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
        self.start_time = time.time()
        for channel in range(self.number_mapped_registers):
            subnode = self.channels_subnode[channel]
            address = self.channels_address[channel]
            reg = self.drive.get_register(subnode, address)
            reg.time = reg.time + self.start_time
        super().enable()

    def disable(self) -> None:
        self.received_bytes = bytes()
        return super().disable()

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
        for channel in range(self.number_mapped_registers):
            for _ in range(n_samples):
                size = self.channels_size[channel]
                dtype = self.channels_dtype[channel]
                bytes = buffer[:size]
                value = convert_bytes_to_dtype(bytes, dtype)
                if isinstance(value, (int, float)):
                    self.channels_data[channel].append(value)
                buffer = buffer[size:]

            dist_signal = np.array(self.channels_data[channel])
            sampling_rate = self.FREQUENCY / self.drive._disturbance.divider
            total_time = len(dist_signal) / sampling_rate
            time_vector = np.arange(0.0, total_time, 1 / sampling_rate)

            if self.drive._disturbance.divider > 1:
                time_vector_resampled = np.arange(0.0, total_time, 1 / self.FREQUENCY)
                dist_signal = np.interp(time_vector_resampled, time_vector, dist_signal)
                time_vector = time_vector_resampled

            subnode = self.channels_subnode[channel]
            address = self.channels_address[channel]
            reg = self.drive.get_register(subnode, address)

            reg.time = time_vector
            reg.signal = dist_signal

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
        self._monitoring = VirtualMonitoring(self)
        self._disturbance = VirtualDisturbance(self)
        self._plant_open_loop_rl_d = PlantOpenLoopRL(self)
        self._plant_closed_loop_rl_d = PlantClosedLoopRL(self, self._plant_open_loop_rl_d.plant)
        self._plant_open_loop_rl_q = PlantOpenLoopRLQuadrature(self)
        self._plant_closed_loop_rl_q = PlantClosedLoopRLQuadrature(
            self, self._plant_open_loop_rl_q.plant
        )
        self._plant_open_loop_jb = PlantOpenLoopJB(self)
        self._plant_closed_loop_jb = PlantClosedLoopJB(self, self._plant_open_loop_jb.plant)
        self._plant_open_loop_position = PlantOpenLoopPosition(self)
        self._plant_closed_loop_position = PlantClosedLoopPosition(
            self, self._plant_open_loop_position.plant
        )
        self._plant_open_loop_vol_to_vel = PlantOpenLoopVoltageToVelocity(self)
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
                    self.__decode_msg(reg_add, subnode, data)
                    self.set_value_by_id(subnode, str(register.identifier), value)
            elif cmd == self.READ_CMD:
                value = self.get_value_by_id(subnode, str(register.identifier))
                sent_cmd = self.ACK_CMD
                if reg_add == self.id_to_address(0, "MON_DATA") and isinstance(value, bytes):
                    self.__emulate_plants()
                    self._monitoring.update_data()
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
        self._monitoring.disable()

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
        self.set_value_by_id(1, "DRV_PS_FREQ_1", 20000)
        self.set_value_by_id(1, "DRV_STATE_STATUS", constants.IL_MC_PDS_STA_RTSO)
        self.set_value_by_id(1, "DRV_POS_VEL_RATE", 20000)
        self.set_value_by_id(1, "CL_CUR_FREQ", 20000)
        self.set_value_by_id(0, "DIST_MAX_SIZE", 8192)
        self.set_value_by_id(0, "MON_MAX_SIZE", 8192)
        self.set_value_by_id(0, VirtualMonitoring.STATUS_REGISTER, 0)
        self.set_value_by_id(0, VirtualDisturbance.STATUS_REGISTER, 0)
        self.set_value_by_id(1, PlantClosedLoopRL.KI_REG, 2800.0)
        self.set_value_by_id(1, PlantClosedLoopRL.KP_REG, 2.1)
        self.set_value_by_id(1, PlantClosedLoopRLQuadrature.KI_REG, 2800.0)
        self.set_value_by_id(1, PlantClosedLoopRLQuadrature.KP_REG, 2.1)
        self.set_value_by_id(1, PlantClosedLoopJB.KI_REG, 2.0)
        self.set_value_by_id(1, PlantClosedLoopJB.KP_REG, 0.7)
        self.set_value_by_id(1, PlantClosedLoopPosition.KI_REG, 0.0)
        self.set_value_by_id(1, PlantClosedLoopPosition.KP_REG, 0.015)
        self.set_value_by_id(1, "DRV_OP_CMD", 0)
        self.set_value_by_id(1, "FBK_DIGENC1_RESOLUTION", 4096)
        self.set_value_by_id(1, "PROF_POS_VEL_RATIO", 1)
        self.set_value_by_id(1, "MOT_COMMU_MOD", 0)
        self.set_value_by_id(1, "MOT_COMMU_MOD", 0)
        self.set_value_by_id(1, "CL_CUR_REF_MAX", 20)
        self.set_value_by_id(1, "CL_VEL_REF_MAX", 100)
        self.set_value_by_id(1, "MOT_RATED_CURRENT", 10)
        self.set_value_by_id(1, "DRV_PROT_VBUS_VALUE", 48)
        self.set_value_by_id(1, "CL_CUR_STATUS", 0)
        self.set_value_by_id(0, "DRV_DIAG_ERROR_TOTAL_COM", 0)
        self.set_value_by_id(0, "DRV_DIAG_SYS_ERROR_TOTAL_COM", 0)
        self.set_value_by_id(1, "DRV_DIAG_ERROR_TOTAL", 0)
        self.set_value_by_id(1, PlantClosedLoopRL.REGISTER_SET_POINT, 0)
        self.set_value_by_id(1, PlantClosedLoopRL.REGISTER_COMMAND, 0)
        self.set_value_by_id(1, PlantClosedLoopRL.REGISTER_VALUE, 0)
        self.set_value_by_id(1, PlantClosedLoopRLQuadrature.REGISTER_SET_POINT, 0)
        self.set_value_by_id(1, PlantClosedLoopRLQuadrature.REGISTER_COMMAND, 0)
        self.set_value_by_id(1, PlantClosedLoopRLQuadrature.REGISTER_VALUE, 0)
        self.set_value_by_id(1, PlantClosedLoopJB.REGISTER_SET_POINT, 0)
        self.set_value_by_id(1, PlantClosedLoopJB.REGISTER_COMMAND, 0)
        self.set_value_by_id(1, PlantClosedLoopJB.REGISTER_VALUE, 0)
        self.set_value_by_id(1, PlantClosedLoopPosition.REGISTER_SET_POINT, 0)
        self.set_value_by_id(1, PlantClosedLoopPosition.REGISTER_COMMAND, 0)
        self.set_value_by_id(1, PlantClosedLoopPosition.REGISTER_VALUE, 0)
        self.set_value_by_id(1, PlantOpenLoopVoltageToVelocity.REGISTER_SET_POINT, 0)
        self.set_value_by_id(1, PlantOpenLoopVoltageToVelocity.REGISTER_COMMAND, 0)
        self.set_value_by_id(1, PlantOpenLoopVoltageToVelocity.REGISTER_VALUE, 0)
        self.set_value_by_id(1, "CL_VOL_D_SET_POINT", 0)

    def _update_registers(self) -> None:
        """Force storage_valid at each register and add registers that are not in the dictionary."""
        for subnode in range(self.__dictionary.subnodes):
            self.__reg_address_to_id[subnode] = {}
            for reg_id, reg in self.__dictionary.registers(subnode).items():
                self.__reg_address_to_id[subnode][reg.address] = reg_id
                self.__dictionary.registers(subnode)[reg_id].storage_valid = True
                self.__dictionary.registers(subnode)[reg_id].signal = np.array([])
                self.__dictionary.registers(subnode)[reg_id].time = np.array([])
                self.__dictionary.registers(subnode)[reg_id].noise_amplitude = 0.0

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
        # time.sleep(0.01)  # Emulate latency of 10 ms
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
        self._monitoring.available_bytes = len(data_left)
        return response

    def __log(self, ip_port: Tuple[str, int], message: bytes, msg_type: MSG_TYPE) -> None:
        """Updates log.

        Args:
            ip_port: IP address and port.
            message: Received or sent message.
            msg_type: Sent or Received.
        """
        self.__logger.append({
            "timestamp": time.time(),
            "ip_port": ip_port,
            "type": msg_type.value,
            "message": message,
        })

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
            self._monitoring.enable()
        if reg_id == "MON_DIST_ENABLE" and subnode == 0 and value == 0:
            self._monitoring.disable()
        if reg_id == "MON_CMD_FORCE_TRIGGER" and subnode == 0 and value == 1:
            self._monitoring.trigger()
        if reg_id == "MON_REMOVE_DATA" and subnode == 0 and value == 1:
            self._monitoring.remove_data()
        if reg_id == "MON_REARM" and subnode == 0 and value == 1:
            self._monitoring.rearm()
        if reg_id == "DIST_ENABLE" and subnode == 0 and value == 1:
            self._disturbance.enable()
            self.__emulate_plants()
        if reg_id == "DIST_ENABLE" and subnode == 0 and value == 0:
            self._disturbance.disable()
            self.__clean_plant_signals()
        if reg_id == "DIST_REMOVE_DATA" and subnode == 0 and value == 1:
            self._disturbance.remove_data()
        if reg_id == "DIST_DATA" and subnode == 0:
            self._disturbance.append_data(data)
        if (
            reg_id == PlantClosedLoopRL.REGISTER_SET_POINT
            and subnode == 1
            and self.operation_mode in [OperationMode.CURRENT]
        ):
            self._plant_closed_loop_rl_d.jog(value)
        if (
            reg_id == PlantClosedLoopRLQuadrature.REGISTER_SET_POINT
            and subnode == 1
            and self.operation_mode in [OperationMode.CURRENT]
        ):
            self._plant_closed_loop_rl_q.jog(value)
        if (
            reg_id == PlantClosedLoopJB.REGISTER_SET_POINT
            and subnode == 1
            and self.operation_mode in [OperationMode.VELOCITY, OperationMode.PROFILE_VELOCITY]
        ):
            self._plant_closed_loop_jb.jog(value)
        if (
            reg_id == PlantClosedLoopPosition.REGISTER_SET_POINT
            and subnode == 1
            and self.operation_mode
            in [
                OperationMode.POSITION,
                OperationMode.PROFILE_POSITION,
                OperationMode.PROFILE_POSITION_S_CURVE,
            ]
        ):
            self._plant_closed_loop_position.jog(value)
        if (
            reg_id == PlantOpenLoopVoltageToVelocity.REGISTER_SET_POINT
            and subnode == 1
            and self.operation_mode in [OperationMode.VOLTAGE]
        ):
            self._plant_open_loop_vol_to_vel.jog(value)
        if reg_id == "DRV_OP_CMD":
            self.__clean_plant_signals()

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
        if hasattr(register, "signal") and len(register.signal) > 0:
            actual_time = time.time()
            if self._disturbance.enabled:
                time_diff = actual_time - self._disturbance.start_time
                actual_time = self._disturbance.start_time + (
                    time_diff % self._disturbance.buffer_time
                )
            sample_index = np.argmin(np.abs(register.time - actual_time))
            value = register.signal[sample_index]
            if register.noise_amplitude > 0:
                value = value + register.noise_amplitude * np.random.uniform()

            if register.dtype != REG_DTYPE.FLOAT:
                value = int(value)
            return value
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

    def __emulate_plants(self):
        if self.operation_mode == OperationMode.CURRENT:
            self._plant_open_loop_rl_d.emulate_plant()
            self._plant_closed_loop_rl_d.emulate_plant()
            self._plant_open_loop_rl_q.emulate_plant()
            self._plant_closed_loop_rl_q.emulate_plant()
        if self.operation_mode in [
            OperationMode.VELOCITY,
            OperationMode.PROFILE_VELOCITY,
        ]:
            self._plant_open_loop_jb.emulate_plant()
            self._plant_closed_loop_jb.emulate_plant()
        if self.operation_mode in [
            OperationMode.POSITION,
            OperationMode.PROFILE_POSITION,
            OperationMode.PROFILE_POSITION_S_CURVE,
        ]:
            self._plant_open_loop_position.emulate_plant()
            self._plant_closed_loop_position.emulate_plant()

    def __clean_plant_signals(self):
        self._plant_open_loop_jb.clean_signals()
        self._plant_closed_loop_jb.clean_signals()
        self._plant_open_loop_position.clean_signals()
        self._plant_closed_loop_position.clean_signals()
        self._plant_open_loop_rl_d.clean_signals()
        self._plant_open_loop_rl_q.clean_signals()
        self._plant_closed_loop_rl_d.clean_signals()
        self._plant_closed_loop_rl_q.clean_signals()
        self._plant_open_loop_vol_to_vel.clean_signals()

    @property
    def operation_mode(self) -> int:
        """Operation Mode."""
        return self.get_value_by_id(1, "DRV_OP_CMD")

    @property
    def current_loop_rate(self) -> int:
        """Current loop rate."""
        return self.get_value_by_id(1, "CL_CUR_FREQ")
