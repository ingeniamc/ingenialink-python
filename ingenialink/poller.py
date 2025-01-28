import time
from threading import Lock, Thread
from typing import Union

import ingenialogger

from ingenialink.exceptions import ILIOError, ILStateError, ILTimeoutError, ILValueError
from ingenialink.register import Register
from ingenialink.servo import Servo

logger = ingenialogger.get_logger(__name__)


class Poller(Thread):
    """Register poller for CANOpen/Ethernet communications.

    Args:
        servo: Servo.
        num_channels: Number of channels.

    """

    def __init__(self, servo: Servo, num_channels: int) -> None:
        super().__init__()
        self.__servo = servo
        self.__num_channels = num_channels
        self.__sz = 0
        self.__refresh_time = 0.0
        self.__samples_count = 0
        self.__samples_lost = False
        self.__running = False
        self.__mappings: dict[int, Register] = {}
        self.__mappings_enabled: list[bool] = []
        self.__lock = Lock()
        self.__acq_time: list[float] = []
        self.__acq_data: list[Union[list[float], list[int]]] = []
        self._reset_acq()

    def run(self) -> None:
        """Start the poller."""
        self.__running = True
        self.__time_start = time.time()
        while self.__running:
            time_start = time.perf_counter()
            self._acquire_callback_poller_data()
            remaining_loop_time = self.__refresh_time - (time.perf_counter() - time_start)
            if remaining_loop_time > 0:
                time.sleep(remaining_loop_time)

    def stop(self) -> None:
        """Stop poller."""
        self.__running = False
        self.join()

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
            self.ch_disable(channel)
        return 0

    def _reset_acq(self) -> None:
        """Resets the acquired channels."""
        self.__acq_time = [0.0]
        self.__acq_data = []

    def _acquire_callback_poller_data(self) -> None:
        """Acquire callback for poller data."""
        time_diff = time.time()

        # Obtain current time
        t = time_diff - self.__time_start

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
                    self.__acq_data[channel][self.__samples_count] = self.servo.read(register)  # type: ignore[assignment]
                except (ILTimeoutError, ILIOError):
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
    def data(self) -> tuple[list[float], list[list[float]], bool]:
        """Time vector, array of data vectors and a flag indicating if data was lost."""
        self.__lock.acquire()
        t = list(self.__acq_time[0 : self.__samples_count])
        d = []

        for channel in range(self.num_channels):
            if self.__mappings_enabled[channel]:
                d.append(list(self.__acq_data[channel][0 : self.__samples_count]))
            else:
                d.append([0.0])

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
