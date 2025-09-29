import re
import threading
import time
from typing import TYPE_CHECKING, Callable, Optional

import ingenialogger

from ingenialink.exceptions import ILError, ILWrongWorkingCountError

if TYPE_CHECKING:
    from ingenialink.ethercat.network import EthercatNetwork


class PDONetworkManager:
    """Manage all the PDO functionalities.

    Args:
        net: Ethercat network.
    """

    __SAFE_RPDO_UID: str = "ETG_COMMS_RPDO_MAP256"
    __SAFE_TPDO_UID: str = "ETG_COMMS_TPDO_MAP256"

    class ProcessDataThread(threading.Thread):
        """Manage the PDO exchange.

        Args:
            net: The EthercatNetwork instance where the PDOs will be active.
            refresh_rate: Determines how often (seconds) the PDO values will be updated.
            watchdog_timeout: The PDO watchdog time. If not provided it will be set proportional
             to the refresh rate.
            notify_send_process_data: Callback to notify when process data is about to be sent.
            notify_receive_process_data: Callback to notify when process data is received.
            notify_exceptions: Callback to notify when an exception is raised.

        Raises:
            ValueError: If the provided refresh rate is unfeasible.
        """

        DEFAULT_PDO_REFRESH_TIME = 0.01
        MINIMUM_PDO_REFRESH_TIME = 0.001
        DEFAULT_WATCHDOG_TIMEOUT = 0.1
        PDO_WATCHDOG_INCREMENT_FACTOR = 2
        # The time.sleep precision is 13 ms for Windows OS
        # https://stackoverflow.com/questions/1133857/how-accurate-is-pythons-time-sleep
        WINDOWS_TIME_SLEEP_PRECISION = 0.013

        def __init__(
            self,
            net: "EthercatNetwork",
            refresh_rate: Optional[float],
            watchdog_timeout: Optional[float],
            notify_send_process_data: Callable[[], None],
            notify_receive_process_data: Callable[[], None],
            notify_exceptions: Callable[[ILError], None],
        ) -> None:
            super().__init__()

            self._net = net
            if refresh_rate is None:
                refresh_rate = self.DEFAULT_PDO_REFRESH_TIME
            elif refresh_rate < self.MINIMUM_PDO_REFRESH_TIME:
                raise ValueError(
                    f"The minimum PDO refresh rate is {self.MINIMUM_PDO_REFRESH_TIME} seconds."
                )
            self._refresh_rate = refresh_rate
            self._watchdog_timeout = watchdog_timeout
            self._notify_send_process_data = notify_send_process_data
            self._notify_receive_process_data = notify_receive_process_data
            self._notify_exceptions = notify_exceptions
            self._pd_thread_stop_event = threading.Event()

        def run(self) -> None:
            """Start the PDO exchange."""
            try:
                self.__set_watchdog_timeout()
            except ILError as e:
                self._notify_exceptions(e)
                return
            first_iteration = True
            iteration_duration: float = -1
            while not self._pd_thread_stop_event.is_set():
                time_start = time.perf_counter()
                self._notify_send_process_data()
                try:
                    if first_iteration:
                        self._net.start_pdos()
                        first_iteration = False
                    else:
                        self._net.send_receive_processdata(self._refresh_rate)
                except ILWrongWorkingCountError as il_error:
                    self._pd_thread_stop_event.set()
                    self._net.stop_pdos()
                    duration_error = (
                        (
                            f"Last iteration took {iteration_duration * 1000:0.1f} ms which is "
                            f"higher than the watchdog timeout "
                            f"({self._watchdog_timeout * 1000:0.1f} ms). Please optimize the"
                            f" callbacks and/or increase the refresh rate/watchdog timeout."
                        )
                        if (
                            self._watchdog_timeout is not None
                            and iteration_duration > self._watchdog_timeout
                        )
                        else ""
                    )
                    self._notify_exceptions(
                        ILError(
                            "Stopping the PDO thread due to the following exception:"
                            f" {il_error} {duration_error}"
                        )
                    )
                except Exception as il_error:
                    self._pd_thread_stop_event.set()
                    if first_iteration:
                        self._notify_exceptions(
                            ILError(f"Could not start the PDOs due to exception: {il_error}")
                        )
                    else:
                        self._notify_exceptions(
                            ILError(f"Exception during PDO exchange: {il_error}")
                        )
                else:
                    self._notify_receive_process_data()
                    while (
                        remaining_loop_time := self._refresh_rate
                        - (time.perf_counter() - time_start)
                    ) > 0:
                        if remaining_loop_time > self.WINDOWS_TIME_SLEEP_PRECISION:
                            time.sleep(self.WINDOWS_TIME_SLEEP_PRECISION)
                        else:
                            self.high_precision_sleep(remaining_loop_time)
                    iteration_duration = time.perf_counter() - time_start

        def stop(self) -> None:
            """Stop the PDO exchange."""
            self._pd_thread_stop_event.set()
            # Only join if we're not trying to join the current thread
            # (e.g., when stopping from an exception handler running in this thread)
            if threading.current_thread() != self:
                self.join()
            self._net.stop_pdos()

        @staticmethod
        def high_precision_sleep(duration: float) -> None:
            """Replaces the time.sleep() method.

            This is done in order to obtain more precise sleeping times.
            """
            start_time = time.perf_counter()
            while duration - (time.perf_counter() - start_time) > 0:
                pass

        def __set_watchdog_timeout(self) -> None:
            if self._watchdog_timeout is None:
                self._watchdog_timeout = max(
                    self.DEFAULT_WATCHDOG_TIMEOUT,
                    self._refresh_rate * self.PDO_WATCHDOG_INCREMENT_FACTOR,
                )
                is_watchdog_timeout_manually_set = False
            else:
                is_watchdog_timeout_manually_set = True
            try:
                for servo in self._net.servos:
                    servo.set_pdo_watchdog_time(self._watchdog_timeout)
            except AttributeError as e:
                max_pdo_watchdog = re.findall("wd_time_ms is limited to (.+) ms", e.__str__())
                max_pdo_watchdog_ms = None
                if max_pdo_watchdog is not None:
                    max_pdo_watchdog_ms = float(max_pdo_watchdog[0])
                if is_watchdog_timeout_manually_set:
                    error_msg = "The watchdog timeout is too high."
                    if max_pdo_watchdog_ms is not None:
                        error_msg += f" The max watchdog timeout is {max_pdo_watchdog_ms} ms."
                else:
                    error_msg = "The sampling time is too high."
                    if max_pdo_watchdog_ms is not None:
                        max_sampling_time = max_pdo_watchdog_ms / self.PDO_WATCHDOG_INCREMENT_FACTOR
                        error_msg += f" The max sampling time is {max_sampling_time} ms."
                raise ILError(error_msg) from e

    def __init__(self, net: "EthercatNetwork") -> None:
        self._net = net
        self.logger = ingenialogger.get_logger(__name__)
        self._pdo_thread: Optional[PDONetworkManager.ProcessDataThread] = None
        self._pdo_send_observers: list[Callable[[], None]] = []
        self._pdo_receive_observers: list[Callable[[], None]] = []
        self._pdo_exceptions_observers: list[Callable[[ILError], None]] = []

    def check_safe_pdo_configuration(self) -> bool:
        """Returns True if safe drives have their safe PDOs configured.

        If there are no safe drives connected to the network, it also returns True.
        """
        for servo in self._net.servos:
            if not servo.dictionary.is_safe:
                continue
            safe_rpdo_idx = servo.dictionary.get_object(self.__SAFE_RPDO_UID, subnode=1).idx
            if servo._rpdo_maps.get(safe_rpdo_idx, None) is None:
                return False
            safe_tpdo_idx = servo.dictionary.get_object(self.__SAFE_TPDO_UID, subnode=1).idx
            if servo._tpdo_maps.get(safe_tpdo_idx, None) is None:
                return False
        return True

    def start_pdos(
        self,
        refresh_rate: Optional[float] = None,
        watchdog_timeout: Optional[float] = None,
    ) -> None:
        """Start the PDO exchange process.

        Args:
            refresh_rate: Determines how often (seconds) the PDO values will be updated.
            watchdog_timeout: The PDO watchdog time. If not provided it will be set proportional
             to the refresh rate.

        Raises:
            ILError: If the PDOs are already active.
        """
        if self._pdo_thread is not None:
            self.stop_pdos()
            raise ILError("PDOs are already active.")
        self._pdo_thread = self.ProcessDataThread(
            net=self._net,
            refresh_rate=refresh_rate,
            watchdog_timeout=watchdog_timeout,
            notify_send_process_data=self._notify_send_process_data,
            notify_receive_process_data=self._notify_receive_process_data,
            notify_exceptions=self._notify_exceptions,
        )
        self._pdo_thread.start()

    def stop_pdos(self) -> None:
        """Stop the PDO exchange process.

        Raises:
            ILError: If the PDOs are not active yet.

        """
        if self._pdo_thread is None:
            raise ILError("The PDO exchange has not started yet.")
        self._pdo_thread.stop()
        self._pdo_thread = None

    @property
    def is_active(self) -> bool:
        """Check if the PDO thread is active.

        Returns:
            True if the PDO thread is active. False otherwise.
        """
        if self._pdo_thread is None:
            return False
        return self._pdo_thread.is_alive()

    def subscribe_to_send_process_data(self, callback: Callable[[], None]) -> None:
        """Subscribe be notified when the RPDO values will be sent.

        Args:
            callback: Callback function.
        """
        if callback in self._pdo_send_observers:
            return
        self._pdo_send_observers.append(callback)

    def subscribe_to_receive_process_data(self, callback: Callable[[], None]) -> None:
        """Subscribe be notified when the TPDO values are received.

        Args:
            callback: Callback function.
        """
        if callback in self._pdo_receive_observers:
            return
        self._pdo_receive_observers.append(callback)

    def subscribe_to_exceptions(self, callback: Callable[[ILError], None]) -> None:
        """Subscribe be notified when there is an exception in the PDO process data thread.

        If a callback is subscribed, the PDO exchange process is paused when an exception is raised.
        It can be resumed using the `resume_pdos` method.

        Args:
            callback: Callback function.
        """
        if callback in self._pdo_exceptions_observers:
            return
        self._pdo_exceptions_observers.append(callback)

    def unsubscribe_to_send_process_data(self, callback: Callable[[], None]) -> None:
        """Unsubscribe from the send process data notifications.

        Args:
            callback: Subscribed callback function.
        """
        if callback not in self._pdo_send_observers:
            return
        self._pdo_send_observers.remove(callback)

    def unsubscribe_to_receive_process_data(self, callback: Callable[[], None]) -> None:
        """Unsubscribe from the receive process data notifications.

        Args:
            callback: Subscribed callback function.
        """
        if callback not in self._pdo_receive_observers:
            return
        self._pdo_receive_observers.remove(callback)

    def unsubscribe_to_exceptions(self, callback: Callable[[ILError], None]) -> None:
        """Unsubscribe from the exceptions in the process data notifications.

        Args:
            callback: Subscribed callback function.

        """
        if callback not in self._pdo_exceptions_observers:
            return
        self._pdo_exceptions_observers.remove(callback)

    def _notify_send_process_data(self) -> None:
        """Notify subscribers that the RPDO values will be sent."""
        for callback in self._pdo_send_observers:
            callback()

    def _notify_receive_process_data(self) -> None:
        """Notify subscribers that the TPDO values were received."""
        for callback in self._pdo_receive_observers:
            callback()

    def _notify_exceptions(self, exc: ILError) -> None:
        """Notify subscribers that there was an exception.

        Args:
            exc: Exception that was raised in the PDO process data thread.
        """
        if not self.check_safe_pdo_configuration():
            exc = ILError(
                f"{exc} \nThe PDO exchange has been stopped due to a wrong PDO configuration "
                "in a safe drive. Please, check that the safe PDOs are correctly mapped. "
            )
        self.logger.error(exc)
        for callback in self._pdo_exceptions_observers:
            callback(exc)
        self._pdo_thread = None  # If there has been an error, remove the pdo thread reference
