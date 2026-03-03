"""Backward-compatible re-export of the shared SDO codec."""

from ingenialink.virtual.codec import deserialize_sdo_frame, serialize_sdo_frame

__all__ = ["deserialize_sdo_frame", "serialize_sdo_frame"]
