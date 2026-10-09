"""SDCP node identification utilities."""

from ingenialink.enums.node import NodeMode
from ingenialink.ethernet.tsn.sdcp.connection import DEFAULT_SDCP_TIMEOUT_S, SDCPConnection
from ingenialink.ethernet.tsn.sdcp.discovery import SDCPNodeDiscovery
from ingenialink.ethernet.tsn.sdcp.messages import (
    SDCPDeviceMode,
    SDCPIdentificationRequest,
    SDCPIdentificationResponse,
    SDCPIdentificationResponseError,
)
from ingenialink.exceptions import ILIOError

_IDENTIFICATION_TRANSACTION_ID = 0x0000


def identify_sdcp_node(
    target: str,
    interface: str,
    timeout: float = DEFAULT_SDCP_TIMEOUT_S,
) -> SDCPNodeDiscovery:
    """Identify an SDCP-compatible device and obtain its operating mode.

    Args:
        target: IPv6 address of the device.
        interface: Network interface used to reach the device.
        timeout: Timeout in seconds for each SDCP transaction.

    Returns:
        Discovery information obtained from the SDCP node.

    Raises:
        ILIOError: If identification fails or an unexpected response is received.
        ILTimeoutError: If an SDCP transaction times out.
    """
    with SDCPConnection(target, interface, timeout) as connection:
        identification = _read_identification(connection)
        mode = (
            NodeMode.APPLICATION
            if identification.device_mode == SDCPDeviceMode.APPLICATION
            else NodeMode.BOOTLOADER
        )

    return SDCPNodeDiscovery(
        target=target,
        interface=interface,
        protocol_version=identification.protocol_version,
        serial_number=identification.serial_number,
        product_code=identification.product_code,
        revision_number=identification.revision_number,
        mode=mode,
    )


def _read_identification(
    connection: SDCPConnection,
) -> SDCPIdentificationResponse:
    """Read the identification information of an SDCP-compatible device.

    Args:
        connection: Open SDCP connection to the device.

    Returns:
        Identification response returned by the device.

    Raises:
        ILIOError: If identification fails or an unexpected response is
            received.
    """
    response = connection.request(
        SDCPIdentificationRequest(
            transaction_id=_IDENTIFICATION_TRANSACTION_ID,
        )
    )

    if isinstance(response, SDCPIdentificationResponseError):
        raise ILIOError(f"SDCP identification failed with error code 0x{response.error_code:08X}")

    if not isinstance(response, SDCPIdentificationResponse):
        raise ILIOError(f"Unexpected SDCP identification response: {response}")

    return response
