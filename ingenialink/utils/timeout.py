import time
from types import TracebackType
from typing import Optional


class Timeout:
    """Context manager to handle timeouts."""

    def __init__(self, timeout: float) -> None:
        """Initialize the Timeout context manager."""
        self.__timeout = timeout
        self.__initial_time = time.time()

    def __enter__(self) -> "Timeout":
        """Enter the context manager and start the timer.

        Returns:
            Timeout: The instance of the Timeout context manager.
        """
        return self

    def __exit__(
        self,
        exc_type: Optional[type[Exception]],
        exc_val: Optional[Exception],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit the context manager."""
        return

    @property
    def elapsed_time_s(self) -> float:
        """Get the elapsed time since the context manager was entered."""
        return time.time() - self.__initial_time

    @property
    def remaining_time_s(self) -> float:
        """Get the remaining time before the timeout is reached."""
        return max(0.0, self.__timeout - self.elapsed_time_s)

    @property
    def remaining_time_us(self) -> int:
        """Get the remaining time in microseconds before the timeout is reached."""
        return int(self.remaining_time_s * 1_000_000)

    @property
    def has_expired(self) -> bool:
        """Check if the timeout has been reached."""
        return self.elapsed_time_s >= self.__timeout
