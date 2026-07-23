"""Tests for the userspace EoE-to-UDP bridge spawned from a CoE servo.

These tests run on an EtherCAT setup and require:

* the pysoem fork with EoE support (pysoem 1.1.13 + https://github.com/bnjmnp/pysoem/pull/163):
  ``pip install "git+https://github.com/polfeliu/pysoem.git@eoe-1.1.13"``
* the smoltcp-based stack extension: ``pip install ./ingenialink/ethercat/eoe/stack``
* a drive whose dictionary contains an ``EoEDevice`` section (XDF v3).
"""

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("eoe_stack", reason="the eoe_stack extension is not installed")
pysoem = pytest.importorskip("pysoem")

try:
    pysoem.CdefSlave.eoe_set_ip
except AttributeError:
    pytest.skip("pysoem is built without EoE support", allow_module_level=True)

from collections.abc import Generator  # noqa: E402

from ingenialink.ethercat.eoe import EoEUdpBridge  # noqa: E402
from ingenialink.ethernet.network import EthernetNetwork  # noqa: E402

if TYPE_CHECKING:
    from summit_testing_framework.setups.descriptors import DriveEcatSetup

    from ingenialink.ethercat.servo import EthercatServo


@pytest.fixture
def eoe_bridge(servo: "EthercatServo") -> Generator[EoEUdpBridge, None, None]:
    """Spawn the EoE interface from the connected CoE servo and close it on teardown.

    Yields:
        The opened bridge.
    """
    bridge = servo.bind_eoe()
    yield bridge
    bridge.close()


@pytest.mark.ethercat
class TestEoEUdpBridge:
    """Userspace EoE bridge against a real drive, alongside the CoE connection."""

    def test_drive_reports_ip_settings(self, eoe_bridge: EoEUdpBridge) -> None:
        """The drive reports EoE IP settings and the bridge adopts a matching subnet."""
        _, ip, _, _, _, _ = eoe_bridge.drive_ip_settings
        assert ip == eoe_bridge.drive_ip
        host_subnet = eoe_bridge.host_ip.rsplit(".", 1)[0]
        assert eoe_bridge.drive_ip.rsplit(".", 1)[0] == host_subnet

    def test_register_read_through_localhost_relay(
        self, eoe_bridge: EoEUdpBridge, setup_descriptor: "DriveEcatSetup"
    ) -> None:
        """A stock EthernetNetwork reads registers through the bridge's localhost relay."""
        eth_net = EthernetNetwork()
        eoe_servo = eth_net.connect_to_slave(
            "127.0.0.1",
            setup_descriptor.dictionary,
            port=eoe_bridge.relay_port,
            is_eoe=True,
        )
        try:
            product_code = eoe_servo.read("DRV_ID_PRODUCT_CODE")
            assert product_code == eoe_servo.dictionary.product_code
        finally:
            eth_net.disconnect_from_slave(eoe_servo)

    def test_coe_connection_remains_usable_while_eoe_is_bound(
        self, eoe_bridge: EoEUdpBridge, servo: "EthercatServo"
    ) -> None:
        """SDO reads on the CoE side keep working while the EoE bridge is polling."""
        assert eoe_bridge.relay_port != 0
        product_code = servo.read("DRV_ID_PRODUCT_CODE")
        assert product_code == servo.dictionary.product_code
