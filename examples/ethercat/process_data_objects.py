import argparse
import sys
import threading
import time
from enum import Enum

import pysoem

from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethercat.pdo import PDOMap, PDOType
from ingenialink.exceptions import ILError


class SlaveState(Enum):
    INIT_STATE = 1
    NONE_STATE = 0
    OP_STATE = 8
    PREOP_STATE = 2
    SAFEOP_STATE = 4
    STATE_ACK = 16
    STATE_ERROR = 16


TPDO_REGISTERS = {
    "CL_POS_FBK_VALUE": 0,
    "CL_VEL_FBK_VALUE": 0,
}

RPDO_REGISTERS = {
    "CL_POS_SET_POINT_VALUE": 0,
}


def process_inputs(pdo_map_item) -> None:
    """Store the received TPDO register value."""
    tpdo_reg = pdo_map_item.register
    TPDO_REGISTERS[tpdo_reg.identifier] = pdo_map_item.value


def generate_output(pdo_map_item):
    """Generate a value to be set to a RPDO register.

    Returns:
          The value to be set.
    """
    rpdo_reg = pdo_map_item.register
    RPDO_REGISTERS[rpdo_reg.identifier] += 100
    return RPDO_REGISTERS[rpdo_reg.identifier]


class ProcessDataExample:
    def __init__(self, interface_name: str, dictionary_path: str, auto_stop: bool = False):
        """Basic example on EtherCAT PDOs.

        Args:
            interface_name: Network adapter interface name.
            dictionary_path: Drive's dictionary path.
            auto_stop: Automatically stop the PDO process after 5 seconds.

        """
        self.net = EthercatNetwork(interface_name)
        self.master = self.net._ecat_master
        slave = self.net.scan_slaves()[0]
        self.servo = self.net.connect_to_slave(slave, dictionary_path)
        self.slave = self.master.slaves[slave]
        self._pd_thread_stop_event = threading.Event()
        self.pdo_map = self.create_pdo_map()
        if auto_stop:
            threading.Timer(5, self._stop_process_data).start()

    def create_pdo_map(self) -> PDOMap:
        """Create a PDO Map with the RPDO and TPDO registers."""
        pdo_map = self.servo.create_pdo_map()
        for tpdo_register in TPDO_REGISTERS:
            pdo_map.add_register(tpdo_register, process_inputs, PDOType.TPDO)
        for rpdo_register in RPDO_REGISTERS:
            pdo_map.add_register(rpdo_register, generate_output, PDOType.RPDO)
        return pdo_map

    def check_state(self, state: SlaveState) -> None:
        """Check if the slave reached the requested state.

        Args:
            state: Requested state.

        Raises:
            ILError: If state is not reached.

        """
        if self.master.state_check(state.value, 50_000) != state.value:
            self.master.read_state()
            if self.slave.state != state.value:
                raise ILError(
                    f"{self.slave.name} did not reach {SlaveState(state).name}."
                    f" {hex(self.slave.al_status)} {pysoem.al_status_code_to_string(self.slave.al_status)}"
                )

    def process_data_loop(self) -> None:
        """Process inputs and generate outputs."""
        while not self._pd_thread_stop_event.is_set():
            self.servo.process_pdo_inputs()
            self.servo.generate_pdo_outputs()
            self._print_values_to_console()
            time.sleep(0.1)

    def _processdata_thread(self) -> None:
        """Background thread that sends and receives the process-data frame in a 10ms interval."""
        while not self._pd_thread_stop_event.is_set():
            self.master.send_processdata()
            self._actual_wkc = self.master.receive_processdata(timeout=100_000)
            if self._actual_wkc != self.master.expected_wkc:
                print("incorrect wkc")
            time.sleep(0.01)

    @staticmethod
    def _print_values_to_console():
        """Print the TPDO register values to console."""
        console_output = "".join(f"{reg}: {value} " for reg, value in TPDO_REGISTERS.items())
        sys.stdout.write("\r" + console_output)
        sys.stdout.flush()

    def _stop_process_data(self):
        """Stop the data processing."""
        self._pd_thread_stop_event.set()

    def run(self) -> None:
        """Main loop of the program."""
        self.slave.config_func = self.servo.map_pdo(self.pdo_map)
        self.master.config_map()
        self.master.config_dc()
        self.check_state(SlaveState.SAFEOP_STATE)
        self.master.state = SlaveState.OP_STATE.value
        self.master.write_state()
        proc_thread = threading.Thread(target=self._processdata_thread)
        proc_thread.start()
        self.check_state(SlaveState.OP_STATE)
        print("Process data started")
        self.servo.enable()
        try:
            self.process_data_loop()
        except KeyboardInterrupt:
            print("Process data stopped")
        self._pd_thread_stop_event.set()
        proc_thread.join()
        self.servo.disable()
        self.master.state = pysoem.INIT_STATE
        self.master.write_state()
        self.master.close()
        self.net.disconnect_from_slave(self.servo)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EtherCAT PDOs example script.")
    parser.add_argument("-ifname", type=str, help="Network adapter interface name.")
    parser.add_argument("-dict", type=str, help="Drive's dictionary.")
    parser.add_argument(
        "-auto_stop",
        help="Automatically stop the PDO process after 5 seconds.",
        action="store_true",
    )
    args = parser.parse_args()
    ProcessDataExample(args.ifname, args.dict, args.auto_stop).run()
