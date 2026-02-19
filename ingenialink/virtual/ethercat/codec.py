from __future__ import annotations

import json
from typing import Any

MAX_FRAME_BYTES = 65536


def serialize_sdo_frame(payload: dict[str, Any]) -> bytes:
    """Serialize an EtherCAT SDO payload to JSON bytes.

    The ``data`` field is encoded as a list of byte values to keep the JSON
    schema simple and language-agnostic.

    Args:
        payload: The EtherCAT SDO payload dictionary to serialize.

    Returns:
        The serialized payload as JSON bytes.

    """
    normalized_payload = dict(payload)
    raw_data = normalized_payload.get("data")
    if isinstance(raw_data, (bytes, bytearray)):
        normalized_payload["data"] = list(raw_data)

    return json.dumps(normalized_payload, separators=(",", ":")).encode("utf-8")


def deserialize_sdo_frame(frame: bytes) -> dict[str, Any]:
    """Deserialize JSON bytes into an EtherCAT SDO payload dictionary.

    Args:
        frame: The JSON bytes representing the EtherCAT SDO payload.

    Returns:
        The deserialized EtherCAT SDO payload as a dictionary.

    Raises:
        ValueError: If the frame exceeds the maximum allowed size, if the JSON
            is invalid, if the payload is not a dictionary, or if the data array
            contains invalid byte values.

    """
    if len(frame) > MAX_FRAME_BYTES:
        raise ValueError("EtherCAT SDO frame exceeds maximum allowed size")

    payload = json.loads(frame.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("EtherCAT SDO frame payload must be a dictionary")

    raw_data = payload.get("data")
    if isinstance(raw_data, list):
        if not all(isinstance(item, int) and 0 <= item <= 0xFF for item in raw_data):
            raise ValueError("EtherCAT SDO data array must contain byte values (0..255)")
        payload["data"] = bytes(raw_data)

    return payload
