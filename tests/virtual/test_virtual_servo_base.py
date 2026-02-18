import pickle
import socket
from threading import Lock
from unittest.mock import Mock

import pytest

from ingenialink.exceptions import ILIOError, ILTimeoutError
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


def test_virtual_servo_base_exchange_serialized_frame_returns_deserialized_data() -> None:
    socket_mock = Mock()
    socket_mock.recv.return_value = pickle.dumps(b"data")
    virtual_base = VirtualServoBase(socket_mock, Lock())

    result = virtual_base.exchange_serialized_frame({"command": "read"}, lambda response: response)

    assert result == b"data"


def test_virtual_ethercat_servo_deserialize_read_response_bytes() -> None:
    assert VirtualEthercatServo._deserialize_read_response(b"value") == b"value"


def test_virtual_ethercat_servo_deserialize_read_response_from_dict() -> None:
    assert VirtualEthercatServo._deserialize_read_response({"data": b"value"}) == b"value"


def test_virtual_ethercat_servo_deserialize_read_response_raises_on_error() -> None:
    with pytest.raises(ILIOError):
        VirtualEthercatServo._deserialize_read_response({"error": "read failed"})
