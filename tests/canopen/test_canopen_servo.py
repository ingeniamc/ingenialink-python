import pytest
from canopen.network import RemoteNode


@pytest.mark.canopen
def test_canopen_getters(interface_controller):
    servo, net, _, _ = interface_controller
    assert servo is not None and net is not None

    assert isinstance(servo.node, RemoteNode)
