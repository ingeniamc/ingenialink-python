"""
Reproduce INGK-1251 via the EXACT CI recovery path.

This simulates what happens in the real test suite:
  1. Connect to the drive via CanopenNetwork + connect_to_slave
  2. Bulk-read registers (like DriveContextManager.__enter__)
  3. Trigger restore_parameters
  4. User manually power-cycles
  5. Call recover_from_disconnection() (same as StatusListener does in CI)
  6. Read registers and check for "another SDO client" errors

This is different from reproduce_stale_sdo.py which does a clean
disconnect + fresh connect. Here we keep the same network alive and
trigger the recovery path.
"""

import argparse
import logging
import time

# Enable logging — only INFO level to avoid flood from heartbeats
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Show DEBUG only for our key modules
logging.getLogger("ingenialink.canopen.network").setLevel(logging.DEBUG)

from ingenialink.canopen.network import CanBaudrate, CanDevice, CanopenNetwork


def main() -> None:
    parser = argparse.ArgumentParser(description="INGK-1251 CI-path reproduction")
    parser.add_argument("--dictionary", required=True, help="XDF dictionary path")
    parser.add_argument("--node-id", type=int, default=32, help="CAN node ID")
    parser.add_argument("--channel", type=int, default=0, help="PCAN channel")
    parser.add_argument("--baudrate", type=int, default=1_000_000, help="CAN baudrate")
    args = parser.parse_args()

    node_id = args.node_id

    # ── Phase 1: Connect ──────────────────────────────────────────────────
    print(f"\n[Phase 1] Connecting to node {node_id}...")
    net = CanopenNetwork(
        device=CanDevice.PCAN,
        channel=args.channel,
        baudrate=CanBaudrate(args.baudrate),
    )
    nodes = net.scan_slaves()
    print(f"  Scanned nodes: {nodes}")
    if node_id not in nodes:
        # Retry once after a short delay
        time.sleep(1)
        nodes = net.scan_slaves()
        print(f"  Retry scanned nodes: {nodes}")
    if node_id not in nodes:
        print(f"  ERROR: Node {node_id} not found.")
        return

    servo = net.connect_to_slave(target=node_id, dictionary=args.dictionary)
    fw = servo.read("DRV_ID_SOFTWARE_VERSION")
    print(f"  Connected. FW: {fw}")

    # ── Phase 2: Bulk-read (simulate DriveContextManager.__enter__) ───────
    print("\n[Phase 2] Bulk-reading registers...")
    read_count = 0
    errors = 0
    for uid in servo.dictionary.registers(1):
        try:
            servo.read(uid, subnode=1)
            read_count += 1
        except Exception:
            errors += 1
    print(f"  Read {read_count}, errors {errors}")

    # ── Phase 3: Trigger restore ──────────────────────────────────────────
    print("\n[Phase 3] Triggering restore_parameters...")
    try:
        servo.restore_parameters()
        print("  Restore sent OK.")
    except Exception as e:
        print(f"  Restore raised: {e}")

    # ── Phase 4: Wait for drive to go down and come back ─────────────────
    print("\n[Phase 4] Waiting for drive to go down (bus errors = drive is off)...")
    print("  >>> POWER-CYCLE THE DRIVE NOW <<<")

    # Wait for the drive to become unreachable (bus errors = powered off)
    drive_went_down = False
    for _ in range(60):  # up to 60 seconds to turn it off
        try:
            servo.read("DRV_STATE_STATUS")
            time.sleep(1)
        except Exception:
            print("  Drive is OFF (read failed).")
            drive_went_down = True
            break

    if not drive_went_down:
        print("  WARNING: Drive never went down. Did you power-cycle it?")

    # Wait for the drive to come back (SDO reads succeed again)
    print("  Waiting for drive to come back (may take 10-30s)...")
    drive_came_back = False
    for attempt in range(120):  # up to 120 seconds
        try:
            # Use a raw SDO read via the canopen node to avoid ingenialink overhead
            node = servo.node
            vendor_id = node.sdo.upload(0x1018, 0x01)
            print(f"  Drive is BACK after ~{attempt}s (vendor_id={vendor_id.hex()})")
            drive_came_back = True
            break
        except Exception:
            time.sleep(1)

    if not drive_came_back:
        print("  ERROR: Drive did not come back within 120s. Aborting.")
        return

    # ── Phase 5: recover_from_disconnection (the CI path) ─────────────────
    print("\n[Phase 5] Calling recover_from_disconnection()...")
    t0 = time.monotonic()
    recovered = net.recover_from_disconnection()
    t1 = time.monotonic()
    print(f"  recover_from_disconnection() returned {recovered} in {t1-t0:.2f}s")

    if not recovered:
        print("  FAILED to recover. Aborting.")
        return

    # ── Phase 6: Read registers and check for stale SDO errors ────────────
    print("\n[Phase 6] Reading ALL registers to check for stale SDO errors...")
    ok_count = 0
    error_count = 0
    sdo_errors: list[str] = []
    other_errors: list[str] = []
    for uid in servo.dictionary.registers(1):
        try:
            servo.read(uid, subnode=1)
            ok_count += 1
        except Exception as e:
            error_count += 1
            err_str = str(e)
            if "another SDO client" in err_str.lower() or "Unexpected response" in err_str:
                sdo_errors.append(f"    {uid}: {err_str}")
            else:
                other_errors.append(f"    {uid}: {err_str}")

    print(f"  Reads: {ok_count} OK, {error_count} errors")

    if sdo_errors:
        print(f"\n  *** SDO MISMATCH ERRORS ({len(sdo_errors)}) ***")
        for s in sdo_errors[:30]:
            print(s)
        if len(sdo_errors) > 30:
            print(f"    ... and {len(sdo_errors) - 30} more")
    else:
        print("  No 'another SDO client' errors.")

    if other_errors:
        print(f"\n  Other errors ({len(other_errors)}):")
        for s in other_errors[:10]:
            print(s)

    # ── Phase 7: is_alive check (this is what test_enable_disable does) ───
    print("\n[Phase 7] Checking is_alive (simulating test_enable_disable)...")
    try:
        alive = servo.is_alive()
        print(f"  is_alive() = {alive}")
    except Exception as e:
        print(f"  is_alive() raised: {e}")

    # ── Cleanup ───────────────────────────────────────────────────────────
    print("\n[Cleanup] Disconnecting...")
    try:
        net.disconnect_from_slave(servo)
    except Exception as e:
        print(f"  Disconnect error: {e}")

    print(f"\n{'='*70}")
    print("DONE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
