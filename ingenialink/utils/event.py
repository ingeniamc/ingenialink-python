import logging
from typing import Any, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

CallbackT = TypeVar("CallbackT", bound=Callable[..., Any])
T = TypeVar("T")


class _Observers(Generic[CallbackT]):
    """Generic publish/subscribe manager.

    Stores a list of subscriber callbacks and notifies them when an event
    is published. Duplicate subscriptions are silently ignored

    Type parameter:
        CallbackT: The callable type of the subscribers.
    """

    def __init__(self, subscribers: list[CallbackT]) -> None:
        self.__subscribers = subscribers

    def subscribe(self, callback: CallbackT) -> None:
        """Subscribe a callback to this observer.

        Args:
            callback: Callable to register. If it is already subscribed the
                call is a no-op.
        """
        if callback in self.__subscribers:
            return
        self.__subscribers.append(callback)

    def unsubscribe(self, callback: CallbackT) -> None:
        """Unsubscribe a previously registered callback.

        Args:
            callback: Callable to remove. If it was not subscribed the call
                is a no-op.
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
            try:
                callback(*args, **kwargs)
            except Exception as e:  # noqa: PERF203
                logger.exception("Error in event callback %s: %s", callback, e)


def create_event(
    callback_type: type[T],
) -> tuple[_Observers[Callable[[T], None]], _Publisher[Callable[[T], None]]]:
    """Create a linked Observers and Publisher pair.

    Args:
        callback_type: Type of the argument emitted by the event.
            Used only for type inference; ignored at runtime.

    Returns:
        A tuple of ``(observers, publisher)`` where *observers* is the public
        handle for subscribing/unsubscribing and *publisher* is the private
        handle used to fire the event.

    Example::

        from ingenialink.utils.event import create_event

        observers, publisher = create_event(int)
        observers.subscribe(lambda x: print(x))
        publisher.notify(42)  # prints 42
    """
    _ = callback_type  # used only for typing
    subscribers: list[Any] = []
    observers = _Observers(subscribers)
    publisher = _Publisher(subscribers)
    return observers, publisher
