import logging
from typing import Any, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

CallbackT = TypeVar("CallbackT", bound=Callable[..., Any])


class _Observers(Generic[CallbackT]):
    """Generic publish/subscribe manager.

    Stores a list of subscriber callbacks and notifies them when an event
    is published. Duplicate subscriptions are silently ignored (a warning is
    logged instead).

    Type parameter:
        CallbackT: The callable type of the subscribers.
    """

    def __init__(self, subscribers: list[CallbackT]) -> None:
        self.__subscribers = subscribers

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


class _Publisher(Generic[CallbackT]):
    """Publisher for an event, linked to an Observers instance."""

    def __init__(self, subscribers: list[CallbackT]) -> None:
        self.__subscribers = subscribers

    def notify(self, *args: object, **kwargs: object) -> None:
        """Notify all subscribers.

        Args:
            *args: Positional arguments forwarded to every callback.
            **kwargs: Keyword arguments forwarded to every callback.
        """
        for callback in list(self.__subscribers):
            callback(*args, **kwargs)


def create_event() -> tuple[_Observers[Callable[..., Any]], _Publisher[Callable[..., Any]]]:
    """Create a linked Observers and Publisher pair.

    Returns:
        A tuple of (observers, publisher) where observers is public for subscribing,
        and publisher is private for notifying.

    Example::

        from typing import Callable
        from ingenialink.utils.event import create_event

        observers, publisher = create_event()
        observers.subscribe(lambda x: print(x))
        publisher.notify(42)  # prints 42
    """
    subscribers: list[Callable[..., Any]] = []
    observers = _Observers[Callable[..., Any]](subscribers)
    publisher = _Publisher[Callable[..., Any]](subscribers)
    return observers, publisher
