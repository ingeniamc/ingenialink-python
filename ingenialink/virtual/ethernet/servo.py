from ingenialink.dictionary import Interface
from ingenialink.ethernet.servo import EthernetServoBase
from ingenialink.virtual.servo import VirtualServoBase


class VirtualEthernetServo(EthernetServoBase):
    """Virtual Ethernet servo implementation."""

    interface = Interface.VIRTUAL

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self._virtual_base = VirtualServoBase()
