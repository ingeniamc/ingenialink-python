import argparse
import sys
import threading
import time
from enum import Enum
from functools import partial
from typing import Tuple

import pysoem

from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.exceptions import ILError
from ingenialink.pdo import PDOMap


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
    "DRV_OP_CMD": 68,
}


class ProcessDataExample:
    def __init__(self, interface_name: str, dictionary_path: str, auto_stop: bool = False):
        """Basic example on EtherCAT PDOs.

        Args:
            interface_name: Network adapter interface name.
            dictionary_path: Drive's dictionary path.
            auto_stop: Automatically stop the PDO process after 5 seconds.

        """
        self.net = EthercatNetwork(interface_name)
        slave = self.net.scan_slaves()[0]
        self.servo = self.net.connect_to_slave(slave, dictionary_path)
        self._pd_thread_stop_event = threading.Event()
        self.create_pdo_maps()
        if auto_stop:
            threading.Timer(5, self._stop_process_data).start()

    def create_pdo_maps(self) -> Tuple[PDOMap]:
        """Create a PDO Map with the RPDO and TPDO registers."""
        self.rpdo_map = self.servo.create_rpdo_map()
        self.tpdo_map = self.servo.create_tpdo_map()
        for tpdo_register in TPDO_REGISTERS:
            register = self.servo.dictionary.registers(1)[tpdo_register]
            self.tpdo_map.add_registers(register)
        for rpdo_register in RPDO_REGISTERS:
            register = self.servo.dictionary.registers(1)[rpdo_register]
            self.rpdo_map.add_registers(register)

    def process_data_loop(self) -> None:
        """Process inputs and generate outputs."""
        while not self._pd_thread_stop_event.is_set():
            self.servo.process_pdo_inputs()
            for item in self.tpdo_map.items:
                TPDO_REGISTERS[item.register.identifier] = item.value
            RPDO_REGISTERS["CL_POS_SET_POINT_VALUE"] += 100
            for item in self.rpdo_map.items:
                item.value = RPDO_REGISTERS[item.register.identifier]
            self.servo.generate_pdo_outputs()
            self._print_values_to_console()
            time.sleep(0.1)

    def _processdata_thread(self) -> None:
        """Background thread that sends and receives the process-data frame in a 10ms interval."""
        while not self._pd_thread_stop_event.is_set():
            self.net._ecat_master.send_processdata()
            self._actual_wkc = self.net._ecat_master.receive_processdata(timeout=100_000)
            if self._actual_wkc != self.net._ecat_master.expected_wkc:
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
        self.servo.set_mapping_in_slave([self.rpdo_map], [self.tpdo_map])
        self.net.start_pdos()
        proc_thread = threading.Thread(target=self._processdata_thread)
        proc_thread.start()
        print("Process data started")
        self.servo.enable()
        try:
            self.process_data_loop()
        except KeyboardInterrupt:
            print("Process data stopped")
        self._pd_thread_stop_event.set()
        proc_thread.join()
        self.servo.disable()
        self.net.stop_pdos()
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
