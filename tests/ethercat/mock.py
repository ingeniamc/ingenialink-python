import pytest


class NetworkEnvironment:
    """Environment controller for managing the simulated EtherCAT network in tests.

    This class allows tests to dynamically control how many slaves are available
    in the mocked network. Slaves are always sequentially numbered starting from 1.
    """

    def __init__(self, num_slaves: int = 3):
        """Initialize the network environment.

        Args:
            num_slaves: Number of slaves in the network (sequentially numbered 1, 2, 3, ...).
        """
        self.num_slaves = num_slaves

    def set_num_slaves(self, num_slaves: int):
        """Set the number of slaves available in the network.

        Args:
            num_slaves: Number of slaves (will be numbered 1, 2, 3, ... num_slaves).
        """
        self.num_slaves = num_slaves

    @property
    def available_slave_ids(self):
        """Get the list of available slave IDs (always sequential from 1)."""
        return list(range(1, self.num_slaves + 1))


class MockSoemSlave:
    def __init__(self, id: int):  # noqa: A002 shadows built-in
        self.id = id
        self._emcy_callbacks = []
        self.state: int = 1  # INIT_STATE

    def write_state(self):
        pass

    def read_state(self):
        return self.state

    def add_emergency_callback(self, callback):
        self._emcy_callbacks.append(callback)

    def state_check(self, expected_state: int, timeout: int = 50000):  # noqa: ARG002
        return self.state

    def sdo_write(
        self, index: int, subindex: int, data: bytes, ca: bool = False, *, release_gil=None
    ):
        pass


class MockSoemMaster:
    def __init__(self, environment_controller=None):
        self.slaves = []
        self.__environment = environment_controller or NetworkEnvironment()
        self.state = 1  # INIT_STATE

    def open(self, ifname, ifname_red=None):
        pass

    def close(self):
        pass

    def config_init(self, **_):
        self.slaves = [
            MockSoemSlave(id=slave_id) for slave_id in self.__environment.available_slave_ids
        ]
        return len(self.slaves)

    def read_state(self):
        pass

    def state_check(self, expected_state: int, timeout: int = 50000):
        pass


@pytest.fixture()
def pysoem_mock_network(mocker):
    environment_controller = NetworkEnvironment()

    def mock_master_factory():
        return MockSoemMaster(environment_controller)

    mocker.patch("pysoem.Master", mock_master_factory)

    # Return the environment controller so tests can manipulate the network
    return environment_controller
