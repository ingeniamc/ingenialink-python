import argparse
import sys
import threading
import time
from enum import Enum
from typing import List, Iterator

import pysoem

from ingenialink import REG_DTYPE, REG_ACCESS
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes
from ingenialink.exceptions import ILError
from ingenialink.ethercat.register import EthercatRegister


class SlaveState(Enum):
    INIT_STATE = 1
    NONE_STATE = 0
    OP_STATE = 8
    PREOP_STATE = 2
    SAFEOP_STATE = 4
    STATE_ACK = 16
    STATE_ERROR = 16


class ProcessDataExample:
    dtype_size = {
        REG_DTYPE.U8: 1,
        REG_DTYPE.S8: 1,
        REG_DTYPE.U16: 2,
        REG_DTYPE.S16: 2,
        REG_DTYPE.U32: 4,
        REG_DTYPE.S32: 4,
        REG_DTYPE.U64: 8,
        REG_DTYPE.S64: 8,
        REG_DTYPE.FLOAT: 4,
    }

    RPDO_ASSIGN_REGISTER_SUB_IDX_0 = EthercatRegister(
        identifier="RPDO_ASSIGN_REGISTER",
        units="",
        subnode=0,
        idx=0x1C12,
        subidx=0x00,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    RPDO_ASSIGN_REGISTER_SUB_IDX_1 = EthercatRegister(
        identifier="RPDO_ASSIGN_REGISTER",
        units="",
        subnode=0,
        idx=0x1C12,
        subidx=0x01,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    RPDO_MAP_REGISTER_SUB_IDX_0 = EthercatRegister(
        identifier="RPDO_MAP_REGISTER",
        units="",
        subnode=0,
        idx=0x1600,
        subidx=0x00,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    RPDO_MAP_REGISTER_SUB_IDX_1 = EthercatRegister(
        identifier="RPDO_MAP_REGISTER",
        units="",
        subnode=0,
        idx=0x1600,
        subidx=0x01,
        dtype=REG_DTYPE.STR,
        access=REG_ACCESS.RW,
    )
    TPDO_ASSIGN_REGISTER_SUB_IDX_0 = EthercatRegister(
        identifier="TPDO_ASSIGN_REGISTER",
        units="",
        subnode=0,
        idx=0x1C13,
        subidx=0x00,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    TPDO_ASSIGN_REGISTER_SUB_IDX_1 = EthercatRegister(
        identifier="TPDO_ASSIGN_REGISTER",
        units="",
        subnode=0,
        idx=0x1C13,
        subidx=0x01,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    TPDO_MAP_REGISTER_SUB_IDX_0 = EthercatRegister(
        identifier="TPDO_MAP_REGISTER",
        units="",
        subnode=0,
        idx=0x1A00,
        subidx=0x00,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    TPDO_MAP_REGISTER_SUB_IDX_1 = EthercatRegister(
        identifier="TPDO_MAP_REGISTER",
        units="",
        subnode=0,
        idx=0x1A00,
        subidx=0x01,
        dtype=REG_DTYPE.STR,
        access=REG_ACCESS.RW,
    )

    rpdo_registers = ["CL_POS_SET_POINT_VALUE"]

    tpdo_registers = [
        "CL_POS_FBK_VALUE",
        "CL_VEL_FBK_VALUE",
    ]

    def __init__(self, interface_name: str, dictionary_path: str):
        """Basic example on EtherCAT PDOs.

        Args:
            interface_name: Network adapter interface name.
            dictionary_path: Drive's dictionary path.

        """
        self.net = EthercatNetwork(interface_name)
        self.master = self.net._ecat_master
        slave = self.net.scan_slaves()[0]
        self.servo = self.net.connect_to_slave(slave, dictionary_path)
        self.slave = self.master.slaves[slave]
        self.tpdo_registers_sizes: List[int] = []
        self._pd_thread_stop_event = threading.Event()
        self.feedback_resolution = self.servo.read("FBK_DIGENC1_RESOLUTION")

    def reset_rpdo_mapping(self) -> None:
        """Reset the RPDO mappings"""
        self.servo.write(self.RPDO_ASSIGN_REGISTER_SUB_IDX_0, 0)
        self.servo.write(self.RPDO_MAP_REGISTER_SUB_IDX_0, 0)

    def reset_tpdo_mapping(self) -> None:
        """Reset the TPDO mappings"""
        self.servo.write(self.TPDO_ASSIGN_REGISTER_SUB_IDX_0, 0)
        self.servo.write(self.TPDO_MAP_REGISTER_SUB_IDX_0, 0)

    def map_rpdo(self) -> None:
        """Map the RPDO registers"""
        rpdo_map = bytes()
        for register in self.rpdo_registers:
            rpdo_register = self.servo.dictionary.registers(1)[register]
            rpdo_map += self.map_register(rpdo_register)
        self.servo.write(self.RPDO_MAP_REGISTER_SUB_IDX_0, len(self.rpdo_registers))
        self.servo.write(
            self.RPDO_MAP_REGISTER_SUB_IDX_1, rpdo_map.decode("utf-8"), complete_access=True
        )
        self.servo.write(self.RPDO_ASSIGN_REGISTER_SUB_IDX_0, 1)
        self.servo.write(
            self.RPDO_ASSIGN_REGISTER_SUB_IDX_1,
            self.RPDO_MAP_REGISTER_SUB_IDX_0.idx,
            complete_access=True,
        )

    def map_tpdo(self) -> None:
        """Map the TPDO registers."""
        tpdo_map = bytes()
        for register in self.tpdo_registers:
            tpdo_register = self.servo.dictionary.registers(1)[register]
            tpdo_map += self.map_register(tpdo_register)
            self.tpdo_registers_sizes.append(self.dtype_size[tpdo_register.dtype])
        self.servo.write(self.TPDO_MAP_REGISTER_SUB_IDX_0, len(self.tpdo_registers))
        self.servo.write(
            self.TPDO_MAP_REGISTER_SUB_IDX_1, tpdo_map.decode("utf-8"), complete_access=True
        )
        self.servo.write(self.TPDO_ASSIGN_REGISTER_SUB_IDX_0, 1)
        self.servo.write(
            self.TPDO_ASSIGN_REGISTER_SUB_IDX_1,
            self.TPDO_MAP_REGISTER_SUB_IDX_0.idx,
            complete_access=True,
        )

    def pdo_setup(self, slave_id: int) -> None:
        """Map RPDOs and TPDOs.

        Args:
            slave_id: Slave ID.

        """
        self.reset_rpdo_mapping()
        self.reset_tpdo_mapping()
        self.map_rpdo()
        self.map_tpdo()

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

    def map_register(self, register: EthercatRegister) -> bytes:
        """Arrange register information into PDO mapping format.

        Args:
            register: Register to map.

        Returns:
            PDO register mapping format.

        """
        index = register.idx
        size_bytes = self.dtype_size[register.dtype]
        mapped_register = (index << 16) | (size_bytes * 8)
        mapped_register_bytes: bytes = mapped_register.to_bytes(4, "little")
        return mapped_register_bytes

    def process_inputs(self) -> None:
        """Print TPDOs values to console."""
        input_data = self.slave.input
        console_output = ""
        for idx, register in enumerate(self.tpdo_registers):
            tpdo_register = self.servo.dictionary.registers(1)[register]
            data_size = self.tpdo_registers_sizes[idx]
            data = input_data[:data_size]
            input_data = input_data[data_size:]
            value = convert_bytes_to_dtype(data, tpdo_register.dtype)
            console_output += f"{register} value: {value} "
        sys.stdout.write("\r" + console_output)
        sys.stdout.flush()

    def generate_output(self) -> Iterator[bytes]:
        """Generate the position set-point value to be writen.

        Returns:
              New position set-point.
        """
        position_set_point = 0
        rpdo_register = self.rpdo_registers[0]
        register_dtype = self.servo.dictionary.registers(1)[rpdo_register].dtype
        while True:
            yield convert_dtype_to_bytes(position_set_point, register_dtype)
            position_set_point += 100
            if position_set_point > self.feedback_resolution:
                position_set_point = 0

    def process_data_loop(self) -> None:
        """Process inputs and generate outputs."""
        generator = self.generate_output()
        while True:
            self.process_inputs()
            self.slave.output = next(generator)
            time.sleep(0.1)

    def _processdata_thread(self) -> None:
        """Background thread that sends and receives the process-data frame in a 10ms interval."""
        while not self._pd_thread_stop_event.is_set():
            self.master.send_processdata()
            self._actual_wkc = self.master.receive_processdata(timeout=100_000)
            if self._actual_wkc != self.master.expected_wkc:
                print("incorrect wkc")
            time.sleep(0.01)

    def run(self) -> None:
        """Main loop of the program."""
        self.slave.config_func = self.pdo_setup
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
        self.master.state = pysoem.INIT_STATE
        self.master.write_state()
        self.master.close()
        self.servo.disable()
        self.net.disconnect_from_slave(self.servo)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EtherCAT PDOs example script.")
    parser.add_argument("-ifname", type=str, help="Network adapter interface name.")
    parser.add_argument("-dict", type=str, help="Drive's dictionary.")
    args = parser.parse_args()
    ProcessDataExample(args.ifname, args.dict).run()
