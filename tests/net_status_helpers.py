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

from ingenialink.network import NetDevEvt

logger = logging.getLogger(__name__)


@dataclass
class NetStatusRecorder:
    """Records ``NetStatusListener`` events and times detection latencies.

    Subscribe :meth:`callback` to the network, call :meth:`mark` right before
    triggering the power cycle, then :meth:`wait_removed` / :meth:`wait_added`
    to block on each event while the elapsed time is logged for profiling.

    Args:
        protocol: Communication type name, used to tag the profiling log lines.
    """

    protocol: str
    removed_event: threading.Event = field(default_factory=threading.Event)
    added_event: threading.Event = field(default_factory=threading.Event)
    _marked_at: float = field(default=0.0, init=False)

    def callback(self, event: NetDevEvt) -> None:
        """Store a listener event so the test thread can wait on it.

        Args:
            event: Net device event notified by the listener.
        """
        if event == NetDevEvt.REMOVED:
            self.removed_event.set()
        elif event == NetDevEvt.ADDED:
            self.added_event.set()

    def reset(self) -> None:
        """Clear both events so the recorder can be reused for another cycle."""
        self.removed_event.clear()
        self.added_event.clear()

    def mark(self) -> None:
        """Timestamp the power-cycle trigger; latencies are measured from here."""
        self._marked_at = time.perf_counter()

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
        tag = f" ({note})" if note else ""
        if detected:
            logger.info("[%s] drive %s%s detected after %.3f s", self.protocol, phase, tag, elapsed)
        else:
            logger.warning(
                "[%s] drive %s%s NOT detected within %.1f s", self.protocol, phase, tag, timeout
            )
        return detected
