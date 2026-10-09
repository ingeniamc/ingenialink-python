"""SDCP node discovery information."""

from dataclasses import dataclass

from ingenialink.enums.node import NodeMode
from ingenialink.ethernet.tsn.sdcp.enums import SDCPProfileFlags


@dataclass(frozen=True)
class SDCPNodeDiscovery:
    """Information obtained while discovering an SDCP node."""

    target: str
    interface: str
    protocol_version: int
    serial_number: int
    product_code: int
    revision_number: int
    mode: NodeMode
    profile_flags: SDCPProfileFlags
