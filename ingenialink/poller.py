from datetime import datetime
from threading import Timer, Lock
from typing import List, Dict, Tuple, Union, Callable, Optional, Any

from ingenialink.exceptions import (
    ILAlreadyInitializedError,
    ILStateError,
    ILValueError,
    ILTimeoutError,
)
from ingenialink.servo import Servo
from ingenialink.register import Register

import ingenialogger

logger = ingenialogger.get_logger(__name__)


class PollerTimer:
    """Custom timer for the Poller.

    Args:
        time: Timeout to use for the timer.
        cb: Callback.

    """

    def __init__(self, time: float, cb: Callable[..., Any]) -> None:
        self.cb = cb
        self.time = time
        self.thread = Timer(self.time, self.handle_function)

    def handle_function(self) -> None:
        """Handle method that creates the timer for the poller"""
        self.cb()
        self.thread = Timer(self.time, self.handle_function)
        self.thread.start()

    def start(self) -> None:
        """Starts the poller timer"""
        self.thread.start()

    def cancel(self) -> None:
        """Stops the poller timer"""
        self.thread.cancel()
        if self.thread.is_alive():
            self.thread.join()


class Poller:
    """Register poller for CANOpen/Ethernet communications.

    Args:
        servo: Servo.
        num_channels: Number of channels.

    """

    def __init__(self, servo: Servo, num_channels: int) -> None:
        self.__servo = servo
        self.__num_channels = num_channels
        self.__sz = 0
        self.__refresh_time = 0.0
        self.__time_start = datetime.now()
        self.__samples_count = 0
        self.__samples_lost = False
        self.__timer: Optional[PollerTimer] = None
        self.__running = False
        self.__mappings: Dict[int, Register] = {}
        self.__mappings_enabled: List[bool] = []
        self.__lock = Lock()
        self.__acq_time: List[float] = []
        self.__acq_data: List[Union[List[float], List[int]]] = []
        self._reset_acq()

    def start(self) -> int:
        """Start the poller."""

        if self.__running:
            raise ILAlreadyInitializedError("Poller already running")

        # Activate timer
        self.__timer = PollerTimer(self.__refresh_time, self._acquire_callback_poller_data)
        self.__timer.start()
        self.__time_start = datetime.now()

        self.__running = True

        return 0

    def stop(self) -> None:
        """Stop poller."""

        if self.__running and self.__timer:
            self.__timer.cancel()

        self.__running = False

    def configure(self, t_s: float, sz: int) -> int:
        """Configure data.

        Args:
            t_s: Polling period (s).
            sz: Buffer size.

        Returns:
            Status code.

        Raises:
            ILStateError: The poller is already running.

        """
        if self.__running:
            raise ILStateError("Poller is running")
        # Configure data and sizes with empty data
        self._reset_acq()
        self.__sz = sz
        self.__refresh_time = t_s
        self.__acq_time = [0.0] * sz
        self.__mappings = {}
        self.__mappings_enabled = []
        for _ in range(self.num_channels):
            data_channel = [0.0] * sz
            self.__acq_data.append(data_channel)
            self.__mappings_enabled.append(False)

        return 0

    def ch_configure(self, channel: int, reg: Register, subnode: int = 1) -> int:
        """Configure a poller channel mapping.

        Args:
            channel: Channel to be configured.
            reg: Register to associate to the given channel.
            subnode: Subnode for the register.

        Returns:
            Status code.

        Raises:
            ILStateError: The poller is already running.
            ILValueError: Channel out of range.
            TypeError: If the register is not valid.

        """

        if self.__running:
            raise ILStateError("Poller is running")

        if channel > self.num_channels:
            raise ILValueError("Channel out of range")

        # Obtain register
        _reg = self.servo._get_reg(reg, subnode)

        if _reg.identifier is None:
            raise TypeError("Register should have an identifier")

        # Reg identifier obtained and set enabled
        self.__mappings[channel] = _reg
        self.__mappings_enabled[channel] = True

        return 0

    def ch_disable(self, channel: int) -> int:
        """Disable a channel.

        Args:
            channel: Channel to be disabled.

        Raises:
            ILStateError: The poller is already running.
            ILValueError: Channel out of range.

        Returns:
            Status code.

        """

        if self.__running:
            raise ILStateError("Poller is running")

        if channel > self.num_channels:
            raise ILValueError("Channel out of range")

        # Set channel required as disabled
        self.__mappings_enabled[channel] = False

        return 0

    def ch_disable_all(self) -> int:
        """Disable all channels.

        Returns:
            Status code.

        """
        for channel in range(self.num_channels):
            r = self.ch_disable(channel)
        return 0

    def _reset_acq(self) -> None:
        """Resets the acquired channels."""
        self.__acq_time = [0.0]
        self.__acq_data = []

    def _acquire_callback_poller_data(self) -> None:
        """Acquire callback for poller data."""
        time_diff = datetime.now()
        delta = time_diff - self.__time_start

        # Obtain current time
        t = delta.total_seconds()

        self.__lock.acquire()
        # Acquire all configured channels
        if self.__samples_count >= self.__sz:
            self.__samples_lost = True
        else:
            self.__acq_time[self.__samples_count] = t

            # Acquire enabled channels, comprehension list indexes obtained
            enabled_channel_indexes = [
                channel_idx
                for channel_idx, is_enabled in enumerate(self.__mappings_enabled)
                if is_enabled
            ]

            reading_error = False
            for channel in enabled_channel_indexes:
                register = self.__mappings[channel]
                try:
                    self.__acq_data[channel][self.__samples_count] = self.servo.read(register)  # type: ignore
                except ILTimeoutError:
                    reading_error = True
                    logger.warning(
                        f"Could not read {register.identifier} register. This sample is lost for"
                        " all channels."
                    )

            if not reading_error:
                # Increment samples count
                self.__samples_count += 1

        self.__lock.release()

    @property
    def data(self) -> Tuple[List[float], List[List[float]], bool]:
        """Time vector, array of data vectors and a flag indicating if data was lost."""
        t = list(self.__acq_time[0 : self.__samples_count])
        d = []

        # Acquire enabled channels, comprehension list indexes obtained
        enabled_channel_indexes = [
            channel_idx
            for channel_idx, is_enabled in enumerate(self.__mappings_enabled)
            if is_enabled
        ]

        for channel in range(self.num_channels):
            if self.__mappings_enabled[channel]:
                d.append(list(self.__acq_data[channel][0 : self.__samples_count]))
            else:
                d.append([0.0])

        self.__lock.acquire()
        self.__samples_count = 0
        self.__samples_lost = False
        self.__lock.release()

        return t, d, self.__samples_lost

    @property
    def servo(self) -> Servo:
        """Servo instance to be used."""
        return self.__servo

    @servo.setter
    def servo(self, value: Servo) -> None:
        self.__servo = value

    @property
    def num_channels(self) -> int:
        """Number of channels in the poller."""
        return self.__num_channels

    @num_channels.setter
    def num_channels(self, value: int) -> None:
        self.__num_channels = value
