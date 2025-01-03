import pytest
from canopen.network import RemoteNode


@pytest.mark.canopen()
def test_canopen_getters(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None
    assert net is not None

    assert isinstance(servo.node, RemoteNode)
