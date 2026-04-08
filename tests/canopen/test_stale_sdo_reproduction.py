"""INGK-1251: Focused reproduction test for stale SDO responses after power cycle.

This test isolates the exact sequence that triggers stale SDO responses on
FW 2.9.0+ by repeating the power-cycle → recovery → register-scan cycle
multiple times with detailed diagnostics.

The test is intentionally simple and self-contained: it does NOT use
DriveContextManager so we can control the exact SDO traffic sequence.
"""

import logging
import struct
import time
from typing import TYPE_CHECKING

import pytest

from ingenialink.canopen.network import CanopenNetwork, SDOTracer
from ingenialink.enums.register import RegAccess

if TYPE_CHECKING:
    from summit_testing_framework.setups import Environment

    from ingenialink.canopen.servo import CanopenServo

logger = logging.getLogger(__name__)

# Number of power-cycle iterations.  More iterations = better statistics.
_NUM_ITERATIONS = 20

# Seconds to wait after recovery before starting the register scan.
# This is the "stale response arrival window".
_POST_RECOVERY_WAIT_S = 0.8

# Seconds to passively listen after the register scan.
_POST_SCAN_WAIT_S = 1.0


def _read_all_rw_registers(servo: "CanopenServo") -> list[tuple[str, int, int]]:
    """Read all readable+writable registers, emulating _store_register_data().

    Returns:
        List of (uid, index, subindex) for each register read.
    """
    read_order: list[tuple[str, int, int]] = []
    for uid, register in servo.dictionary.registers(subnode=0).items():
        if register.access in [RegAccess.WO, RegAccess.RO]:
            continue
        idx = getattr(register, "idx", None)
        subidx = getattr(register, "subidx", None)
        if idx is None or subidx is None:
            continue
        try:
            servo.read(uid, subnode=0)
            read_order.append((uid, idx, subidx))
        except Exception:  # noqa: PERF203
            pass  # Some registers may not be readable in all states
    return read_order


def _write_some_registers(servo: "CanopenServo", count: int = 5) -> list[str]:
    """Write a few registers (read → write same value) to generate SDO write traffic.

    Returns:
        List of UIDs that were written.
    """
    written: list[str] = []
    for uid, register in servo.dictionary.registers(subnode=0).items():
        if len(written) >= count:
            break
        if register.access not in [RegAccess.RW]:
            continue
        idx = getattr(register, "idx", None)
        if idx is None:
            continue
        try:
            val = servo.read(uid, subnode=0)
            servo.write(uid, val, subnode=0)
            written.append(uid)
        except Exception:  # noqa: PERF203
            continue
    return written


@pytest.mark.canopen
@pytest.mark.nightly
def test_stale_sdo_reproduction(
    net: CanopenNetwork,
    servo: "CanopenServo",
    environment: "Environment",
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Reproduce stale SDO responses across multiple power-cycle iterations.

    For each iteration:
      1. Read ALL registers (emulating DriveContextManager._store_register_data)
      2. Write a few registers (emulating test operations)
      3. Power cycle the drive
      4. Wait for recovery
      5. Wait _POST_RECOVERY_WAIT_S for delayed responses
      6. Attach SDOTracer
      7. Read ALL registers again (emulating force_restore read phase)
      8. Wait _POST_SCAN_WAIT_S for any trailing stale responses
      9. Report SDOTracer findings
    """
    assert net._connection is not None
    node_id = servo.target
    all_unsolicited_counts: list[int] = []

    # Initial sanity check
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    logger.info("REPRO: Starting stale SDO reproduction test. FW=%s node=%d", fw_version, node_id)

    for iteration in range(_NUM_ITERATIONS):
        logger.info("REPRO: ========== ITERATION %d/%d ==========", iteration + 1, _NUM_ITERATIONS)

        # Step 1: Read all registers (pre-power-cycle, like DCM __enter__)
        with caplog.at_level("DEBUG"):
            pre_regs = _read_all_rw_registers(servo)
            logger.info("REPRO: Pre-cycle read %d registers", len(pre_regs))

        # Step 2: Write a few registers
        written = _write_some_registers(servo, count=5)
        logger.info("REPRO: Pre-cycle wrote %d registers: %s", len(written), written)

        # Step 3: Power cycle
        logger.info("REPRO: Power cycling...")
        drives_reconnected = environment.power_cycle(
            wait_for_drives=False, reconnect_drives=True, reconnect_timeout=30
        )
        assert drives_reconnected, f"Iteration {iteration + 1}: drive did not recover"
        logger.info("REPRO: Drive recovered.")

        # Step 4: Wait for delayed SDO responses to arrive
        logger.info("REPRO: Waiting %.1fs for delayed SDO responses...", _POST_RECOVERY_WAIT_S)
        time.sleep(_POST_RECOVERY_WAIT_S)

        # Step 5: Drain the SDO queue (see what's accumulated during the wait)
        sdo_client = servo.node.sdo
        drained = 0
        while not sdo_client.responses.empty():
            try:
                stale_data = sdo_client.responses.get_nowait()
                if len(stale_data) >= 4:
                    idx = struct.unpack_from("<H", stale_data, 1)[0]
                    sub = stale_data[3]
                    logger.warning(
                        "REPRO: Drained stale response after wait: 0x%04X:%d raw=[%s]",
                        idx,
                        sub,
                        stale_data.hex(" "),
                    )
                drained += 1
            except Exception:  # noqa: PERF203
                break
        logger.info("REPRO: Drained %d stale responses from queue after wait", drained)

        # Step 6: Attach fresh SDOTracer
        # Stop any existing tracer first
        net._stop_sdo_tracer()
        node_ids: set[int] = {s.target for s in net.servos if isinstance(s.target, int)}
        tracer = SDOTracer(node_ids, network=net._connection)
        if net._connection is not None and net._connection.bus is not None:
            net._connection.notifier.add_listener(tracer)
            net._sdo_tracer = tracer
            logger.info("REPRO: Fresh SDOTracer attached.")

        # Step 7: Read ALL registers again (emulating force_restore read phase)
        post_regs = _read_all_rw_registers(servo)
        logger.info("REPRO: Post-cycle read %d registers", len(post_regs))

        # Step 8: Write some registers (emulating force_restore write phase)
        written2 = _write_some_registers(servo, count=5)
        logger.info("REPRO: Post-cycle wrote %d registers: %s", len(written2), written2)

        # Step 9: Wait for any trailing stale responses
        logger.info("REPRO: Waiting %.1fs for trailing stale responses...", _POST_SCAN_WAIT_S)
        time.sleep(_POST_SCAN_WAIT_S)

        # Step 10: Report SDOTracer findings
        logger.info("REPRO: Reporting SDOTracer for iteration %d", iteration + 1)
        tracer.report()
        net._stop_sdo_tracer()

        # Count unsolicited from the tracer frames
        unsolicited = 0
        expecting = False
        for frame in tracer._frames:
            if frame[3] == -1:
                continue
            if frame[1] == "TX>":
                expecting = True
            elif frame[1] == "RX<":
                if not expecting:
                    unsolicited += 1
                expecting = False
        all_unsolicited_counts.append(unsolicited)
        logger.info(
            "REPRO: Iteration %d complete. Unsolicited=%d, Drained=%d",
            iteration + 1,
            unsolicited,
            drained,
        )

    # Final summary
    logger.info("REPRO: ========== SUMMARY ==========")
    logger.info("REPRO: FW=%s node=%d", fw_version, node_id)
    logger.info("REPRO: Unsolicited counts per iteration: %s", all_unsolicited_counts)
    logger.info("REPRO: Total unsolicited: %d", sum(all_unsolicited_counts))

    total_unsolicited = sum(all_unsolicited_counts)
    if total_unsolicited > 0:
        logger.warning(
            "REPRO: STALE SDO RESPONSES DETECTED! %d total across %d iterations",
            total_unsolicited,
            _NUM_ITERATIONS,
        )
    else:
        logger.info("REPRO: No stale SDO responses detected across %d iterations", _NUM_ITERATIONS)

    # The test always passes — it's diagnostic, not a gating test
    # But we log a warning if stale responses are found
