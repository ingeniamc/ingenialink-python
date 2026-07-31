"""SDCP node discovery information."""

from dataclasses import dataclass

from ingenialink.enums.node import NodeMode


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
