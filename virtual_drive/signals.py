from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Signal(Generic[T]):
    """Virtual Drive Signal.

    Represents any physical or internal continuous signal of the drive.

    Intended to use as a publisher-subscriber pattern.
    The module signal owner publishes the signal, other modules subscribes to it
    """

    def __init__(self, initial_value: T):
        self.__value = initial_value
        self.__watchers: list[Callable[[], None]] = []

    def get(self) -> T:
        """Get current value of the signal.

        Returns:
            current value of the signal.
        """
        return self.__value

    def watch(self, callback: Callable[[], None]) -> None:
        """Watch signal.

        Args:
            callback: Will be called when signal changes
        """
        self.__watchers.append(callback)

    def set(self, value: T) -> None:
        """Set signal value."""
        self.__value = value
        for wat in self.__watchers:
            wat()
