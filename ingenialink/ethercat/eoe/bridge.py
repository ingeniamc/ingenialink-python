"""Userspace EoE-to-UDP bridge.

Tunnels MCB-over-UDP traffic to a drive through the EtherCAT mailbox using the
pysoem EoE API, with ARP/IPv4/UDP handled by a smoltcp-based userspace stack
(the ``eoe_stack`` extension). No TAP device or OS networking is involved, so
the bridge works without admin rights and is OS-independent.

The bridge attaches to an already-connected slave (see
:meth:`ingenialink.ethercat.servo.EthercatServo.bind_eoe`) and exposes a plain
UDP relay socket on localhost, so a stock ``EthernetNetwork`` can connect to
the drive as if it were a wired Ethernet drive::

    ingenialink UDP datagram <-> localhost relay <-> eoe_stack (ARP/IPv4/UDP) <-> EoE mailbox
"""

import socket
import threading
import time
from typing import TYPE_CHECKING, Optional

import ingenialogger
from eoe_stack import UdpStack

from ingenialink.exceptions import ILError

if TYPE_CHECKING:
    from pysoem import CdefSlave

logger = ingenialogger.get_logger(__name__)

MCB_UDP_PORT = 1061


class EoEUdpBridge:
    """Bridges UDP datagrams on a localhost socket to EoE frames of a single slave.

    The bridge assigns the slave an IP address over EoE and relays UDP payloads
    between a localhost socket and the EtherCAT mailbox. The UDP source port of
    each localhost client is preserved on the EoE side, so responses are routed
    back statelessly.

    All mailbox accesses are serialized through ``mailbox_lock``. Passing the
    owning servo's SDO lock keeps the bridge's mailbox polling from interleaving
    with concurrent SDO transfers on the CoE side.

    Args:
        slave: Slave to attach to, already initialized by an EtherCAT master.
        mailbox_lock: Lock serializing mailbox access with other users of the
            slave. A private lock is created if not provided.
        host_ip: IP address of the host side of the EoE link.
        drive_ip: IP address to assign to the drive over EoE.
    """

    HOST_MAC = "02:aa:bb:cc:dd:01"
    DRIVE_MAC = "02:aa:bb:cc:dd:02"
    NETMASK = "255.255.255.0"
    PREFIX_LEN = 24
    LOOP_PERIOD_S = 0.001
    MAILBOX_ERROR_BACKOFF_S = 0.1
    SII_MAILBOX_PROTOCOL_WORD_ADDRESS = 0x1C
    SII_EEPROM_TIMEOUT_US = 200_000
    EOE_PROTOCOL_BIT = 0x2

    def __init__(
        self,
        slave: "CdefSlave",
        mailbox_lock: Optional[threading.Lock] = None,
        host_ip: str = "192.168.100.1",
        drive_ip: str = "192.168.100.2",
    ) -> None:
        self._slave = slave
        self._master = slave._master
        self._mailbox_lock = mailbox_lock if mailbox_lock is not None else threading.Lock()
        self._host_ip = host_ip
        self._drive_ip = drive_ip
        self._slave_num = 0
        self._stack = UdpStack(self.HOST_MAC, host_ip, self.PREFIX_LEN)
        self._running = False
        self._bridge_thread = threading.Thread(target=self._bridge_loop, daemon=True)
        self._relay_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._client_ports: set[int] = set()
        self._drive_ip_settings: list[Optional[str]] = []

    @property
    def drive_ip_settings(self) -> list[Optional[str]]:
        """EoE IP settings read back from the slave when the bridge was opened.

        A ``[mac, ip, netmask, gateway, dns_ip, dns_name]`` list, with ``None``
        for settings the slave does not report. Empty until :meth:`open` is called.
        """
        return self._drive_ip_settings

    @property
    def drive_ip(self) -> str:
        """Effective IP address of the drive on the EoE link."""
        return self._drive_ip

    @property
    def host_ip(self) -> str:
        """Effective IP address of the host side of the EoE link."""
        return self._host_ip

    @property
    def relay_port(self) -> int:
        """UDP port on localhost where the relay socket is listening."""
        port: int = self._relay_sock.getsockname()[1]
        return port

    def open(self) -> None:
        """Configure the EoE link addresses and start bridging.

        First tries to assign ``drive_ip`` to the slave over EoE (without
        forcing a MAC address, which some EoE stacks reject). If the slave
        refuses, it falls back to the IP settings the slave already reports
        (Summit drives ship with a default EoE IP) and moves the host to that
        subnet.

        Raises:
            ILError: If the slave does not support EoE, or its IP can neither
                be set nor read back.
        """
        self._slave_num = self._master.slaves.index(self._slave) + 1
        with self._mailbox_lock:
            supported_protocols = int.from_bytes(
                self._slave.eeprom_read(
                    self.SII_MAILBOX_PROTOCOL_WORD_ADDRESS, self.SII_EEPROM_TIMEOUT_US
                )[:2],
                "little",
            )
            if not supported_protocols & self.EOE_PROTOCOL_BIT:
                raise ILError(
                    f"Slave {self._slave_num} does not advertise EoE mailbox support "
                    f"(SII mailbox protocols: {supported_protocols:#06x})"
                )
            set_wkc = self._slave.eoe_set_ip(ip=self._drive_ip, netmask=self.NETMASK)
            self._drive_ip_settings = self._slave.eoe_get_ip()
        reported_ip = self._drive_ip_settings[1] if len(self._drive_ip_settings) > 1 else None
        if set_wkc <= 0:
            if reported_ip is None:
                raise ILError(
                    f"Failed to set EoE IP settings on slave {self._slave_num} "
                    f"(wkc={set_wkc}) and the slave reports no current IP "
                    f"(settings: {self._drive_ip_settings})"
                )
            logger.warning(
                f"Slave {self._slave_num} refused the EoE IP assignment (wkc={set_wkc}), "
                f"falling back to its reported settings: {self._drive_ip_settings}"
            )
            self._drive_ip = reported_ip
            self._host_ip = self._derive_host_ip(reported_ip)
        elif reported_ip is not None:
            self._drive_ip = reported_ip
        # Rebuild the stack in case the host address moved to the drive's subnet
        self._stack = UdpStack(self.HOST_MAC, self._host_ip, self.PREFIX_LEN)
        self._master.set_eoe_callback(self._on_eoe_frame)
        self._relay_sock.bind(("127.0.0.1", 0))
        self._relay_sock.setblocking(False)
        self._running = True
        self._bridge_thread.start()

    @staticmethod
    def _derive_host_ip(drive_ip: str) -> str:
        """Pick a host IP on the same /24 subnet as the drive.

        Args:
            drive_ip: IP address reported by the drive.

        Returns:
            An IP address with the same first three octets and a different
            last octet.
        """
        octets = drive_ip.split(".")
        last_octet = "250" if octets[3] != "250" else "251"
        return ".".join([*octets[:3], last_octet])

    def close(self) -> None:
        """Stop bridging and detach from the slave. The CoE connection is unaffected."""
        self._running = False
        if self._bridge_thread.is_alive():
            self._bridge_thread.join(timeout=2.0)
        self._master.set_eoe_callback(None)
        self._relay_sock.close()

    def _bridge_loop(self) -> None:
        """Move data between the localhost socket, the stack and the EoE mailbox."""
        while self._running:
            self._service_mailbox()
            self._forward_localhost_to_stack()
            self._stack.poll()
            self._flush_stack_to_drive()
            self._deliver_stack_to_localhost()
            time.sleep(self.LOOP_PERIOD_S)

    def _service_mailbox(self) -> None:
        """Service the slave mailbox so inbound EoE fragments are processed."""
        try:
            with self._mailbox_lock:
                self._slave.mbx_receive()
        except Exception as exc:
            logger.warning(f"Mailbox error: {exc}")
            time.sleep(self.MAILBOX_ERROR_BACKOFF_S)

    def _on_eoe_frame(self, frame: bytes, slave_num: int) -> None:
        """Queue a reassembled Ethernet frame received from the slave over EoE.

        Args:
            frame: Complete Ethernet frame received.
            slave_num: 1-based position of the slave that sent the frame.
        """
        if slave_num == self._slave_num:
            self._stack.push_frame(frame)

    def _forward_localhost_to_stack(self) -> None:
        """Feed datagrams received on the localhost socket into the stack."""
        while True:
            try:
                payload, (_, client_port) = self._relay_sock.recvfrom(4096)
            except (BlockingIOError, OSError):
                return
            self._client_ports.add(client_port)
            self._stack.send(client_port, self._drive_ip, MCB_UDP_PORT, payload)

    def _flush_stack_to_drive(self) -> None:
        """Send all Ethernet frames produced by the stack to the slave over EoE."""
        frame = self._stack.pop_frame()
        while frame is not None:
            with self._mailbox_lock:
                self._slave.eoe_send_data(frame)
            frame = self._stack.pop_frame()

    def _deliver_stack_to_localhost(self) -> None:
        """Deliver UDP payloads received by the stack back to the localhost clients."""
        for port in self._client_ports:
            datagram = self._stack.recv(port)
            while datagram is not None:
                payload, _, _ = datagram
                self._relay_sock.sendto(payload, ("127.0.0.1", port))
                datagram = self._stack.recv(port)
