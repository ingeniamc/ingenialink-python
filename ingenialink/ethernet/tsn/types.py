"""Shared types for TSN communication."""

from typing import NamedTuple


class IPv6SocketAddress(NamedTuple):
    """IPv6 socket address matching Python's ``AF_INET6`` address tuple."""

    address: str
    port: int
    flowinfo: int
    scopeid: int
