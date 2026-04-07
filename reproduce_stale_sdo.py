"""
Standalone reproduction script for INGK-1251: stale SDO responses after power cycle.

This script validates whether the Capitan firmware sends unsolicited SDO response
frames after a restore-all + manual power cycle. It does NOT use pytest.

Sequence:
  1. Connect to the CANopen Capitan drive
  2. Read a batch of registers (simulating DriveContextManager.__enter__)
  3. Trigger restore_parameters (writes DRV_RESTORE_COCO_ALL)
  4. Prompt user to manually power-cycle the drive
  5. Passively listen on the CAN bus WITHOUT sending any SDO requests
  6. Report any unsolicited SDO response frames received
  7. Reconnect and do active reads to check for "another SDO client" errors

Usage:
  python reproduce_stale_sdo.py --dictionary cap-net-c_can_2.9.0_v2.xdf
  python reproduce_stale_sdo.py --dictionary cap-net-c_can_2.9.0_v2.xdf --passive-wait 10
"""

import argparse
import struct
import time

import can

# ── Constants ──────────────────────────────────────────────────────────────────
SDO_TX_COBID_BASE = 0x580  # SDO response from server: 0x580 + node_id
SDO_RX_COBID_BASE = 0x600  # SDO request to server:   0x600 + node_id
NMT_HEARTBEAT_COBID_BASE = 0x700  # NMT heartbeat: 0x700 + node_id


class PassiveSDOListener(can.Listener):
    """CAN listener that records all SDO response frames without sending anything."""

    def __init__(self, node_id: int):
        self.node_id = node_id
        self.sdo_response_cobid = SDO_TX_COBID_BASE + node_id
        self.heartbeat_cobid = NMT_HEARTBEAT_COBID_BASE + node_id
        self.sdo_responses: list[tuple[float, can.Message]] = []
        self.heartbeats: list[tuple[float, can.Message]] = []
        self.start_time = time.monotonic()

    def on_message_received(self, msg: can.Message) -> None:
        elapsed = time.monotonic() - self.start_time
        if msg.arbitration_id == self.sdo_response_cobid:
            self.sdo_responses.append((elapsed, msg))
        elif msg.arbitration_id == self.heartbeat_cobid:
            self.heartbeats.append((elapsed, msg))

    def report(self) -> None:
        print(f"\n{'='*70}")
        print("PASSIVE LISTENER REPORT")
        print(f"{'='*70}")
        print(f"Heartbeats received: {len(self.heartbeats)}")
        print(f"SDO responses received (unsolicited): {len(self.sdo_responses)}")

        if self.sdo_responses:
            print(f"\n{'!'*70}")
            print("FIRMWARE IS SENDING UNSOLICITED SDO RESPONSES!")
            print(f"{'!'*70}")
            for elapsed, msg in self.sdo_responses:
                data_hex = msg.data.hex(" ")
                # Parse SDO response: byte 0 = command, bytes 1-2 = index, byte 3 = subindex
                if len(msg.data) >= 4:
                    cmd = msg.data[0]
                    index = struct.unpack_from("<H", msg.data, 1)[0]
                    subindex = msg.data[3]
                    print(
                        f"  t={elapsed:7.3f}s  "
                        f"cmd=0x{cmd:02X}  "
                        f"index=0x{index:04X}:{subindex}  "
                        f"raw=[{data_hex}]"
                    )
                else:
                    print(f"  t={elapsed:7.3f}s  raw=[{data_hex}]")
        else:
            print("\nNo unsolicited SDO responses detected.")
            print("The stale responses are likely a reaction to host SDO requests (queue desync).")

        if self.heartbeats:
            first_hb = self.heartbeats[0][0]
            last_hb = self.heartbeats[-1][0]
            print(f"\nFirst heartbeat at t={first_hb:.3f}s, last at t={last_hb:.3f}s")


def wait_for_any_traffic(bus: can.Bus, node_id: int, timeout: float = 60.0) -> bool:
    """Wait for ANY CAN frame from the node (heartbeat, SDO, NMT boot-up, etc.)."""
    target_ids = {
        SDO_TX_COBID_BASE + node_id,
        NMT_HEARTBEAT_COBID_BASE + node_id,
        0x80 + node_id,  # EMCY
        0x00,  # NMT
    }
    print(f"  Waiting for CAN traffic from node {node_id} (timeout={timeout}s)...")
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        msg = bus.recv(timeout=1.0)
        if msg and msg.arbitration_id in target_ids:
            elapsed = time.monotonic() - start
            print(
                f"  Traffic detected after {elapsed:.1f}s: "
                f"id=0x{msg.arbitration_id:03X} data={msg.data.hex(' ')}"
            )
            return True
    return False


def wait_for_node_sdo_ready(bus: can.Bus, node_id: int, timeout: float = 60.0) -> bool:
    """Probe the node with SDO reads until it responds (polls Vendor ID 0x1018:01)."""
    import struct as _struct

    sdo_rx_cobid = SDO_RX_COBID_BASE + node_id
    sdo_tx_cobid = SDO_TX_COBID_BASE + node_id
    # SDO upload request for 0x1018:01 (Vendor ID)
    sdo_request = bytearray(8)
    sdo_request[0] = 0x40  # initiate upload
    _struct.pack_into("<H", sdo_request, 1, 0x1018)
    sdo_request[3] = 0x01
    print(f"  Probing node {node_id} with SDO reads (timeout={timeout}s)...")
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        # Send SDO upload request
        bus.send(can.Message(arbitration_id=sdo_rx_cobid, data=sdo_request, is_extended_id=False))
        # Wait for response
        resp_start = time.monotonic()
        while time.monotonic() - resp_start < 1.0:
            msg = bus.recv(timeout=0.5)
            if msg and msg.arbitration_id == sdo_tx_cobid:
                elapsed = time.monotonic() - start
                print(
                    f"  Node responded after {elapsed:.1f}s: "
                    f"data={msg.data.hex(' ')}"
                )
                return True
        # No response yet, retry after a short pause
        time.sleep(0.5)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce INGK-1251 stale SDO responses")
    parser.add_argument("--dictionary", required=True, help="Path to the XDF dictionary file")
    parser.add_argument("--node-id", type=int, default=32, help="CAN node ID (default: 32)")
    parser.add_argument("--channel", type=int, default=0, help="PCAN channel (default: 0)")
    parser.add_argument("--baudrate", type=int, default=1_000_000, help="CAN baudrate")
    parser.add_argument(
        "--passive-wait",
        type=float,
        default=5.0,
        help="Seconds to passively listen after drive comes back (default: 5)",
    )
    parser.add_argument(
        "--skip-bulk-read",
        action="store_true",
        help="Skip the initial bulk register read before restore",
    )
    args = parser.parse_args()

    node_id = args.node_id
    dictionary = args.dictionary

    # ── Phase 1: Connect and optionally bulk-read registers ────────────────
    print(f"\n[Phase 1] Connecting to node {node_id} via PCAN...")
    from ingenialink.canopen.network import CanBaudrate, CanDevice, CanopenNetwork

    net = CanopenNetwork(
        device=CanDevice.PCAN,
        channel=args.channel,
        baudrate=CanBaudrate(args.baudrate),
    )
    nodes = net.scan_slaves()
    print(f"  Scanned nodes: {nodes}")
    if node_id not in nodes:
        print(f"  ERROR: Node {node_id} not found. Available: {nodes}")
        return

    servo = net.connect_to_slave(target=node_id, dictionary=dictionary)
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    print(f"  Connected. FW version: {fw_version}")

    if not args.skip_bulk_read:
        print("\n[Phase 1b] Bulk-reading registers (simulating DriveContextManager)...")
        read_count = 0
        errors = 0
        for uid, reg in servo.dictionary.registers(1).items():
            try:
                servo.read(uid, subnode=1)
                read_count += 1
            except Exception:
                errors += 1
        print(f"  Read {read_count} registers, {errors} errors")

    # ── Phase 2: Trigger restore_parameters ────────────────────────────────
    print("\n[Phase 2] Triggering restore_parameters (DRV_RESTORE_COCO_ALL)...")
    try:
        servo.restore_parameters()
        print("  Restore command sent successfully.")
    except Exception as e:
        print(f"  Restore raised: {e} (may be expected)")

    # ── Phase 3: Disconnect cleanly ───────────────────────────────────────
    print("\n[Phase 3] Disconnecting from the network...")
    try:
        net.disconnect_from_slave(servo)
    except Exception as e:
        print(f"  Disconnect error (expected): {e}")

    # ── Phase 4: Manual power cycle + passive listen ──────────────────────
    print("\n[Phase 4] Opening raw CAN bus for passive listening...")
    bus = can.Bus(
        interface="pcan",
        channel=f"PCAN_USBBUS{args.channel + 1}",
        bitrate=args.baudrate,
    )
    try:
        print("\n" + "=" * 70)
        print("ACTION REQUIRED: Please power-cycle the drive now.")
        print("  1. Turn OFF the drive power")
        print("  2. Wait 2-3 seconds")
        print("  3. Turn ON the drive power")
        input("Press ENTER after you have power-cycled the drive...")
        print("=" * 70)

        # Start passive listener IMMEDIATELY — before any SDO probes
        print(f"\n[Phase 5] Passive listening for {args.passive_wait}s "
              "(NO SDO requests sent)...")
        listener = PassiveSDOListener(node_id)
        notifier = can.Notifier(bus, [listener])

        time.sleep(args.passive_wait)

        notifier.stop()
        listener.report()

        # ── Phase 6: Now do active reads and see if they get corrupted ─────
        print(f"\n[Phase 6] Reconnecting via ingenialink and reading registers...")
        bus.shutdown()
        bus = None  # Mark as shut down so finally doesn't double-shutdown

        net2 = CanopenNetwork(
            device=CanDevice.PCAN,
            channel=args.channel,
            baudrate=CanBaudrate(args.baudrate),
        )
        nodes2 = net2.scan_slaves()
        print(f"  Scanned nodes: {nodes2}")
        if node_id not in nodes2:
            print(f"  ERROR: Node {node_id} not found after reboot.")
            return

        servo2 = net2.connect_to_slave(target=node_id, dictionary=dictionary)
        fw2 = servo2.read("DRV_ID_SOFTWARE_VERSION")
        print(f"  Reconnected. FW version: {fw2}")

        print("  Reading registers to check for 'another SDO client' errors...")
        ok_count = 0
        error_count = 0
        sdo_errors: list[str] = []
        other_errors: list[str] = []
        for uid, _reg in servo2.dictionary.registers(1).items():
            try:
                servo2.read(uid, subnode=1)
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
            print(f"\n  SDO MISMATCH errors ({len(sdo_errors)}):")
            for s in sdo_errors[:30]:
                print(s)
            if len(sdo_errors) > 30:
                print(f"    ... and {len(sdo_errors) - 30} more")
        if other_errors:
            print(f"\n  Other errors ({len(other_errors)}):")
            for s in other_errors[:10]:
                print(s)
            if len(other_errors) > 10:
                print(f"    ... and {len(other_errors) - 10} more")
        if not sdo_errors:
            print("  No SDO mismatch errors detected during active reads.")

        net2.disconnect_from_slave(servo2)
    finally:
        if bus is not None:
            try:
                bus.shutdown()
            except Exception:
                pass

    print(f"\n{'='*70}")
    print("DONE")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
