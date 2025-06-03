import os
import pathlib
import platform
import socket
import time
import typing
from enum import Enum, IntEnum
from functools import cached_property
from threading import Thread, Timer
from typing import TYPE_CHECKING, Any, Optional, Union

import numpy as np
from numpy.typing import NDArray
from scipy import signal
from typing_extensions import override

from ingenialink.configuration_file import ConfigurationFile
from ingenialink.constants import ETH_BUF_SIZE, MONITORING_BUFFER_SIZE
from ingenialink.dictionary import DictionaryV3, Interface
from ingenialink.enums.register import RegAccess, RegDtype
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.ethernet.servo import EthernetServo
from ingenialink.servo import DictionaryFactory
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes
from ingenialink.utils.mcb import MCB
from ingenialink.virtual.dictionary import VirtualDictionary
from virtual_drive import constants

from .environment import Environment
from .gpios import Gpios

if TYPE_CHECKING:
    from .signals import Signal

R_VALUE = 1.1
L_VALUE = 3.9e-4
J_VALUE = 0.012
B_VALUE = 0.027
TORQUE_CONSTANT = 0.05

STATUS_WORD_COMMUTATION_FEEDBACK_ALIGNED_BIT = 0x4000

INC_ENC1_RESOLUTION = 4096
INC_ENC2_RESOLUTION = 2000


class MsgType(Enum):
    """Message type enum."""

    RECEIVED = "RECEIVED"
    SENT = "SENT"


class OperationMode(IntEnum):
    """Operation Mode Enum."""

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


class PhasingMode(IntEnum):
    """Phasing modes."""

    NON_FORCED = 0
    """Non forced"""
    FORCED = 1
    """Forced"""
    NO_PHASING = 2
    """No phasing"""


class SensorType(IntEnum):
    """Summit series feedback type enum."""

    ABS1 = 1
    """Absolute encoder 1"""
    INTGEN = 3
    """Internal generator"""
    QEI = 4
    """Digital/Incremental encoder 1"""
    HALLS = 5
    """Digital halls"""
    SSI2 = 6
    """Secondary SSI"""
    BISSC2 = 7
    """Absolute encoder 2"""
    QEI2 = 8
    """Digital/Incremental encoder 2"""
    SINCOS = 10
    """SinCos encoder 1"""


class GeneratorMode(IntEnum):
    """Generator modes."""

    CONSTANT = 0
    """Constant"""
    SAW_TOOTH = 1
    """Saw tooth"""
    SQUARE = 2
    """Square"""


class BasePlant:
    """Base class for open-loop and closed-loop plants.

    Args:
        drive: Instance of VirtualDrive.

    Attributes:
        drive: Instance of VirtualDrive.
        plant: Plant's discrete transfer function.
        monitoring_frequency: Monitoring frequency
        set_point_register: Set-point register.
        command_register: Command register.
        value_register: Value register.
    """

    REGISTER_SET_POINT: str
    """Register of the set-point signal."""
    REGISTER_COMMAND: str
    """Register of the command signal."""
    REGISTER_VALUE: str
    """Register of the value (output) signal."""

    def __init__(self, drive: "VirtualDrive") -> None:
        self.drive = drive
        self.monitoring_frequency = VirtualMonitoring.FREQUENCY
        self.plant: signal.TransferFunction
        self.set_point_register = self.drive.get_register(1, register_id=self.REGISTER_SET_POINT)
        self.command_register = self.drive.get_register(1, register_id=self.REGISTER_COMMAND)
        self.value_register = self.drive.get_register(1, register_id=self.REGISTER_VALUE)

    def emulate_plant(self, from_disturbance: bool = True) -> None:
        """Emulate the plant by filtering the excitation signal with the plant's frequency response.

        Args:
            from_disturbance: If True the input signal is repeated to fit the monitoring window.
        """
        dist_signal = self.drive.reg_signals[self.REGISTER_SET_POINT]
        if len(dist_signal) == 0:
            return

        if from_disturbance and self.drive._monitoring:
            monitoring_size = self.drive._monitoring.buffer_size * self.drive._monitoring.divider
            if monitoring_size > len(dist_signal):
                repetitions = monitoring_size // len(dist_signal) + 1
                dist_signal = np.tile(dist_signal, repetitions)

        initial_value = (
            self.set_point_register.storage if self.set_point_register.storage > 0 else 0
        )
        use_fft_method = self.value_register.dtype == RegDtype.FLOAT
        mon_signal = self._filter_signal(
            dist_signal, use_fft_method=use_fft_method, initial_value=initial_value
        )

        self.drive.reg_signals[self.REGISTER_COMMAND] = dist_signal
        self.drive.reg_time[self.REGISTER_COMMAND] = self.drive.reg_time[self.REGISTER_SET_POINT]
        self.drive.reg_signals[self.REGISTER_VALUE] = mon_signal
        self.drive.reg_time[self.REGISTER_VALUE] = self.drive.reg_time[self.REGISTER_SET_POINT]

    def _filter_signal(
        self,
        input_signal: NDArray[np.float64],
        use_fft_method: bool = True,
        initial_value: float = 0.0,
        plant: Optional[signal.TransferFunction] = None,
    ) -> NDArray[np.float64]:
        """Filter signal with the plant's frequency response.

        Args:
            input_signal: Signal to be filtered.
            use_fft_method: If True the FFT method is used.
            initial_value: Initial value.
            plant: Plant's transfer function.

        Returns:
            Filtered signal.
        """
        output_signal: NDArray[np.float64]
        plant = plant or self.plant
        if len(plant.num) == 1 and len(plant.den) == 1:
            gain = plant.num[0] / plant.den[0]
            output_signal = input_signal * gain
        if use_fft_method:
            input_signal_fft = np.fft.fft(input_signal)
            _, freq_response = signal.freqz(
                plant.num, plant.den, worN=len(input_signal), whole=True
            )
            output_signal_fft = input_signal_fft * freq_response
            output_signal = np.real(np.fft.ifft(output_signal_fft))
        else:
            initial_x = [initial_value] * (len(plant.num) - 1)
            initial_y = [initial_value] * (len(plant.den) - 1)
            zi = signal.lfiltic(plant.num, plant.den, initial_y, x=initial_x)
            output_signal, _ = signal.lfilter(plant.num, plant.den, input_signal, zi=zi)

        return output_signal

    def jog(self, new_value: Union[int, float]) -> None:
        """Emulate jogs by disturbing the input register using a step signal.

        Args:
            new_value: Target value.
        """
        if not self.drive.enabled:
            return
        time_of_change = time.time()
        start_time = time_of_change - 1
        end_time = start_time + 5
        time_vector = np.arange(start_time, end_time, 1 / self.drive.current_loop_rate)
        index_change = int(np.argmin(np.abs(time_vector - time_of_change)))
        jog_signal = np.zeros(len(time_vector))
        current_value = self.set_point_register.storage
        jog_signal[:index_change] = current_value
        jog_signal[index_change:] = new_value
        self.drive.reg_signals[self.REGISTER_SET_POINT] = jog_signal
        self.drive.reg_time[self.REGISTER_SET_POINT] = time_vector
        self.emulate_plant(from_disturbance=False)

    def clean_signals(self) -> None:
        """Clean all signals."""
        self.drive.reg_time[self.REGISTER_COMMAND] = np.array([])
        self.drive.reg_signals[self.REGISTER_COMMAND] = np.array([])
        self.drive.reg_time[self.REGISTER_VALUE] = np.array([])
        self.drive.reg_signals[self.REGISTER_VALUE] = np.array([])
        self.drive.reg_time[self.REGISTER_SET_POINT] = np.array([])
        self.drive.reg_signals[self.REGISTER_SET_POINT] = np.array([])


class BaseOpenLoopPlant(BasePlant):
    """Base class for open-loop plants.

    Args:
        drive: Instance of VirtualDrive.
        num: Numerator of the continuos transfer function.
        den: Denominator of the continuos transfer function.

    Attributes:
        drive: Instance of VirtualDrive.
        plant: Plant's discrete transfer function.
    """

    def __init__(self, drive: "VirtualDrive", num: list[float], den: list[float]) -> None:
        super().__init__(drive)
        self.plant = signal.TransferFunction(num, den).to_discrete(dt=1 / self.monitoring_frequency)
        self.drive.reg_noise_amplitude[self.REGISTER_VALUE] = 0.01


class BaseClosedLoopPlant(BasePlant):
    """Base class for closed-loop plants.

    Args:
        drive: Instance of VirtualDrive.
        open_loop_plant: Open-loop plant's discrete transfer function.

    Attributes:
        drive: Instance of VirtualDrive.
        open_loop_plant: Open-loop plant's discrete transfer function.
        plant: Closed-loop plant's discrete transfer function.
    """

    KI_REG: str
    """Register containing the Ki value."""
    KP_REG: str
    """Register containing the Kp value."""

    TUNING_OPERATION_MODE: Optional[OperationMode] = None
    """Operation mode used for tuning."""
    OL_PLANT_INPUT: str
    """Register of the open-loop plant's input."""

    def __init__(self, drive: "VirtualDrive", open_loop_plant: signal.TransferFunction) -> None:
        super().__init__(drive)
        self.open_loop_plant = open_loop_plant
        self.create_closed_loop_plant()

    def create_closed_loop_plant(self) -> None:
        """Create the closed-loop plant."""
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

    @override
    def emulate_plant(self, from_disturbance: bool = True) -> None:
        self.create_closed_loop_plant()
        super().emulate_plant(from_disturbance=from_disturbance)
        self.__obtain_command_signal()

    def __obtain_command_signal(self) -> None:
        """Obtain command signal from the output by applying the inverse of the open-loop plant."""
        if not (
            self.TUNING_OPERATION_MODE is not None
            and self.drive.operation_mode == self.TUNING_OPERATION_MODE
            and len(self.drive.reg_signals[self.REGISTER_VALUE]) > 0
        ):
            return
        output_signal = self.drive.reg_signals[self.REGISTER_VALUE]
        inverse_open_loop = signal.TransferFunction(
            self.open_loop_plant.den, self.open_loop_plant.num, dt=self.open_loop_plant.dt
        )
        command_value = self._filter_signal(
            output_signal,
            use_fft_method=False,
            initial_value=output_signal[0],
            plant=inverse_open_loop,
        )
        self.drive.reg_signals[self.OL_PLANT_INPUT] = command_value
        self.drive.reg_time[self.OL_PLANT_INPUT] = self.drive.reg_time[self.REGISTER_VALUE]
        self.drive.reg_noise_amplitude[self.OL_PLANT_INPUT] = self.drive.reg_noise_amplitude[
            self.REGISTER_VALUE
        ]

    @property
    def kp(self) -> float:
        """Return Kp value.

        Returns:
            Kp value.
        """
        return float(self.drive.get_value_by_id(1, self.KP_REG))

    @property
    def ki(self) -> float:
        """Return Ki value.

        Returns:
            Ki value.
        """
        return float(self.drive.get_value_by_id(1, self.KI_REG))


class PlantOpenLoopRL(BaseOpenLoopPlant):
    """Emulator of a open-loop RL plant."""

    REGISTER_SET_POINT = "CL_VOL_D_SET_POINT"
    REGISTER_COMMAND = "CL_VOL_D_CMD"
    REGISTER_VALUE = "CL_CUR_D_VALUE"

    def __init__(self, drive: "VirtualDrive") -> None:
        self.l_henry = L_VALUE
        self.r_ohm = R_VALUE
        super().__init__(drive, [1], [self.l_henry, self.r_ohm])


class PlantClosedLoopRL(BaseClosedLoopPlant):
    """Emulator of a closed-loop RL plant."""

    REGISTER_SET_POINT = "CL_CUR_D_SET_POINT"
    REGISTER_COMMAND = "CL_CUR_D_REF_VALUE"
    REGISTER_VALUE = "CL_CUR_D_VALUE"

    KI_REG = "CL_CUR_D_KI"
    KP_REG = "CL_CUR_D_KP"

    TUNING_OPERATION_MODE = OperationMode.CURRENT
    OL_PLANT_INPUT = PlantOpenLoopRL.REGISTER_COMMAND

    @override
    def emulate_plant(self, from_disturbance: bool = True) -> None:
        super().emulate_plant(from_disturbance)


class PlantOpenLoopRLQuadrature(BaseOpenLoopPlant):
    """Emulator of a open-loop RL quadrature plant."""

    REGISTER_SET_POINT = "CL_VOL_Q_SET_POINT"
    REGISTER_COMMAND = "CL_VOL_Q_CMD"
    REGISTER_VALUE = "CL_CUR_Q_VALUE"

    def __init__(self, drive: "VirtualDrive") -> None:
        self.l_henry = L_VALUE
        self.r_ohm = R_VALUE
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
        self.j_value = J_VALUE
        self.b_value = B_VALUE
        super().__init__(drive, [1], [self.j_value, self.b_value])


class PlantClosedLoopJB(BaseClosedLoopPlant):
    """Emulator of a closed-loop JB plant."""

    REGISTER_SET_POINT = "CL_VEL_SET_POINT_VALUE"
    REGISTER_COMMAND = "CL_VEL_REF_VALUE"
    REGISTER_VALUE = "CL_VEL_FBK_VALUE"

    KI_REG = "CL_VEL_PID_KI"
    KP_REG = "CL_VEL_PID_KP"

    TUNING_OPERATION_MODE = OperationMode.PROFILE_VELOCITY
    OL_PLANT_INPUT = "CL_CUR_Q_CMD_VALUE"


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

    TUNING_OPERATION_MODE = OperationMode.PROFILE_POSITION_S_CURVE
    OL_PLANT_INPUT = "CL_VEL_CMD_VALUE"


class PlantOpenLoopVoltageToVelocity(BaseOpenLoopPlant):
    """Emulator of a open-loop voltage-to-velocity plant."""

    REGISTER_SET_POINT = "CL_VOL_Q_SET_POINT"
    REGISTER_COMMAND = "CL_VOL_Q_REF_VALUE"
    REGISTER_VALUE = "CL_VEL_FBK_VALUE"

    def __init__(
        self,
        drive: "VirtualDrive",
    ) -> None:
        self.gain = TORQUE_CONSTANT / (R_VALUE * B_VALUE)
        super().__init__(drive, [self.gain], [1])
        self.plant = signal.TransferFunction([self.gain], [1], dt=1 / self.monitoring_frequency)


class PlantOpenLoopVoltageToCurrentA(PlantOpenLoopRL):
    """Emulator of a open-loop voltage-to-current (A) plant."""

    REGISTER_SET_POINT = "CL_VOL_D_SET_POINT"
    REGISTER_COMMAND = "CL_VOL_D_REF_VALUE"
    REGISTER_VALUE = "FBK_CUR_A_VALUE"


class PlantOpenLoopVoltageToCurrentB(PlantOpenLoopVoltageToCurrentA):
    """Emulator of a open-loop voltage-to-current (B) plant."""

    REGISTER_VALUE = "FBK_CUR_B_VALUE"


class PlantOpenLoopVoltageToCurrentC(PlantOpenLoopVoltageToCurrentA):
    """Emulator of a open-loop voltage-to-current (C) plant."""

    REGISTER_VALUE = "FBK_CUR_C_VALUE"


class VirtualPhasing:
    """Mock of the phasing calibration.

    Args:
        drive: Instance of the VirtualDrive.
    """

    PHASING_MODE_REGISTER = "COMMU_PHASING_MODE"
    PHASING_CURRENT_REGISTER = "COMMU_PHASING_MAX_CURRENT"
    PHASING_TIMEOUT_REGISTER = "COMMU_PHASING_TIMEOUT"
    PHASING_ACCURACY_REGISTER = "COMMU_PHASING_ACCURACY"

    REFERENCE_ANGLE_VALUE_REGISTER = "COMMU_ANGLE_REF_VALUE"
    COMMUTATION_ANGLE_VALUE_REGISTER = "COMMU_ANGLE_VALUE"
    REFERENCE_ANGLE_OFFSET_REGISTER = "COMMU_ANGLE_REF_OFFSET"
    COMMUTATION_ANGLE_OFFSET_REGISTER = "COMMU_ANGLE_OFFSET"

    REFERENCE_FEEDBACK_SENSOR = "COMMU_ANGLE_REF_SENSOR"

    CURRENT_CMD_VALUE_REGISTER = "CL_CUR_CMD_VALUE"
    CURRENT_ACTUAL_VALUE_REGISTER = "FBK_CUR_MODULE_VALUE"

    SETUP_TIME = 1.0
    INITIAL_ANGLE = 180.0
    INITIAL_ANGLE_HALLS = 240.0
    SAMPLING_RATE = 100

    def __init__(self, drive: "VirtualDrive") -> None:
        self.drive = drive
        self.start_time = 0.0
        self.phased = False
        self.drive.reg_signals[self.REFERENCE_ANGLE_VALUE_REGISTER] = (
            np.ones(1) * self.reference_angle_offset
        )
        self.drive.reg_time[self.REFERENCE_ANGLE_VALUE_REGISTER] = np.zeros(1)
        self.drive.reg_signals[self.COMMUTATION_ANGLE_VALUE_REGISTER] = (
            np.ones(1) * self.commutation_angle_offset
        )
        self.drive.reg_time[self.COMMUTATION_ANGLE_VALUE_REGISTER] = np.zeros(1)
        self.drive.reg_signals[self.CURRENT_CMD_VALUE_REGISTER] = np.zeros(1)
        self.drive.reg_time[self.CURRENT_CMD_VALUE_REGISTER] = np.zeros(1)
        self.drive.reg_signals[self.CURRENT_ACTUAL_VALUE_REGISTER] = np.zeros(1)
        self.drive.reg_time[self.CURRENT_ACTUAL_VALUE_REGISTER] = np.zeros(1)
        self.drive.reg_noise_amplitude[self.CURRENT_ACTUAL_VALUE_REGISTER] = 0.01

    def enable(self) -> None:
        """Enable phasing and create signals."""
        if self.phasing_mode != PhasingMode.FORCED or self.phasing_bit:
            return
        self.start_time = time.time()
        period = self.SETUP_TIME + self.phasing_steps * self.phasing_timeout
        n_samples = int(self.SAMPLING_RATE * period)
        time_vector = self.start_time - self.SETUP_TIME + np.linspace(0, period, n_samples)

        setup_ix = int(self.SETUP_TIME * self.SAMPLING_RATE)
        step_samples = int(self.phasing_timeout * self.SAMPLING_RATE)

        commutation_signal = np.zeros(n_samples)
        commutation_signal[:setup_ix] = self.commutation_angle_offset
        commutation_signal[setup_ix:] = 0.0

        reference_signal = np.zeros(n_samples)
        reference_signal[:setup_ix] = self.commutation_angle_offset
        initial_angle_rev = self.initial_angle / 360
        actual_angle_rev = initial_angle_rev
        for step in range(self.phasing_steps):
            step_ix = step * step_samples + setup_ix
            reference_signal[step_ix : step_ix + step_samples] = actual_angle_rev
            actual_angle_rev += (1 - actual_angle_rev) / 2

        current_signal = np.zeros(n_samples)
        current_signal[:setup_ix] = 0.0
        current_signal[setup_ix : step_samples + setup_ix] = np.linspace(
            0, self.phasing_current, step_samples
        )
        current_signal[step_samples + setup_ix :] = self.phasing_current

        self.drive.reg_signals[self.REFERENCE_ANGLE_VALUE_REGISTER] = reference_signal
        self.drive.reg_time[self.REFERENCE_ANGLE_VALUE_REGISTER] = time_vector
        self.drive.reg_signals[self.COMMUTATION_ANGLE_VALUE_REGISTER] = commutation_signal
        self.drive.reg_time[self.COMMUTATION_ANGLE_VALUE_REGISTER] = time_vector
        self.drive.reg_signals[self.CURRENT_CMD_VALUE_REGISTER] = current_signal
        self.drive.reg_time[self.CURRENT_CMD_VALUE_REGISTER] = time_vector
        self.drive.reg_signals[self.CURRENT_ACTUAL_VALUE_REGISTER] = current_signal
        self.drive.reg_time[self.CURRENT_ACTUAL_VALUE_REGISTER] = time_vector

        self.phased = True
        Timer(
            self.phasing_steps * self.phasing_timeout,
            self.set_phasing_bit,
            args=(reference_signal[-1],),
        ).start()

    @property
    def phasing_steps(self) -> int:
        """Phasing steps."""
        delta = 3 * self.phasing_accuracy / 1000

        actual_angle = self.initial_angle
        num_of_steps = 1
        while actual_angle > delta:
            actual_angle = actual_angle / 2
            num_of_steps += 1
        return num_of_steps

    def set_phasing_bit(self, new_offset: Optional[float] = None) -> None:
        """Set the phasing bit.

        Args:
            new_offset: New offset to be set.
        """
        if not self.phased:
            return
        new_status_word = self.drive.status_word | STATUS_WORD_COMMUTATION_FEEDBACK_ALIGNED_BIT
        self.drive.status_word = new_status_word
        if new_offset:
            self.reference_angle_offset = new_offset
            self.commutation_angle_offset = new_offset

    def clear_phasing_bit(self) -> None:
        """Clear phasing bit."""
        new_status_word = self.drive.status_word & ~STATUS_WORD_COMMUTATION_FEEDBACK_ALIGNED_BIT
        self.drive.status_word = new_status_word

    @property
    def phasing_bit(self) -> bool:
        """Phasing bit."""
        phasing_bit = self.drive.status_word & STATUS_WORD_COMMUTATION_FEEDBACK_ALIGNED_BIT
        return bool(phasing_bit)

    @property
    def phasing_mode(self) -> int:
        """Phasing mode."""
        return int(self.drive.get_value_by_id(1, self.PHASING_MODE_REGISTER))

    @property
    def phasing_current(self) -> int:
        """Phasing max current."""
        return int(self.drive.get_value_by_id(1, self.PHASING_CURRENT_REGISTER))

    @property
    def phasing_timeout(self) -> float:
        """Phasing timeout."""
        return float(self.drive.get_value_by_id(1, self.PHASING_TIMEOUT_REGISTER)) / 1000

    @property
    def phasing_accuracy(self) -> int:
        """Phasing accuracy."""
        return int(self.drive.get_value_by_id(1, self.PHASING_ACCURACY_REGISTER))

    @property
    def reference_feedback(self) -> int:
        """Reference feedback sensor."""
        return int(self.drive.get_value_by_id(1, self.REFERENCE_FEEDBACK_SENSOR))

    @property
    def reference_angle_offset(self) -> float:
        """Reference angle offset."""
        return float(self.drive.get_value_by_id(1, self.REFERENCE_ANGLE_OFFSET_REGISTER))

    @reference_angle_offset.setter
    def reference_angle_offset(self, value: float) -> None:
        self.drive.set_value_by_id(1, self.REFERENCE_ANGLE_OFFSET_REGISTER, value)

    @property
    def commutation_angle_offset(self) -> float:
        """Commutation angle offset."""
        return float(self.drive.get_value_by_id(1, self.COMMUTATION_ANGLE_OFFSET_REGISTER))

    @commutation_angle_offset.setter
    def commutation_angle_offset(self, value: float) -> None:
        self.drive.set_value_by_id(1, self.COMMUTATION_ANGLE_OFFSET_REGISTER, value)

    @property
    def initial_angle(self) -> float:
        """Initial angle."""
        if self.reference_feedback == SensorType.HALLS:
            return self.INITIAL_ANGLE_HALLS
        else:
            return self.INITIAL_ANGLE


class VirtualInternalGenerator:
    """Emulate the virtual generator with the only purpose of mocking the feedback tests.

    Args:
        drive: Instance of VirtualDrive.
    """

    MODE_REGISTER = "FBK_GEN_MODE"
    FREQUENCY_REGISTER = "FBK_GEN_FREQ"
    GAIN_REGISTER = "FBK_GEN_GAIN"
    OFFSET_REGISTER = "FBK_GEN_OFFSET"
    CYCLE_NUMBER_REGISTER = "FBK_GEN_CYCLES"
    REARM_REGISTER = "FBK_GEN_REARM"

    ACTUAL_POSITION_REGISTER = "CL_POS_FBK_VALUE"
    POLE_PAIRS_REGISTER = "MOT_PAIR_POLES"
    DIG_HALL_POLE_PAIRS_REGISTER = "FBK_DIGHALL_PAIRPOLES"
    ABS1_ST_BITS_REGISTER = "FBK_BISS1_SSI1_POS_ST_BITS"
    ABS2_ST_BITS_REGISTER = "FBK_BISS2_POS_ST_BITS"
    COMMUTATION_FEEDBACK_REGISTER = "COMMU_ANGLE_SENSOR"
    POSITION_FEEDBACK_REGISTER = "CL_POS_FBK_SENSOR"
    SINCOS_MULTIPLIER_FACTOR_REGISTER = "FBK_SINCOS_MULT_FACTOR"
    SINCOS_RESOLUTION_REGISTER = "FBK_SINCOS_RESOLUTION"

    HALL_VALUES = (1, 3, 2, 6, 4, 5)

    def __init__(self, drive: "VirtualDrive") -> None:
        self.drive = drive
        self.start_time = 0.0

    @cached_property
    def encoder_registers(self) -> dict[SensorType, str]:
        """Encoder register associated with a sensor type."""
        return {
            SensorType.QEI: "FBK_DIGENC1_VALUE",
            SensorType.QEI2: "FBK_DIGENC2_VALUE",
            SensorType.HALLS: "FBK_DIGHALL_VALUE",
            SensorType.ABS1: "FBK_BISS1_SSI1_POS_VALUE",
            SensorType.BISSC2: "FBK_BISS2_POS_VALUE",
            SensorType.SINCOS: "FBK_SINCOS_VALUE",
        }

    def enable(self) -> None:
        """Enable internal generator and generate the encoder and position signals."""
        self.start_time = time.time()
        if (
            self.commutation_feedback != SensorType.INTGEN
            or self.generator_mode != GeneratorMode.SAW_TOOTH
            or self.position_encoder not in self.encoder_registers
        ):
            return
        if self.position_encoder == SensorType.HALLS:
            pole_pairs = self.drive.get_value_by_id(1, self.POLE_PAIRS_REGISTER)
            self.drive.set_value_by_id(1, self.DIG_HALL_POLE_PAIRS_REGISTER, pole_pairs)

        period = 1 / self.frequency
        n_samples = int(VirtualMonitoring.FREQUENCY * period * self.cycles)
        time_vector = self.start_time + np.linspace(0, period * self.cycles, n_samples)

        signal_period: NDArray[np.float64] = self.offset + np.linspace(
            0, self.gain, int(n_samples / self.cycles), dtype=np.float64
        )
        pos_signal = np.tile(signal_period, self.cycles)
        initial_value = self.drive.get_value_by_id(1, self.ACTUAL_POSITION_REGISTER)
        pos_signal = initial_value + (pos_signal - pos_signal[0]) * self.encoder_resolution
        pos_signal = pos_signal.astype(int)

        if self.position_encoder == SensorType.HALLS:
            encoder_signal = self.__create_halls_encoder_signal(pos_signal)
        elif self.position_encoder in [SensorType.ABS1, SensorType.BISSC2]:
            encoder_signal = self.__create_abs_encoder_signal(pos_signal)
        else:
            encoder_signal = pos_signal.copy()

        self.drive.reg_signals[self.encoder_register] = encoder_signal
        self.drive.reg_time[self.encoder_register] = time_vector
        self.drive.reg_signals[self.ACTUAL_POSITION_REGISTER] = pos_signal
        self.drive.reg_time[self.ACTUAL_POSITION_REGISTER] = time_vector

    def __create_halls_encoder_signal(self, pos_signal: NDArray[np.float64]) -> NDArray[np.float64]:
        """Create the halls encoder signal by discretizing the pos_signal using the hall values.

        Args:
            pos_signal: Position signal.

        Returns:
            Encoder signal.

        """
        encoder_signal = pos_signal.copy()
        encoder_signal[0] = self.drive.get_value_by_id(1, self.encoder_register)
        hall_value_ix = self.HALL_VALUES.index(encoder_signal[0])
        for sample_ix in range(1, len(encoder_signal)):
            hall_change = 0
            if (pos_signal[sample_ix] - pos_signal[sample_ix - 1]) > 0:
                hall_change = 1
            elif (pos_signal[sample_ix] - pos_signal[sample_ix - 1]) < 0:
                hall_change = -1
            else:
                hall_change = 0
            hall_value_ix = (hall_value_ix + hall_change) % len(self.HALL_VALUES)
            encoder_signal[sample_ix] = self.HALL_VALUES[hall_value_ix]
        return encoder_signal

    def __create_abs_encoder_signal(self, pos_signal: NDArray[np.float64]) -> NDArray[np.float64]:
        """Crete the absolute encoder signal by saturating the position signal.

        Args:
            pos_signal: Position signal.

        Returns:
            Encoder signal.
        """
        encoder_signal = pos_signal.copy()
        for sample_ix in range(1, len(encoder_signal)):
            if encoder_signal[sample_ix] > self.encoder_resolution - 1:
                encoder_signal[sample_ix:] = encoder_signal[sample_ix:] - self.encoder_resolution
            elif encoder_signal[sample_ix] < 0:
                encoder_signal[sample_ix:] = encoder_signal[sample_ix:] + self.encoder_resolution
        return encoder_signal

    @property
    def encoder_register(self) -> str:
        """Register of the encoder value."""
        return self.encoder_registers[SensorType(self.position_encoder)]

    @property
    def encoder_resolution(self) -> int:
        """Encoder resolution."""
        if self.position_encoder == SensorType.QEI:
            return INC_ENC1_RESOLUTION
        elif self.position_encoder == SensorType.QEI2:
            return INC_ENC2_RESOLUTION
        elif self.position_encoder == SensorType.HALLS:
            pole_pairs = int(self.drive.get_value_by_id(1, self.DIG_HALL_POLE_PAIRS_REGISTER))
            return pole_pairs * len(self.HALL_VALUES)
        elif self.position_encoder == SensorType.ABS1:
            single_turn_bits = int(self.drive.get_value_by_id(1, self.ABS1_ST_BITS_REGISTER))
            return int(2**single_turn_bits)
        elif self.position_encoder == SensorType.BISSC2:
            single_turn_bits = int(self.drive.get_value_by_id(1, self.ABS2_ST_BITS_REGISTER))
            return int(2**single_turn_bits)
        elif self.position_encoder == SensorType.SINCOS:
            sincos_resolution = int(self.drive.get_value_by_id(1, self.SINCOS_RESOLUTION_REGISTER))
            multiplier_reg_value = int(
                self.drive.get_value_by_id(1, self.SINCOS_MULTIPLIER_FACTOR_REGISTER)
            )
            multiplier_factor = typing.cast("int", 2**multiplier_reg_value)
            return sincos_resolution * multiplier_factor
        else:
            return 1

    @property
    def position_encoder(self) -> int:
        """Position encoder."""
        return int(self.drive.get_value_by_id(1, self.POSITION_FEEDBACK_REGISTER))

    @property
    def generator_mode(self) -> int:
        """Generator mode."""
        return int(self.drive.get_value_by_id(1, self.MODE_REGISTER))

    @property
    def commutation_feedback(self) -> int:
        """Commutation feedback sensor."""
        return int(self.drive.get_value_by_id(1, self.COMMUTATION_FEEDBACK_REGISTER))

    @property
    def frequency(self) -> float:
        """Internal generator frequency."""
        return float(self.drive.get_value_by_id(1, self.FREQUENCY_REGISTER))

    @property
    def offset(self) -> float:
        """Internal generator offset."""
        return float(self.drive.get_value_by_id(1, self.OFFSET_REGISTER))

    @property
    def gain(self) -> float:
        """Internal generator gain."""
        return float(self.drive.get_value_by_id(1, self.GAIN_REGISTER))

    @property
    def cycles(self) -> int:
        """Internal generator cycles."""
        return int(self.drive.get_value_by_id(1, self.CYCLE_NUMBER_REGISTER))


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
        self.channels_data: dict[int, NDArray[np.float64]] = {}
        self.channels_dtype: dict[int, RegDtype] = {}
        self.channels_address: dict[int, int] = {}
        self.channels_subnode: dict[int, int] = {}
        self.channels_size: dict[int, int] = {}
        self.channels_signal: dict[int, NDArray[np.float64]] = {}

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
        self.drive.set_value_by_id(0, self.DATA_REG, bytes(1))

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
    def buffer_time(self) -> float:
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

    def get_mapped_register(self, channel: int) -> tuple[int, int, int, int]:
        """Decodes the register with the information of a mapped register.

        Args:
            channel: Channel of the register to be decoded.

        Raises:
            ValueError: if the register has a wrong type.

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
        for channel in range(self.number_mapped_registers):
            subnode, address, dtype, size = self.get_mapped_register(channel)
            self.channels_data[channel] = np.array([])
            self.channels_dtype[channel] = RegDtype(dtype)
            self.channels_address[channel] = address
            self.channels_subnode[channel] = subnode
            self.channels_size[channel] = size
            self.channels_signal[channel] = np.array([])
            self.bytes_per_block += size

    def get_channel_index(self, reg_id: str) -> Optional[int]:
        """Return the channel index of a mapped register.

        If the register is not mapped returns None.

        Args:
            reg_id: Register ID.

        Returns:
            Channel index. None if the register is not mapped.
        """
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
    DATA_REG = "MON_DATA_VALUE"
    TRIGGER_TYPE_REG = "MON_CFG_SOC_TYPE"
    AVAILABLE_BYTES_REG = "MON_CFG_BYTES_VALUE"
    STATUS_REGISTER = "MON_DIST_STATUS"

    def __init__(self, drive: "VirtualDrive") -> None:
        self.start_time = 0.0
        super().__init__(drive)

    @override
    def enable(self) -> None:
        super().map_registers()
        super().enable()

        # Set monitoring end and frame available
        self.drive.set_value_by_id(0, self.STATUS_REGISTER, 0x10 | (0x8 + 1))
        self.update_data()

    def update_data(self) -> None:
        """Update the monitoring data."""
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
            reg_id = self.drive.address_to_id(subnode, address)
            if len(self.drive.reg_signals[reg_id]) > 0:
                self.channels_signal[channel] = self.drive.reg_signals[reg_id]
                if self.divider > 1:
                    indexes = np.arange(
                        0, self.buffer_size * self.divider - 1, self.divider, dtype=int
                    )
                    self.channels_signal[channel] = self.channels_signal[channel][indexes]
                if self.drive.reg_noise_amplitude[reg_id] > 0:
                    rng = np.random.default_rng()
                    noise = self.drive.reg_noise_amplitude[reg_id] * rng.normal(
                        size=len(self.channels_signal[channel])
                    )
                    self.channels_signal[channel] = self.channels_signal[channel] + noise
                continue

            start_value = address + subnode
            if self.channels_dtype[channel] == RegDtype.FLOAT:
                signal = [
                    float(start_value + i)
                    for i in range(0, self.buffer_size * self.divider, self.divider)
                ]
            else:
                signal = [
                    start_value + i for i in range(0, self.buffer_size * self.divider, self.divider)
                ]
            self.channels_signal[channel] = np.array(signal)

    def _store_data_bytes(self) -> None:
        """Convert signals into a bytes and store it at MON_DATA register."""
        byte_array = b""
        n_samples = len(self.channels_data[0])
        for sample in range(n_samples):
            for channel in range(self.number_mapped_registers):
                value = self.channels_data[channel][sample]
                size = self.channels_size[channel]
                if self.channels_dtype[channel] != RegDtype.FLOAT:
                    value = int(value)
                sample_bytes = convert_dtype_to_bytes(value, self.channels_dtype[channel])
                if len(sample_bytes) < size:
                    sample_bytes += b"0" * (size - len(sample_bytes))
                byte_array += sample_bytes
        self.drive.set_value_by_id(0, self.DATA_REG, byte_array)

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
    DATA_REG = "DIST_DATA_VALUE"
    STATUS_REGISTER = "DIST_STATUS"

    def __init__(self, drive: "VirtualDrive") -> None:
        self.start_time = 0.0
        self.received_bytes = b""
        super().__init__(drive)

    @override
    def enable(self) -> None:
        self.start_time = time.time()
        for channel in range(self.number_mapped_registers):
            subnode = self.channels_subnode[channel]
            address = self.channels_address[channel]
            reg = self.drive.get_register(subnode, address)
            self.drive.reg_time[str(reg.identifier)] += self.start_time
        super().enable()

    @override
    def disable(self) -> None:
        self.received_bytes = b""
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
                data_bytes = buffer[:size]
                value = convert_bytes_to_dtype(data_bytes, dtype)
                if isinstance(value, (int, float)):
                    self.channels_data[channel] = np.append(self.channels_data[channel], value)
                buffer = buffer[size:]

            dist_signal = np.array(self.channels_data[channel])
            sampling_rate = self.FREQUENCY / self.divider
            total_time = len(dist_signal) / sampling_rate
            time_vector = np.arange(0.0, total_time, 1 / sampling_rate)

            if self.divider > 1:
                time_vector_resampled = np.arange(0.0, total_time, 1 / self.FREQUENCY)
                dist_signal = np.interp(time_vector_resampled, time_vector, dist_signal)
                time_vector = time_vector_resampled

            subnode = self.channels_subnode[channel]
            address = self.channels_address[channel]
            reg_id = str(self.drive.get_register(subnode, address).identifier)

            self.drive.reg_time[reg_id] = time_vector
            self.drive.reg_signals[reg_id] = dist_signal

    @property
    def buffer_size_bytes(self) -> int:
        """Buffer size in bytes."""
        buffer_size_bytes = 0
        n_samples = self.buffer_size
        for channel in range(self.number_mapped_registers):
            buffer_size_bytes += self.channels_size[channel] * n_samples
        return buffer_size_bytes


class SinCosSignalGenerator:
    """SinCos signals generator."""

    SIGNAL_FREQUENCY_HZ = 50

    SINE_REGISTER_VALUE = "FBK_SINCOS_SINE_VALUE"
    SINE_GAIN = 0.8
    SINE_OFFSET = 0.5

    COSINE_REGISTER_VALUE = "FBK_SINCOS_COSINE_VALUE"
    COSINE_GAIN = 0.9
    COSINE_OFFSET = 0.6

    NOISE_AMPLITUDE = 0.01

    def __init__(self, drive: "VirtualDrive") -> None:
        self.drive = drive

    def emulate_signals(self) -> None:
        """Emulate the SinCos signals."""
        if self.drive._monitoring is None:
            return
        total_time_s = self.drive._monitoring.buffer_time
        n_samples = self.drive._monitoring.buffer_size * self.drive._monitoring.divider
        sample_step_s = total_time_s / n_samples
        t = np.arange(0, total_time_s, sample_step_s)

        sine_signal_data = self.SINE_OFFSET + (
            self.SINE_GAIN * np.sin(2 * np.pi * self.SIGNAL_FREQUENCY_HZ * t)
        )
        cosine_signal_data = self.COSINE_OFFSET + (
            self.COSINE_GAIN * np.cos(2 * np.pi * self.SIGNAL_FREQUENCY_HZ * t)
        )
        self.drive.reg_signals[self.SINE_REGISTER_VALUE] = sine_signal_data
        self.drive.reg_noise_amplitude[self.SINE_REGISTER_VALUE] = self.NOISE_AMPLITUDE
        self.drive.reg_signals[self.COSINE_REGISTER_VALUE] = cosine_signal_data
        self.drive.reg_noise_amplitude[self.COSINE_REGISTER_VALUE] = self.NOISE_AMPLITUDE


class VirtualDrive(Thread):
    """Emulates a drive by creating a UDP server that sends and receives MCB messages.

    Args:
        port: Server port number.
        dictionary_path: Path to the dictionary. If None, the default dictionary is used.

    """

    IP_ADDRESS = "127.0.0.1"

    ACK_CMD = 3
    NACK_CMD = 5
    WRITE_CMD = 2
    READ_CMD = 1

    PATH_CONFIGURATION_RELATIVE = "./resources/virtual_drive.xcf"
    PATH_DICTIONARY_RELATIVE = "./resources/virtual_drive.xdf"

    def __init__(self, port: int, dictionary_path: Optional[str] = None) -> None:
        super().__init__()
        self.ip = self.IP_ADDRESS
        self.port = port

        self.environment = Environment()
        self.__gpios = Gpios(self.environment)

        self.__register_signals: dict[str, Signal[Any]] = {
            "IO_IN_VALUE": self.__gpios.value,
            "IO_IN_POLARITY": self.__gpios.polarity,
        }

        default_dictionary = os.path.join(
            pathlib.Path(__file__).parent.resolve(), self.PATH_DICTIONARY_RELATIVE
        )
        self.dictionary_path = dictionary_path or default_dictionary
        self.__stop = False
        self.device_info = None
        self.__logger: list[dict[str, Union[float, bytes, str, tuple[str, int]]]] = []
        self.__reg_address_to_id: dict[int, dict[int, str]] = {}
        self.__dictionary = DictionaryFactory.create_dictionary(
            self.dictionary_path, Interface.VIRTUAL
        )
        self.reg_signals: dict[str, NDArray[np.float64]] = {}
        self.reg_time: dict[str, NDArray[np.float64]] = {}
        self.reg_noise_amplitude: dict[str, float] = {}
        self.is_monitoring_available = EthernetServo.MONITORING_DATA in self.__dictionary.registers(
            0
        )

        self._init_registers()
        self._update_registers()
        if self.is_monitoring_available and isinstance(self.__dictionary, VirtualDictionary):
            self._create_monitoring_disturbance_registers()
        self._init_register_signals()
        self.__set_motor_ready_to_switch_on()

        self._monitoring: Optional[VirtualMonitoring] = None
        self._disturbance: Optional[VirtualDisturbance] = None
        if self.__register_exists(0, VirtualMonitoring.STATUS_REGISTER) and self.__register_exists(
            0, VirtualDisturbance.STATUS_REGISTER
        ):
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
        self._plant_open_loop_vol_to_curr_a = PlantOpenLoopVoltageToCurrentA(self)
        self._plant_open_loop_vol_to_curr_b = PlantOpenLoopVoltageToCurrentB(self)
        self._plant_open_loop_vol_to_curr_c = PlantOpenLoopVoltageToCurrentC(self)

        self._sincos_signals = SinCosSignalGenerator(self)

        self.phasing = VirtualPhasing(self)
        self.internal_generator = VirtualInternalGenerator(self)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if platform.system() != "Windows":
            # On Linux, the SO_REUSEADDR should be set to avoid keeping the socket opened.
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def run(self) -> None:
        """Open socket, listen and decode messages."""
        server_address = (self.ip, self.port)
        self.socket.bind(server_address)
        self.socket.settimeout(2)
        while not self.__stop:
            try:
                frame, add = self.socket.recvfrom(ETH_BUF_SIZE)
            except Exception:
                continue
            reg_add, subnode, cmd, data = MCB.read_mcb_frame(frame)
            self.__log(add, frame, MsgType.RECEIVED)
            register = self.get_register(subnode, reg_add)
            if cmd == self.WRITE_CMD:
                response = self.__get_response_to_write_command(register, data)
            elif cmd == self.READ_CMD:
                response = self.__get_response_to_read_command(register)
            else:
                continue
            self.__send(response, add)

        time.sleep(0.1)

    def __get_response_to_write_command(self, register: EthernetRegister, data: bytes) -> bytes:
        """Return the response to a WRITE command.

        Args:
            register: Register instance.
            data: Received data frame.

        Returns:
            bytes: Response to be sent.
        """
        response = MCB.build_mcb_frame(self.ACK_CMD, register.subnode, register.address, data[:8])
        if register.access in [RegAccess.RW, RegAccess.WO]:
            value = convert_bytes_to_dtype(data, register.dtype)
            self.__decode_msg(register.address, register.subnode, data)
            self.set_value_by_id(register.subnode, str(register.identifier), value)

        return response

    def __get_response_to_read_command(self, register: EthernetRegister) -> bytes:
        """Return the response to a READ command.

        Args:
            register: Register instance.

        Returns:
            bytes: Response to be sent.
        """
        value = self.get_value_by_id(register.subnode, str(register.identifier))
        if (
            self.is_monitoring_available
            and register.address == self.id_to_address(0, EthernetServo.MONITORING_DATA)
            and isinstance(value, bytes)
            and self._monitoring
        ):
            self._monitoring.update_data()
            response = self._response_monitoring_data(value)
        elif (
            self._disturbance is None
            and self._monitoring is None
            and self.__register_exists(0, VirtualMonitoring.STATUS_REGISTER)
            and register.address == self.id_to_address(0, VirtualMonitoring.STATUS_REGISTER)
        ):
            # If a request to read the MON_DIST_STATUS register is made
            # Respond with a read error
            # This is done because the MONITORING_V1 is not supported by the virtual drive.
            response = MCB.build_mcb_frame(
                self.NACK_CMD,
                register.subnode,
                register.address,
                convert_dtype_to_bytes(0, register.dtype),
            )
        else:
            if not isinstance(value, bytes):
                data = convert_dtype_to_bytes(value, register.dtype)
            else:
                data = value
            response = MCB.build_mcb_frame(self.ACK_CMD, register.subnode, register.address, data)

        return response

    def stop(self) -> None:
        """Stop socket."""
        if self.socket is not None:
            self.socket.close()
        self.__stop = True
        if self._monitoring:
            self._monitoring.disable()

    def _read_defaults_from_config(self) -> None:
        configuration_file = os.path.join(
            pathlib.Path(__file__).parent.resolve(), self.PATH_CONFIGURATION_RELATIVE
        )
        conf_file = ConfigurationFile.load_from_xcf(configuration_file)
        for conf_register in conf_file.registers:
            subnode = conf_register.subnode
            reg_data = conf_register.storage
            if not self.__register_exists(subnode, conf_register.uid):
                continue
            self.set_value_by_id(
                subnode,
                conf_register.uid,
                reg_data,
            )

    def _read_defaults_from_xdf_v3(self) -> None:
        for subnode in self.__dictionary.subnodes:
            for uid, dict_register in self.__dictionary.registers(subnode).items():
                if not self.__register_exists(subnode, uid) or dict_register.default is None:
                    continue
                self.set_value_by_id(
                    subnode,
                    uid,
                    dict_register.default,
                )

    def _init_registers(self) -> None:
        """Initialize the registers using the configuration file."""
        if isinstance(self.__dictionary, DictionaryV3):
            self._read_defaults_from_xdf_v3()
        else:
            self._read_defaults_from_config()

        value: Union[str, int]
        for subnode in self.__dictionary.subnodes:
            for reg_id, reg in self.__dictionary.registers(subnode).items():
                if reg._storage is not None:
                    continue
                elif reg.enums_count > 0:
                    value = next(iter(reg.enums.values()))
                elif reg.dtype == RegDtype.STR:
                    value = ""
                else:
                    value = 0
                self.set_value_by_id(subnode, reg_id, value)

    def _update_registers(self) -> None:
        """Force storage_valid at each register and add registers that are not in the dictionary.

        Raises:
            ValueError: if the register is not an EthernetRegister.
        """
        for subnode in self.__dictionary.subnodes:
            self.__reg_address_to_id[subnode] = {}
            for reg_id, reg in self.__dictionary.registers(subnode).items():
                if not isinstance(reg, EthernetRegister):
                    raise ValueError(f"Register {reg_id} is not an EthernetRegister")
                self.__reg_address_to_id[subnode][reg.address] = reg_id
                self.__dictionary.registers(subnode)[reg_id].storage_valid = True

    def _create_monitoring_disturbance_registers(self) -> None:
        """Create the monitoring and disturbance data registers.

        Only used for dictionaries V2 because V3 includes these registers.

        Raises:
            ValueError: if the register is not an EthernetRegister.
        """
        if not isinstance(self.__dictionary, VirtualDictionary):
            return
        custom_regs = {
            EthernetServo.MONITORING_DATA: self.__dictionary.registers(0)[
                EthernetServo.MONITORING_DATA
            ],
            EthernetServo.DIST_DATA: self.__dictionary.registers(0)[EthernetServo.DIST_DATA],
        }
        for register_id, reg in custom_regs.items():
            if not isinstance(reg, EthernetRegister):
                raise ValueError
            register = EthernetRegister(
                reg.address,
                RegDtype.BYTE_ARRAY_512,
                reg.access,
                identifier=register_id,
                subnode=reg.subnode,
            )
            self.__dictionary._add_register_list(register)
            self.__dictionary.registers(reg.subnode)[register_id].storage_valid = True

            self.__reg_address_to_id[reg.subnode][reg.address] = register_id

    def _init_register_signals(self) -> None:
        """Init signals, vector time and noise amplitude for each register."""
        for subnode in self.__dictionary.subnodes:
            for reg_id in self.__dictionary.registers(subnode):
                self.reg_signals[reg_id] = np.array([])
                self.reg_time[reg_id] = np.array([])
                self.reg_noise_amplitude[reg_id] = 0.0

    def __send(self, response: bytes, address: tuple[str, int]) -> None:
        """Send a message and update log.

        Args:
            response: Message to be sent.
            address: IP address and port.
        """
        self.socket.sendto(response, address)
        self.__log(address, response, MsgType.SENT)

    def _response_monitoring_data(self, data: bytes) -> bytes:
        """Creates a response for monitoring data.

        Args:
            data: Data to be sent.

        Returns:
            MCB frame.
        """
        if not self._monitoring:
            return bytes(1)
        sent_cmd = self.ACK_CMD
        reg_add = self.id_to_address(0, EthernetServo.MONITORING_DATA)
        limit = min(len(data), MONITORING_BUFFER_SIZE)
        response = MCB.build_mcb_frame(sent_cmd, 0, reg_add, data[:limit])
        data_left = data[limit:]
        self.set_value_by_id(0, EthernetServo.MONITORING_DATA, data_left)
        self._monitoring.available_bytes = len(data_left)
        return response

    def __log(self, ip_port: tuple[str, int], message: bytes, msg_type: MsgType) -> None:
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
    def log(self) -> list[dict[str, Union[float, bytes, str, tuple[str, int]]]]:
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
        if reg_id == "MON_DIST_ENABLE" and subnode == 0 and value == 1 and self._monitoring:
            self._sincos_signals.emulate_signals()
            self._monitoring.enable()
        if reg_id == "MON_DIST_ENABLE" and subnode == 0 and value == 0 and self._monitoring:
            self._monitoring.disable()
        if reg_id == "MON_CMD_FORCE_TRIGGER" and subnode == 0 and value == 1 and self._monitoring:
            self._monitoring.trigger()
        if reg_id == "MON_REMOVE_DATA" and subnode == 0 and value == 1 and self._monitoring:
            self._monitoring.remove_data()
        if reg_id == "MON_REARM" and subnode == 0 and value == 1 and self._monitoring:
            self._monitoring.rearm()
            self.__emulate_plants()
        if reg_id == "DIST_ENABLE" and subnode == 0 and value == 1 and self._disturbance:
            self._disturbance.enable()
            self.__emulate_plants()
        if reg_id == "DIST_ENABLE" and subnode == 0 and value == 0 and self._disturbance:
            self._disturbance.disable()
            self.__clean_plant_signals()
        if reg_id == "DIST_REMOVE_DATA" and subnode == 0 and value == 1 and self._disturbance:
            self._disturbance.remove_data()
        if reg_id == VirtualDisturbance.DATA_REG and subnode == 0 and self._disturbance:
            self._disturbance.append_data(data)
        if reg_id == "DRV_OP_CMD":
            self.operation_mode = int(value)
            self.__clean_plant_signals()
        if reg_id == "DRV_STATE_CONTROL" and subnode == 1 and (int(value) & constants.IL_MC_CW_EO):
            self.__set_motor_enable()
        if (
            reg_id == "DRV_STATE_CONTROL"
            and subnode == 1
            and (int(value) & constants.IL_MC_PDS_CMD_DV_MSK == constants.IL_MC_PDS_CMD_DV)
        ):
            self.__set_motor_disable()
        if (
            reg_id == "DRV_STATE_CONTROL"
            and subnode == 1
            and (int(value) & constants.IL_MC_PDS_CMD_MSK == constants.IL_MC_PDS_CMD_SD)
        ):
            self.__set_motor_ready_to_switch_on()
        if reg_id == "COMMU_ANGLE_SENSOR" and subnode == 1:
            self.phasing.clear_phasing_bit()
        if (
            reg_id == PlantOpenLoopJB.REGISTER_SET_POINT
            and subnode == 1
            and self.operation_mode in [OperationMode.CURRENT]
        ):
            self._plant_open_loop_jb.jog(float(value))
        if (
            reg_id == PlantClosedLoopRL.REGISTER_SET_POINT
            and subnode == 1
            and self.operation_mode in [OperationMode.CURRENT, OperationMode.VOLTAGE]
        ):
            self._plant_closed_loop_rl_d.jog(float(value))
        if (
            reg_id == PlantClosedLoopRLQuadrature.REGISTER_SET_POINT
            and subnode == 1
            and self.operation_mode in [OperationMode.CURRENT, OperationMode.VOLTAGE]
        ):
            self._plant_closed_loop_rl_q.jog(float(value))
        if (
            reg_id == PlantClosedLoopJB.REGISTER_SET_POINT
            and subnode == 1
            and self.operation_mode in [OperationMode.VELOCITY, OperationMode.PROFILE_VELOCITY]
        ):
            self._plant_closed_loop_jb.jog(float(value))
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
            self._plant_closed_loop_position.jog(int(value))
        if (
            reg_id == PlantOpenLoopVoltageToVelocity.REGISTER_SET_POINT
            and subnode == 1
            and self.operation_mode in [OperationMode.VOLTAGE]
        ):
            self._plant_open_loop_vol_to_vel.jog(float(value))
        if reg_id == VirtualInternalGenerator.REARM_REGISTER and subnode == 1:
            self.internal_generator.enable()

    def address_to_id(self, subnode: int, address: int) -> str:
        """Converts a register address into its ID.

        Args:
            subnode: Subnode.
            address: Register address.

        Returns:
            Register ID.
        """
        return self.__reg_address_to_id[subnode][address]

    def id_to_address(self, subnode: int, uid: str) -> int:
        """Return address of Register with the target subnode and UID.

        Args:
            subnode: Subnode.
            uid: Register UID.

        Raises:
            ValueError: if the register is not an EthernetRegister.

        Returns:
            Register address.
        """
        register = self.__dictionary.registers(subnode)[uid]
        if not isinstance(register, EthernetRegister):
            raise ValueError(f"Register {uid} is not an EthernetRegister")
        return register.address

    def get_value_by_id(self, subnode: int, register_id: str) -> Union[int, float, str, bytes]:
        """Returns a register value by its ID.

        Args:
            subnode: Subnode.
            register_id: Register ID.

        Returns:
            Register value.
        """
        if register_id in self.__register_signals:
            return self.__register_signals[register_id].get()  # type: ignore[no-any-return]

        register = self.__dictionary.registers(subnode)[register_id]
        value: Union[int, float]
        if len(self.reg_signals[register_id]) > 0:
            actual_time = time.time()
            if self._disturbance and self._disturbance.enabled:
                time_diff = actual_time - self._disturbance.start_time
                actual_time = self._disturbance.start_time + (
                    time_diff % self._disturbance.buffer_time
                )
            sample_index = np.argmin(np.abs(self.reg_time[register_id] - actual_time))
            value = self.reg_signals[register_id][sample_index]
            if self.reg_noise_amplitude[register_id] > 0:
                rng = np.random.default_rng()
                value = value + self.reg_noise_amplitude[register_id] * rng.uniform()

            if register.dtype != RegDtype.FLOAT:
                value = int(value)
            return value
        storage_value = self.__dictionary.registers(subnode)[register_id]._storage
        if isinstance(storage_value, (int, float, str, bytes)):
            return storage_value
        else:
            return 0

    def set_value_by_id(
        self, subnode: int, register_id: str, value: Union[float, int, str, bytes]
    ) -> None:
        """Set a register value by its ID.

        Args:
            subnode: Subnode.
            register_id: Register ID.
            value: Value to be set.
        """
        if register_id in self.__register_signals:
            self.__register_signals[register_id].set(value)

        self.__dictionary.registers(subnode)[register_id].storage = value

    def __register_exists(self, subnode: int, register_id: str) -> bool:
        """Returns True if the register exists in the dictionary.

        Args:
            subnode: Subnode.
            register_id: Register ID.

        Returns:
            Register value.
        """
        return subnode in self.__dictionary.subnodes and register_id in self.__dictionary.registers(
            subnode
        )

    def get_register(
        self, subnode: int, address: Optional[int] = None, register_id: Optional[str] = None
    ) -> EthernetRegister:
        """Returns a register by its address or ID.

        Args:
            subnode: Subnode.
            address: Register address. Default to None.
            register_id: Register ID. Default to None.

        Returns:
            Register instance.

        Raises:
            ValueError: If both address and id are None.
        """
        if address is not None:
            register_id = self.address_to_id(subnode, address)
        else:
            if register_id is None:
                raise ValueError("Register address or id should be passed")
        register = self.__dictionary.registers(subnode)[register_id]
        if not isinstance(register, EthernetRegister):
            raise ValueError(f"Register {register_id} is not an EthernetRegister")
        return register

    def __set_motor_enable(self) -> None:
        """Set the enabled state."""
        new_status_word = (
            self.status_word & ~constants.IL_MC_PDS_STA_OE_MSK | constants.IL_MC_PDS_STA_OE
        )
        self.status_word = new_status_word
        self.phasing.enable()

    def __set_motor_disable(self) -> None:
        """Set the disabled state."""
        new_status_word = (
            self.status_word & ~constants.IL_MC_PDS_STA_OE_MSK | constants.IL_MC_PDS_STA_SOD
        )
        self.status_word = new_status_word
        self.phasing.set_phasing_bit()

    def __set_motor_ready_to_switch_on(self) -> None:
        """Set the ready-to-switch-on state."""
        new_status_word = (
            self.status_word & ~constants.IL_MC_PDS_STA_OE_MSK | constants.IL_MC_PDS_STA_RTSO
        )
        self.status_word = new_status_word

    def __emulate_plants(self) -> None:
        """Emulate plants according the operation mode."""
        if self.operation_mode in [OperationMode.VOLTAGE]:
            self._plant_open_loop_rl_d.emulate_plant()
            self._plant_open_loop_rl_q.emulate_plant()
            self._plant_open_loop_vol_to_curr_a.emulate_plant()
            self._plant_open_loop_vol_to_curr_b.emulate_plant()
            self._plant_open_loop_vol_to_curr_c.emulate_plant()
        if self.operation_mode in [OperationMode.CURRENT]:
            self._plant_open_loop_jb.emulate_plant()
            self._plant_closed_loop_rl_d.emulate_plant()
            self._plant_closed_loop_rl_q.emulate_plant()
        if self.operation_mode in [OperationMode.VELOCITY]:
            self._plant_open_loop_position.emulate_plant()
        if self.operation_mode in [
            OperationMode.VELOCITY,
            OperationMode.PROFILE_VELOCITY,
        ]:
            self._plant_closed_loop_jb.emulate_plant()
        if self.operation_mode in [
            OperationMode.POSITION,
            OperationMode.PROFILE_POSITION,
            OperationMode.PROFILE_POSITION_S_CURVE,
        ]:
            self._plant_closed_loop_position.emulate_plant()

    def __clean_plant_signals(self) -> None:
        """Clean all plant signals."""
        self._plant_open_loop_jb.clean_signals()
        self._plant_closed_loop_jb.clean_signals()
        self._plant_open_loop_position.clean_signals()
        self._plant_closed_loop_position.clean_signals()
        self._plant_open_loop_rl_d.clean_signals()
        self._plant_open_loop_rl_q.clean_signals()
        self._plant_closed_loop_rl_d.clean_signals()
        self._plant_closed_loop_rl_q.clean_signals()
        self._plant_open_loop_vol_to_vel.clean_signals()
        self._plant_open_loop_vol_to_curr_a.clean_signals()
        self._plant_open_loop_vol_to_curr_b.clean_signals()
        self._plant_open_loop_vol_to_curr_c.clean_signals()

    @property
    def operation_mode(self) -> int:
        """Operation Mode."""
        return int(self.get_value_by_id(1, "DRV_OP_VALUE"))

    @operation_mode.setter
    def operation_mode(self, operation_mode: int) -> None:
        """Set Operation Mode."""
        self.set_value_by_id(1, "DRV_OP_VALUE", operation_mode)

    @property
    def current_loop_rate(self) -> int:
        """Current loop rate."""
        return int(self.get_value_by_id(1, "CL_CUR_FREQ"))

    @property
    def enabled(self) -> bool:
        """Return true if the motor is enabled.

        Returns:
            True if the motor is enabled.
        """
        return (self.status_word & constants.IL_MC_PDS_STA_OE_MSK) == constants.IL_MC_PDS_STA_OE

    @property
    def status_word(self) -> int:
        """Get the status word register."""
        return int(self.get_value_by_id(1, "DRV_STATE_STATUS"))

    @status_word.setter
    def status_word(self, value: int) -> None:
        return self.set_value_by_id(1, "DRV_STATE_STATUS", value)
