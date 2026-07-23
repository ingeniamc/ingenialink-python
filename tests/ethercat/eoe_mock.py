"""Fake pysoem EoE slave backed by a virtual drive.

Emulates the pysoem surface :class:`ingenialink.ethercat.eoe.EoEUdpBridge`
uses (``eeprom_read``, ``eoe_set_ip``, ``eoe_get_ip``, ``eoe_send_data``,
``mbx_receive`` and the master EoE callback) and implements the drive side of
the EoE link: it answers ARP requests for the drive IP and relays UDP
datagrams addressed to the MCB port to a :class:`virtual_drive.core.VirtualDrive`
server, so the whole bridge path can be exercised without hardware.
"""

import socket
import struct
from collections import deque
from typing import Callable, Optional

ETHERTYPE_ARP = 0x0806
ETHERTYPE_IPV4 = 0x0800
ARP_REQUEST = 1
ARP_REPLY = 2
IP_PROTO_UDP = 17
ETH_HEADER_SIZE = 14
ARP_OPERATION_OFFSET = 20
IPV4_MIN_FRAME_SIZE = 34
MCB_UDP_PORT = 1061


def _mac_bytes(mac: str) -> bytes:
    return bytes.fromhex(mac.replace(":", ""))


def _checksum(data: bytes) -> int:
    """Compute the ones' complement checksum used by IPv4 and UDP.

    Args:
        data: Bytes to checksum, zero-padded to an even length.

    Returns:
        The 16-bit checksum.
    """
    if len(data) % 2:
        data += b"\x00"
    total: int = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while total > 0xFFFF:
        total = (total & 0xFFFF) + (total >> 16)
    return ~total & 0xFFFF


class FakeEoEDrive:
    """Drive-side endpoint of the EoE link.

    Answers ARP requests for its IP and relays MCB-over-UDP payloads to a
    virtual drive server on localhost.

    Args:
        mac: MAC address of the drive on the EoE link.
        ip: IP address of the drive on the EoE link.
        virtual_drive_port: UDP port of the virtual drive server on localhost.
    """

    def __init__(self, mac: str, ip: str, virtual_drive_port: int) -> None:
        self.mac = mac
        self.ip = ip
        self._virtual_drive_address = ("127.0.0.1", virtual_drive_port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(2.0)
        self._ip_identification = 0

    def close(self) -> None:
        """Release the relay socket to the virtual drive."""
        self._sock.close()

    def handle_frame(self, frame: bytes) -> list[bytes]:
        """Process one Ethernet frame sent to the drive over EoE.

        Args:
            frame: Raw Ethernet frame received from the host.

        Returns:
            Ethernet frames the drive sends back, if any.
        """
        if len(frame) < ETH_HEADER_SIZE:
            return []
        ethertype = int.from_bytes(frame[12:14], "big")
        if ethertype == ETHERTYPE_ARP:
            return self._handle_arp(frame)
        if ethertype == ETHERTYPE_IPV4:
            return self._handle_ipv4(frame)
        return []

    def _handle_arp(self, frame: bytes) -> list[bytes]:
        """Reply to ARP requests that target the drive IP.

        Args:
            frame: ARP frame received from the host.

        Returns:
            A single ARP reply frame, or nothing if the request is not for
            the drive.
        """
        operation = int.from_bytes(frame[ARP_OPERATION_OFFSET : ARP_OPERATION_OFFSET + 2], "big")
        sender_mac = frame[22:28]
        sender_ip = frame[28:32]
        target_ip = frame[38:42]
        if operation != ARP_REQUEST or target_ip != socket.inet_aton(self.ip):
            return []
        arp_reply = struct.pack(
            "!HHBBH6s4s6s4s",
            1,  # Hardware type: Ethernet
            ETHERTYPE_IPV4,
            6,  # Hardware address length
            4,  # Protocol address length
            ARP_REPLY,
            _mac_bytes(self.mac),
            socket.inet_aton(self.ip),
            sender_mac,
            sender_ip,
        )
        header = sender_mac + _mac_bytes(self.mac) + ETHERTYPE_ARP.to_bytes(2, "big")
        return [header + arp_reply]

    def _handle_ipv4(self, frame: bytes) -> list[bytes]:
        """Relay a UDP datagram addressed to the drive MCB port.

        Args:
            frame: IPv4 frame received from the host.

        Returns:
            A single UDP response frame from the virtual drive, or nothing if
            the frame is not an MCB request or the drive does not answer.
        """
        if len(frame) < IPV4_MIN_FRAME_SIZE:
            return []
        header_length = (frame[14] & 0x0F) * 4
        protocol = frame[23]
        dst_ip = frame[30:34]
        if protocol != IP_PROTO_UDP or dst_ip != socket.inet_aton(self.ip):
            return []
        udp_offset = ETH_HEADER_SIZE + header_length
        src_port, dst_port, udp_length = struct.unpack("!HHH", frame[udp_offset : udp_offset + 6])
        if dst_port != MCB_UDP_PORT:
            return []
        payload = frame[udp_offset + 8 : udp_offset + udp_length]
        self._sock.sendto(payload, self._virtual_drive_address)
        try:
            response = self._sock.recv(4096)
        except TimeoutError:
            return []
        host_mac = frame[6:12]
        host_ip = frame[26:30]
        return [self._build_udp_frame(host_mac, host_ip, src_port, response)]

    def _build_udp_frame(
        self, host_mac: bytes, host_ip: bytes, host_port: int, payload: bytes
    ) -> bytes:
        """Wrap a UDP payload into an Ethernet frame addressed to the host.

        Args:
            host_mac: Destination MAC address.
            host_ip: Destination IP address, packed.
            host_port: Destination UDP port.
            payload: UDP payload.

        Returns:
            The complete Ethernet frame.
        """
        drive_ip = socket.inet_aton(self.ip)
        udp_length = 8 + len(payload)
        udp_header = struct.pack("!HHHH", MCB_UDP_PORT, host_port, udp_length, 0)
        pseudo_header = drive_ip + host_ip + struct.pack("!BBH", 0, IP_PROTO_UDP, udp_length)
        udp_checksum = _checksum(pseudo_header + udp_header + payload) or 0xFFFF
        udp_header = udp_header[:6] + udp_checksum.to_bytes(2, "big")
        self._ip_identification = (self._ip_identification + 1) & 0xFFFF
        ip_header = struct.pack(
            "!BBHHHBBH4s4s",
            0x45,  # Version 4, header length 20
            0,  # DSCP/ECN
            20 + udp_length,
            self._ip_identification,
            0,  # Flags and fragment offset
            64,  # TTL
            IP_PROTO_UDP,
            0,  # Checksum placeholder
            drive_ip,
            host_ip,
        )
        ip_header = ip_header[:10] + _checksum(ip_header).to_bytes(2, "big") + ip_header[12:]
        header = host_mac + _mac_bytes(self.mac) + ETHERTYPE_IPV4.to_bytes(2, "big")
        return header + ip_header + udp_header + payload


class FakeEoEMaster:
    """Master half of the fake pysoem surface used by the bridge."""

    def __init__(self) -> None:
        self.slaves: list[FakeEoESlave] = []
        self.eoe_callback: Optional[Callable[[bytes, int], None]] = None

    def set_eoe_callback(self, callback: Optional[Callable[[bytes, int], None]]) -> None:
        """Register the callback invoked with reassembled EoE frames.

        Args:
            callback: Callable receiving ``(frame, slave_num)``, or ``None``
                to unregister.
        """
        self.eoe_callback = callback


class FakeEoESlave:
    """Slave half of the fake pysoem surface used by the bridge.

    Args:
        drive: Drive-side endpoint that consumes and produces Ethernet frames.
        accept_set_ip: Whether the slave accepts EoE IP assignments. When
            ``False`` it keeps ``drive.ip``, mimicking drives that refuse the
            SET_IP_PARAMETER request.
        supports_eoe: Whether the SII advertises EoE mailbox support.
        report_unspecified_ip: When ``True``, ``eoe_get_ip`` always reports
            0.0.0.0, mimicking drives whose EoE stack does not persist the
            assigned IP in the reported settings.
    """

    COE_PROTOCOL_BIT = 0x04
    EOE_PROTOCOL_BIT = 0x02
    # frameinfo2 of an EoE data fragment, as SOEM returns it when a queued
    # data frame is misread as the SET_IP response
    DESYNC_WKC = -0x1080

    def __init__(
        self,
        drive: FakeEoEDrive,
        accept_set_ip: bool = True,
        supports_eoe: bool = True,
        report_unspecified_ip: bool = False,
    ) -> None:
        self._drive = drive
        self._accept_set_ip = accept_set_ip
        self._supports_eoe = supports_eoe
        self._report_unspecified_ip = report_unspecified_ip
        self._netmask: Optional[str] = "255.255.255.0" if not accept_set_ip else None
        self._pending_frames: deque[bytes] = deque()
        self.sent_frames: list[bytes] = []
        self._master = FakeEoEMaster()
        self._master.slaves.append(self)

    def queue_unsolicited_frame(self, frame: bytes) -> None:
        """Queue an unsolicited EoE frame, as chatty drives do on link-up.

        While unsolicited frames are pending, the IP handshake fails the way
        SOEM fails on a desynchronized mailbox: ``eoe_set_ip`` returns a
        negative working counter and ``eoe_get_ip`` returns garbage settings.
        The bridge must drain the mailbox (with the EoE callback installed)
        before the handshake to succeed.

        Args:
            frame: Raw Ethernet frame the drive pushes on its own.
        """
        self._pending_frames.append(frame)

    def eeprom_read(self, word_address: int, timeout_us: int) -> bytes:  # noqa: ARG002
        """Return the SII mailbox protocols word.

        Args:
            word_address: SII word address, expected to be the mailbox
                protocols word.
            timeout_us: Ignored.

        Returns:
            Two little-endian bytes with the supported mailbox protocols.
        """
        protocols = self.COE_PROTOCOL_BIT
        if self._supports_eoe:
            protocols |= self.EOE_PROTOCOL_BIT
        return protocols.to_bytes(2, "little")

    def eoe_set_ip(self, **settings: Optional[str]) -> int:
        """Assign EoE IP settings to the slave.

        Args:
            **settings: ``ip``, ``netmask``, ... as accepted by pysoem.

        Returns:
            The mailbox working counter: 1 on success, 0 when refused, or a
            negative value when a pending unsolicited frame desynchronizes
            the exchange.
        """
        if self._pending_frames:
            return self.DESYNC_WKC
        if not self._accept_set_ip:
            return 0
        ip = settings.get("ip")
        if ip is not None:
            self._drive.ip = ip
        self._netmask = settings.get("netmask")
        return 1

    def eoe_get_ip(self) -> list[Optional[str]]:
        """Report the current EoE IP settings.

        Returns:
            A pysoem-style ``[mac, ip, netmask, gateway, dns_ip, dns_name]``
            list. Garbage settings while an unsolicited frame is pending,
            mimicking SOEM parsing a data frame as the response.
        """
        if self._pending_frames:
            return ["00:00:00:00:00:00", "0.0.32.0", None, None, None, None]
        if self._report_unspecified_ip:
            return [self._drive.mac, "0.0.0.0", self._netmask, None, None, None]
        return [self._drive.mac, self._drive.ip, self._netmask, None, None, None]

    def eoe_send_data(self, data: bytes) -> int:
        """Consume one Ethernet frame sent by the host over EoE.

        Args:
            data: Raw Ethernet frame.

        Returns:
            The mailbox working counter (always 1).
        """
        self.sent_frames.append(data)
        self._pending_frames.extend(self._drive.handle_frame(data))
        return 1

    def mbx_receive(self) -> int:
        """Deliver one pending drive frame through the master EoE callback.

        Returns:
            The mailbox working counter: 1 if a frame was delivered, 0 if the
            mailbox was empty.
        """
        if not self._pending_frames or self._master.eoe_callback is None:
            return 0
        slave_num = self._master.slaves.index(self) + 1
        self._master.eoe_callback(self._pending_frames.popleft(), slave_num)
        return 1
