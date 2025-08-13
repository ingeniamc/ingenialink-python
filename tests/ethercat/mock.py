import pytest
from pysoem import INIT_STATE


class MockSoemSlave:
    def __init__(self, id: int):
        self.id = id
        self._emcy_callbacks = []
        self.state: int = INIT_STATE

    def write_state(self):
        pass

    def read_state(self):
        return self.state

    def add_emergency_callback(self, callback):
        self._emcy_callbacks.append(callback)

    def state_check(self, expected_state: int, timeout=2000):
        return self.state

    def sdo_write(
        self, index: int, subindex: int, data: bytes, ca: bool = False, *, release_gil=None
    ):
        pass


class MockSoemMaster:
    def __init__(self):
        self.slaves = []

    def open(self, ifname, ifname_red=None):
        pass

    def close(self):
        pass

    def config_init(self, usetable=False, *, release_gil=None):
        self.slaves = [MockSoemSlave(id=1), MockSoemSlave(id=2), MockSoemSlave(id=3)]

        return len(self.slaves)

    def read_state(self):
        pass

    def state_check(self, expected_state: int, timeout: int = 50000):
        pass


@pytest.fixture()
def pysoem_mock_network(mocker):
    mocker.patch("pysoem.Master", MockSoemMaster)
