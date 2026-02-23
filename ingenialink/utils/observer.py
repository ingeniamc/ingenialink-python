import logging
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

CallbackT = TypeVar("CallbackT")


class Observer(Generic[CallbackT]):
    """Generic publish/subscribe manager.

    Stores a list of subscriber callbacks and notifies them when an event
    is published. Duplicate subscriptions are silently ignored (a warning is
    logged instead).

    Type parameter:
        CallbackT: The callable type of the subscribers.

    Example::

        from typing import Callable
        from ingenialink.utils.observer import Observer

        obs: Observer[Callable[[int], None]] = Observer()
        obs.subscribe(lambda x: print(x))
        obs.notify(42)     # prints 42
    """

    def __init__(self) -> None:
        self.__subscribers: list[CallbackT] = []

    def subscribe(self, callback: CallbackT) -> None:
        """Subscribe a callback to this observer.

        Args:
            callback: Callable to register. If it is already subscribed the
                call is a no-op (a warning is logged).
        """
        if callback in self.__subscribers:
            return
        self.__subscribers.append(callback)

    def unsubscribe(self, callback: CallbackT) -> None:
        """Unsubscribe a previously registered callback.

        Args:
            callback: Callable to remove. If it was not subscribed the call
                is a no-op (a warning is logged).
        """
        if callback not in self.__subscribers:
            return
        self.__subscribers.remove(callback)

    def notify(self, *args: object, **kwargs: object) -> None:
        """Call all subscribed callbacks with the provided arguments.

        Args:
            *args: Positional arguments forwarded to every callback.
            **kwargs: Keyword arguments forwarded to every callback.
        """
        for callback in list(self.__subscribers):
            callback(*args, **kwargs)
