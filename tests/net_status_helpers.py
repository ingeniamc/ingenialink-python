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

    Subscribe :meth:`callback` to the network and, after triggering a power
    cycle, use :meth:`wait_for` to block on the REMOVED/ADDED events while
    measuring how long the library took to react.

    Args:
        protocol: Communication type name, used to tag the profiling log lines.
    """

    protocol: str
    removed_event: threading.Event = field(default_factory=threading.Event)
    added_event: threading.Event = field(default_factory=threading.Event)

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

    def wait_for(
        self, event: threading.Event, timeout: float, since: float, phase: str
    ) -> tuple[bool, float]:
        """Wait for an event and log how long the library took to reach it.

        Args:
            event: The ``removed_event`` or ``added_event`` to wait on.
            timeout: Maximum time to wait, in seconds.
            since: ``time.perf_counter`` timestamp when the power cycle was triggered.
            phase: Human-readable phase name, e.g. ``"disconnection"``.

        Returns:
            Tuple of ``(detected, elapsed_seconds)``. ``elapsed_seconds`` is the
            time from ``since`` until the event fired, or until ``timeout`` if it
            never did.
        """
        detected = event.wait(timeout=timeout)
        elapsed = time.perf_counter() - since
        if detected:
            logger.info("[%s] drive %s detected after %.3f s", self.protocol, phase, elapsed)
        else:
            logger.warning(
                "[%s] drive %s NOT detected within %.1f s", self.protocol, phase, timeout
            )
        return detected, elapsed
