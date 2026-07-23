"""Tests for the EoE-to-UDP bridge against a fake EoE slave and a virtual drive.

The pysoem surface is emulated by :mod:`tests.ethercat.eoe_mock`, so the whole
bridge path (localhost relay, smoltcp stack, ARP resolution, EoE framing) is
exercised without hardware. Only the real SOEM mailbox mechanics and the drive
firmware are out of scope.
"""

from collections.abc import Generator

import pytest

pytest.importorskip("eoe_stack", reason="the eoe_stack extension is not installed")

from virtual_drive.core import VirtualDrive  # noqa: E402

from ingenialink.dictionary import Interface  # noqa: E402
from ingenialink.ethercat.eoe import EoEUdpBridge  # noqa: E402
from ingenialink.ethernet.network import EthernetNetwork  # noqa: E402
from ingenialink.exceptions import ILError  # noqa: E402
from tests.ethercat.eoe_mock import FakeEoEDrive, FakeEoESlave  # noqa: E402

DRIVE_MAC = "02:11:22:33:44:55"
DEFAULT_DRIVE_IP = "192.168.2.22"


@pytest.fixture
def virtual_drive_server() -> Generator[VirtualDrive, None, None]:
    """Yield a running virtual drive server."""
    server = VirtualDrive(protocol=Interface.ETH)
    server.start()
    yield server
    if server.is_alive():
        server.stop()


@pytest.fixture
def fake_slave(virtual_drive_server: VirtualDrive) -> Generator[FakeEoESlave, None, None]:
    """Yield a fake EoE slave whose drive side relays MCB requests to the virtual drive."""
    drive = FakeEoEDrive(DRIVE_MAC, DEFAULT_DRIVE_IP, virtual_drive_server.port)
    yield FakeEoESlave(drive)
    drive.close()


@pytest.fixture
def eoe_bridge(fake_slave: FakeEoESlave) -> Generator[EoEUdpBridge, None, None]:
    """Yield an opened bridge attached to the fake slave."""
    bridge = EoEUdpBridge(fake_slave)
    bridge.open()
    yield bridge
    bridge.close()


def _read_product_code_through_relay(bridge: EoEUdpBridge, dictionary: str) -> int:
    """Connect through the bridge relay and read the product code register.

    Args:
        bridge: Opened bridge to connect through.
        dictionary: Path to the drive dictionary.

    Returns:
        The value of the product code register.
    """
    net = EthernetNetwork()
    servo = net.connect_to_slave("127.0.0.1", dictionary, port=bridge.relay_port, is_eoe=True)
    try:
        product_code = servo.read("DRV_ID_PRODUCT_CODE")
    finally:
        net.disconnect_from_slave(servo)
    assert isinstance(product_code, int)
    return product_code


@pytest.mark.virtual
class TestEoEUdpBridgeVirtual:
    """EoE bridge against the fake slave, backed by a virtual drive."""

    def test_open_assigns_requested_ip(self, eoe_bridge: EoEUdpBridge) -> None:
        """The bridge assigns its default drive IP when the slave accepts it."""
        assert eoe_bridge.drive_ip == "192.168.100.2"
        assert eoe_bridge.host_ip == "192.168.100.1"
        assert eoe_bridge.drive_ip_settings[1] == "192.168.100.2"

    def test_register_read_through_localhost_relay(
        self, eoe_bridge: EoEUdpBridge, virtual_drive_server: VirtualDrive
    ) -> None:
        """A stock EthernetNetwork reads a register through the bridge relay.

        The value read over the EoE path must match a direct UDP read from
        the same virtual drive.
        """
        direct_net = EthernetNetwork()
        direct_servo = direct_net.connect_to_slave(
            "127.0.0.1", virtual_drive_server.dictionary_path, port=virtual_drive_server.port
        )
        try:
            direct_product_code = direct_servo.read("DRV_ID_PRODUCT_CODE")
        finally:
            direct_net.disconnect_from_slave(direct_servo)
        product_code = _read_product_code_through_relay(
            eoe_bridge, virtual_drive_server.dictionary_path
        )
        assert product_code == direct_product_code

    def test_frames_are_padded_to_ethernet_minimum(
        self, eoe_bridge: EoEUdpBridge, fake_slave: FakeEoESlave, virtual_drive_server: VirtualDrive
    ) -> None:
        """Every frame sent over EoE is padded to the 60-byte Ethernet minimum."""
        _read_product_code_through_relay(eoe_bridge, virtual_drive_server.dictionary_path)
        assert fake_slave.sent_frames
        assert all(len(frame) >= EoEUdpBridge.MIN_FRAME_SIZE for frame in fake_slave.sent_frames)

    def test_refused_ip_assignment_falls_back_to_reported_settings(
        self, virtual_drive_server: VirtualDrive
    ) -> None:
        """The bridge adopts the drive's reported IP when the assignment is refused."""
        drive = FakeEoEDrive(DRIVE_MAC, DEFAULT_DRIVE_IP, virtual_drive_server.port)
        slave = FakeEoESlave(drive, accept_set_ip=False)
        bridge = EoEUdpBridge(slave)
        bridge.open()
        try:
            assert bridge.drive_ip == DEFAULT_DRIVE_IP
            assert bridge.host_ip == "192.168.2.250"
            # The relay must still work against the fallback addresses
            _read_product_code_through_relay(bridge, virtual_drive_server.dictionary_path)
        finally:
            bridge.close()
            drive.close()

    def test_open_survives_unsolicited_frames_queued_in_mailbox(
        self, virtual_drive_server: VirtualDrive
    ) -> None:
        """The bridge drains link-up chatter before the IP handshake.

        Chatty drives queue unsolicited EoE frames (e.g. IPv6 neighbor
        discovery) that desynchronize the SET/GET IP exchange unless they are
        consumed first.
        """
        drive = FakeEoEDrive(DRIVE_MAC, DEFAULT_DRIVE_IP, virtual_drive_server.port)
        slave = FakeEoESlave(drive)
        chatter = b"\x33\x33\x00\x00\x00\x02" + b"\x00" * 60
        for _ in range(3):
            slave.queue_unsolicited_frame(chatter)
        bridge = EoEUdpBridge(slave)
        bridge.open()
        try:
            assert bridge.drive_ip == "192.168.100.2"
            _read_product_code_through_relay(bridge, virtual_drive_server.dictionary_path)
        finally:
            bridge.close()
            drive.close()

    def test_unspecified_reported_ip_keeps_configured_ip(
        self, virtual_drive_server: VirtualDrive
    ) -> None:
        """A 0.0.0.0 reported IP is not adopted when the assignment succeeded."""
        drive = FakeEoEDrive(DRIVE_MAC, DEFAULT_DRIVE_IP, virtual_drive_server.port)
        slave = FakeEoESlave(drive, report_unspecified_ip=True)
        bridge = EoEUdpBridge(slave)
        bridge.open()
        try:
            assert bridge.drive_ip == "192.168.100.2"
            assert bridge.host_ip == "192.168.100.1"
            _read_product_code_through_relay(bridge, virtual_drive_server.dictionary_path)
        finally:
            bridge.close()
            drive.close()

    def test_refused_assignment_with_unspecified_reported_ip_raises(
        self, virtual_drive_server: VirtualDrive
    ) -> None:
        """The bridge raises instead of adopting 0.0.0.0 when the assignment fails."""
        drive = FakeEoEDrive(DRIVE_MAC, DEFAULT_DRIVE_IP, virtual_drive_server.port)
        slave = FakeEoESlave(drive, accept_set_ip=False, report_unspecified_ip=True)
        bridge = EoEUdpBridge(slave)
        try:
            with pytest.raises(ILError, match="reports no usable IP"):
                bridge.open()
        finally:
            drive.close()

    def test_missing_eoe_support_raises(self, virtual_drive_server: VirtualDrive) -> None:
        """Opening the bridge on a slave without EoE mailbox support raises."""
        drive = FakeEoEDrive(DRIVE_MAC, DEFAULT_DRIVE_IP, virtual_drive_server.port)
        slave = FakeEoESlave(drive, supports_eoe=False)
        bridge = EoEUdpBridge(slave)
        try:
            with pytest.raises(ILError, match="does not advertise EoE mailbox support"):
                bridge.open()
        finally:
            drive.close()
