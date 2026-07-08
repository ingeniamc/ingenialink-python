"""Shared helpers for the ``NetStatusListener`` power-cycle hardware tests.

These helpers let the EtherCAT, Ethernet and CANopen
``test_net_status_listener_detects_power_cycle`` tests share a single
detect-and-recover measurement path, so the real reconnection timing of the
library can be profiled consistently across communication types.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from types import TracebackType
from typing import Optional, Union

from ingenialink.network import NetDevEvt, Network

logger = logging.getLogger(__name__)


@dataclass
class NetStatusRecorder:
    """Records ``NetStatusListener`` events and times detection latencies.

    Use the recorder as a context manager around each power cycle: entering the
    ``with`` block subscribes to the network status, starts the listener and
    starts the timer; :meth:`wait_removed` / :meth:`wait_added` block on each
    event while logging its latency; and leaving the block stops the listener and
    logs a profile summary. Call :meth:`rearm` to time a second power cycle
    without leaving the block.

    Args:
        network: Network the drive is connected through.
        servo_id: Identifier of the drive within the network (slave id, IP or node id).
        protocol: Communication type name, used to tag the profiling log lines.
    """

    network: Network
    servo_id: Union[int, str]
    protocol: str
    removed_event: threading.Event = field(default_factory=threading.Event)
    added_event: threading.Event = field(default_factory=threading.Event)
    _marked_at: float = field(default=0.0, init=False)
    _latencies: dict[str, float] = field(default_factory=dict, init=False)

    def callback(self, event: NetDevEvt) -> None:
        """Store a listener event so the test thread can wait on it.

        Args:
            event: Net device event notified by the listener.
        """
        if event == NetDevEvt.REMOVED:
            self.removed_event.set()
        elif event == NetDevEvt.ADDED:
            self.added_event.set()

    def rearm(self) -> None:
        """Clear the events and restart the timer for another power cycle."""
        self.removed_event.clear()
        self.added_event.clear()
        self._marked_at = time.perf_counter()

    def __enter__(self) -> "NetStatusRecorder":
        """Subscribe, start the listener and start the timer.

        Returns:
            The recorder itself, to be bound by the ``with`` statement.
        """
        self.network.subscribe_to_status(self.servo_id, self.callback)
        self.network.start_status_listener()
        self._latencies.clear()
        self.rearm()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Stop the listener and log a summary of the measured latencies.

        The listener is intentionally left subscribed; see
        https://novantamotion.atlassian.net/browse/CIT-627.
        """
        self.network.stop_status_listener()
        summary = ", ".join(f"{phase} after {sec:.3f} s" for phase, sec in self._latencies.items())
        logger.info(f"[{self.protocol}] power-cycle window: {summary or 'no events detected'}")

    def wait_removed(self, timeout: float, note: str = "") -> bool:
        """Wait for the REMOVED event, logging how long detection took.

        Args:
            timeout: Maximum time to wait, in seconds.
            note: Optional tag appended to the log line, e.g. ``"PDO"``.

        Returns:
            True if the drive disconnection was detected within ``timeout``.
        """
        return self._wait(self.removed_event, timeout, "disconnection", note)

    def wait_added(self, timeout: float, note: str = "") -> bool:
        """Wait for the ADDED event, logging how long detection took.

        Args:
            timeout: Maximum time to wait, in seconds.
            note: Optional tag appended to the log line, e.g. ``"PDO"``.

        Returns:
            True if the drive reconnection was detected within ``timeout``.
        """
        return self._wait(self.added_event, timeout, "reconnection", note)

    def _wait(self, event: threading.Event, timeout: float, phase: str, note: str) -> bool:
        detected = event.wait(timeout=timeout)
        elapsed = time.perf_counter() - self._marked_at
        label = f"{phase} ({note})" if note else phase
        if detected:
            logger.info(f"[{self.protocol}] drive {label} detected after {elapsed:.3f} s")
            self._latencies[label] = elapsed
        else:
            logger.warning(f"[{self.protocol}] drive {label} NOT detected within {timeout:.1f} s")
        return detected
