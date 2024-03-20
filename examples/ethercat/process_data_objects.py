import argparse
import sys
import threading
import time
from enum import Enum
from typing import Tuple

from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.pdo import RPDOMap, TPDOMap


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
        self.servos = []
        self.rpdo_maps = []
        self.tpdo_maps = []
        slaves = self.net.scan_slaves()
        for slave in slaves:
            servo = self.net.connect_to_slave(slave, dictionary_path)
            rpdo_map, tpdo_map = self.create_pdo_maps(servo)
            servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
            self.rpdo_maps.append(rpdo_map)
            self.tpdo_maps.append(tpdo_map)
            self.servos.append(servo)
        self._pd_thread_stop_event = threading.Event()
        if auto_stop:
            threading.Timer(5, self._stop_process_data).start()

    @staticmethod
    def create_pdo_maps(servo) -> Tuple[RPDOMap, TPDOMap]:
        """Create a PDO Map with the RPDO and TPDO registers.

        Returns:
            Tuple with the RPDOMap and TPDOMap created
        """
        rpdo_map = RPDOMap()
        tpdo_map = TPDOMap()
        for tpdo_register in TPDO_REGISTERS:
            register = servo.dictionary.registers(1)[tpdo_register]
            tpdo_map.add_registers(register)
        for rpdo_register in RPDO_REGISTERS:
            register = servo.dictionary.registers(1)[rpdo_register]
            rpdo_map.add_registers(register)
        for item in rpdo_map.items:
            item.value = RPDO_REGISTERS[item.register.identifier]
        return rpdo_map, tpdo_map

    def process_data_loop(self) -> None:
        """Process inputs and generate outputs."""
        while not self._pd_thread_stop_event.is_set():
            for index, _ in enumerate(self.servos):
                for item in self.tpdo_maps[index].items:
                    TPDO_REGISTERS[item.register.identifier] = item.value
                RPDO_REGISTERS["CL_POS_SET_POINT_VALUE"] += 100
                for item in self.rpdo_maps[index].items:
                    item.value = RPDO_REGISTERS[item.register.identifier]
            time.sleep(0.1)

    def _processdata_thread(self) -> None:
        """Background thread that sends and receives the process-data frame in a 10ms interval."""
        while not self._pd_thread_stop_event.is_set():
            self.net.send_receive_processdata()
            self._print_values_to_console()
            time.sleep(0.01)

    def _print_values_to_console(self) -> None:
        """Print the TPDO register values to console."""
        sys.stdout.write("\r")
        for index, _ in enumerate(self.servos):
            sys.stdout.write(f"Drive: {index} ")
            console_output = " ".join(
                f"{item.register.identifier}: {item.value}" for item in self.tpdo_maps[index].items
            )
            sys.stdout.write(console_output + " ")
        sys.stdout.flush()

    def _stop_process_data(self) -> None:
        """Stop the data processing."""
        self._pd_thread_stop_event.set()

    def run(self) -> None:
        """Main loop of the program."""
        self.net.start_pdos()
        print("Process data started")
        proc_thread = threading.Thread(target=self._processdata_thread)
        proc_thread.start()
        for servo in self.servos:
            servo.enable()
        try:
            self.process_data_loop()
        except KeyboardInterrupt:
            print("Process data stopped")
        self._pd_thread_stop_event.set()
        proc_thread.join()
        self.net.stop_pdos()
        for servo in self.servos:
            servo.disable()
            self.net.disconnect_from_slave(servo)


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
