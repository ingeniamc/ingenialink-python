import threading

import pytest
from canopen.network import RemoteNode

from ingenialink.canopen.servo import CanopenServo


@pytest.mark.canopen
def test_canopen_getters(servo, net):
    assert servo is not None and net is not None

    assert isinstance(servo.node, RemoteNode)


class TestMinimumSdoTimeout:
    """Tests for the CanopenServo._minimum_sdo_timeout context manager."""

    class MockSdo:
        def __init__(self, response_timeout: float) -> None:
            # mimic canopen RemoteNode.sdo.RESPONSE_TIMEOUT attribute
            self.RESPONSE_TIMEOUT = response_timeout

    class MockNode:
        def __init__(self, response_timeout: float) -> None:
            self.sdo = TestMinimumSdoTimeout.MockSdo(response_timeout)

    # Replace FakeServo with a TestServo subclassing CanopenServo. We override
    # __init__ to avoid calling the real CanopenServo.__init__ (which does
    # heavy dictionary parsing and network setup). This gives us a servo-like
    # object that the context manager can operate on directly.
    class TestServo(CanopenServo):
        def __init__(self, node: "TestMinimumSdoTimeout.MockNode") -> None:
            # Set the name-mangled __node attribute that the context manager uses.
            self._CanopenServo__node = node
            # Provide the lock used by servo methods
            self._lock = threading.Lock()

        def _change_sdo_timeout(self, value: float) -> None:
            # Restore the RESPONSE_TIMEOUT on the node.sdo
            self._CanopenServo__node.sdo.RESPONSE_TIMEOUT = value

    def test_increases_and_restores(self):
        """Test that the context manager increases the timeout if needed"""
        node = TestMinimumSdoTimeout.MockNode(0.1)
        servo = TestMinimumSdoTimeout.TestServo(node)

        assert node.sdo.RESPONSE_TIMEOUT == 0.1

        with servo._minimum_sdo_timeout(0.3):
            # while inside the context the timeout should be the requested one
            assert node.sdo.RESPONSE_TIMEOUT == 0.3

        # after exiting the context it must be restored
        assert node.sdo.RESPONSE_TIMEOUT == 0.1

    def test_does_not_change_if_current_higher(self):
        """Test that the context manager does not decrease the timeout"""
        node = TestMinimumSdoTimeout.MockNode(0.5)
        servo = TestMinimumSdoTimeout.TestServo(node)

        assert node.sdo.RESPONSE_TIMEOUT == 0.5

        # requesting a lower timeout should leave the current value unchanged
        with servo._minimum_sdo_timeout(0.3):
            assert node.sdo.RESPONSE_TIMEOUT == 0.5

        assert node.sdo.RESPONSE_TIMEOUT == 0.5

    def test_restores_on_exception(self):
        """Test that the context manager restores the timeout even on exception."""
        node = TestMinimumSdoTimeout.MockNode(0.1)
        servo = TestMinimumSdoTimeout.TestServo(node)

        with pytest.raises(RuntimeError), servo._minimum_sdo_timeout(0.4):
            # should be updated inside
            assert node.sdo.RESPONSE_TIMEOUT == 0.4
            # simulate failure inside context
            raise RuntimeError("boom")

        # Even after exception, timeout must be restored
        assert node.sdo.RESPONSE_TIMEOUT == 0.1
