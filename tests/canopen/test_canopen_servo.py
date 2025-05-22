import pytest
from canopen.network import RemoteNode


@pytest.mark.canopen
def test_canopen_getters(servo, net):
    assert servo is not None and net is not None

    assert isinstance(servo.node, RemoteNode)
