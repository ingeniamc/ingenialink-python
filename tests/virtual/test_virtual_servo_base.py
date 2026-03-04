import socket
from threading import Lock
from unittest.mock import Mock

import pytest

from ingenialink.exceptions import ILIOError, ILTimeoutError
from ingenialink.virtual.ethercat.codec import serialize_sdo_frame
from ingenialink.virtual.ethercat.servo import VirtualEthercatServo
from ingenialink.virtual.servo import VirtualServoBase


def test_virtual_servo_base_send_frame_raises_il_io_error_on_socket_error() -> None:
    socket_mock = Mock()
    socket_mock.sendall.side_effect = OSError("send failed")
    virtual_base = VirtualServoBase(socket_mock, Lock())

    with pytest.raises(ILIOError):
        virtual_base.send_frame(b"frame")


def test_virtual_servo_base_receive_frame_raises_il_timeout_error_on_timeout() -> None:
    socket_mock = Mock()
    socket_mock.recv.side_effect = socket.timeout("timeout")
    virtual_base = VirtualServoBase(socket_mock, Lock())

    with pytest.raises(ILTimeoutError):
        virtual_base.receive_frame()


def test_virtual_ethercat_servo_exchange_sdo_frame_returns_deserialized_data() -> None:
    socket_mock = Mock()
    socket_mock.recv.return_value = serialize_sdo_frame({"data": b"data"})
    servo = VirtualEthercatServo.__new__(VirtualEthercatServo)
    servo._virtual_base = VirtualServoBase(socket_mock, Lock())

    result = servo._virtual_base.exchange_sdo_frame({"command": "read"})

    assert result == {"data": b"data"}


def test_virtual_ethercat_servo_deserialize_read_response_bytes() -> None:
    assert VirtualServoBase.deserialize_read_response(b"value") == b"value"


def test_virtual_ethercat_servo_deserialize_read_response_from_dict() -> None:
    assert VirtualServoBase.deserialize_read_response({"data": b"value"}) == b"value"


def test_virtual_ethercat_servo_deserialize_read_response_raises_on_error() -> None:
    error_code = 0x12345678
    with pytest.raises(ILIOError) as exc_info:
        VirtualServoBase.deserialize_read_response({"error_code": error_code})
    assert str(exc_info.value) == f"Error code {error_code} received in read response"
