"""TSN node identification utilities."""

from ingenialink.enums.node import NodeMode
from ingenialink.enums.register import ByteOrder
from ingenialink.ethernet.tsn.node import TSNNodeDiscovery
from ingenialink.ethernet.tsn.sdcp.connection import DEFAULT_SDCP_TIMEOUT_S, SDCPConnection
from ingenialink.ethernet.tsn.sdcp.messages import (
    SDCPIdentificationRequest,
    SDCPIdentificationResponse,
    SDCPIdentificationResponseError,
    SDCPReadRequest,
    SDCPReadResponse,
    SDCPReadResponseError,
)
from ingenialink.exceptions import ILIOError

_IDENTIFICATION_TRANSACTION_ID = 0x0000
_COMMUNICATION_STATUS_TRANSACTION_ID = 0x0001

_COMMUNICATION_STATUS_INDEX = 0x1101
_COMMUNICATION_STATUS_SUBINDEX = 0x00
_COMMUNICATION_STATUS_SIZE = 2

_COMMUNICATION_STATUS_APPLICATION_MASK = 1 << 0
_COMMUNICATION_STATUS_BOOTLOADER_MASK = 1 << 1


def identify_tsn_node(
    target: str,
    interface: str,
    timeout: float = DEFAULT_SDCP_TIMEOUT_S,
) -> TSNNodeDiscovery:
    """Identify an SDCP-compatible device and read its operating mode.

    Args:
        target: IPv6 address of the device.
        interface: Network interface used to reach the device.
        timeout: Timeout in seconds for each SDCP transaction.

    Returns:
        Discovery information obtained from the TSN node.

    Raises:
        ILIOError: If identification or communication-status reading fails,
            or an unexpected response is received.
        ILTimeoutError: If an SDCP transaction times out.
    """
    with SDCPConnection(target, interface, timeout) as connection:
        identification = _read_identification(connection)
        mode = _read_node_mode(connection)

    return TSNNodeDiscovery(
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


def _read_node_mode(connection: SDCPConnection) -> NodeMode:
    """Read the Communication Status object and return the node mode.

    Args:
        connection: Open SDCP connection to the device.

    Returns:
        Operating mode reported by the Communication Status object.

    Raises:
        ILIOError: If the object cannot be read, has an invalid size, or
            contains an invalid combination of mode flags.
    """
    response = connection.request(
        SDCPReadRequest(
            transaction_id=_COMMUNICATION_STATUS_TRANSACTION_ID,
            index=_COMMUNICATION_STATUS_INDEX,
            subindex=_COMMUNICATION_STATUS_SUBINDEX,
        )
    )

    if isinstance(response, SDCPReadResponseError):
        raise ILIOError(
            "Could not read the Communication Status object with error code "
            f"0x{response.error_code:08X}"
        )

    if not isinstance(response, SDCPReadResponse):
        raise ILIOError(f"Unexpected Communication Status response: {response}")

    return _decode_node_mode(response.value)


def _decode_node_mode(data: bytes) -> NodeMode:
    """Decode the node mode from a Communication Status value.

    Args:
        data: Big-endian UINT16 value read from object 0x1101:00.

    Returns:
        Operating mode indicated by the Application or Bootloader flag.

    Raises:
        ILIOError: If the value is not a UINT16 or the mode flags contain an
            invalid combination.
    """
    if len(data) != _COMMUNICATION_STATUS_SIZE:
        raise ILIOError(
            "Invalid Communication Status size: "
            f"expected {_COMMUNICATION_STATUS_SIZE} bytes, "
            f"received {len(data)}"
        )

    status = int.from_bytes(
        data,
        byteorder=ByteOrder.BIG.value,
        signed=False,
    )

    application_active = bool(status & _COMMUNICATION_STATUS_APPLICATION_MASK)
    bootloader_active = bool(status & _COMMUNICATION_STATUS_BOOTLOADER_MASK)

    if application_active == bootloader_active:
        raise ILIOError(f"Invalid Communication Status mode flags: 0x{status:04X}")

    if application_active:
        return NodeMode.APPLICATION

    return NodeMode.BOOTLOADER
