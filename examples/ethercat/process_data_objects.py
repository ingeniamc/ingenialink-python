import time

import pysoem

from ingenialink import REG_DTYPE
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.utils._utils import convert_bytes_to_dtype
from ingenialink.exceptions import ILError
from ingenialink.canopen.register import CanopenRegister


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

    rpdo_registers = [
        "CIA402_DRV_STATE_CONTROL"
    ]

    tpdo_registers = [
        "CIA402_CL_POS_FBK_VALUE",
        "CIA402_CL_VEL_FBK_VALUE",

    ]

    def __init__(self, interface_name: str, dictionary_path: str):
        self.rpdo_assign_register = 0x1C12
        self.rpdo_map_register = 0x1600
        self.tpdo_assign_register = 0x1C13
        self.tpdo_map_register = 0x1A00
        self.net = EthercatNetwork(interface_name)
        self.master = self.net._ecat_master
        slave = self.net.scan_slaves()[0]
        self.servo = self.net.connect_to_slave(slave, dictionary_path)
        self.slave = self.master.slaves[slave]
        self.tpdo_registers_sizes = []

    def reset_rpdo_mapping(self) -> None:
        self.slave.sdo_write(self.rpdo_assign_register, 0x00, bytes(0))
        self.slave.sdo_write(self.rpdo_map_register, 0x00, bytes(0))

    def reset_tpdo_mapping(self) -> None:
        zero = int.to_bytes(0, 4, "little")
        self.slave.sdo_write(self.tpdo_assign_register, 0x00, bytes(0))
        self.slave.sdo_write(self.tpdo_map_register, 0x00, bytes(0))

    def map_rpdo(self) -> None:
        rpdo_map = bytes()
        for register in self.rpdo_registers:
            rpdo_register = self.servo.dictionary.registers(1)[register]
            rpdo_map += self.map_register(rpdo_register)
        rpdo_cnt = int.to_bytes(len(self.rpdo_registers), 4, "little")
        self.slave.sdo_write(self.rpdo_map_register, 0x01, rpdo_map, True)
        self.slave.sdo_write(self.rpdo_map_register, 0x00, rpdo_cnt)
        self.slave.sdo_write(self.rpdo_assign_register, 0x01, self.rpdo_map_register.to_bytes(4, "little"))
        self.slave.sdo_write(self.rpdo_assign_register, 0x00, int.to_bytes(1, 4, "little"))

    def map_tpdo(self) -> None:
        tpdo_map = bytes()
        for register in self.tpdo_registers:
            tpdo_register = self.servo.dictionary.registers(1)[register]
            tpdo_map += self.map_register(tpdo_register)
            self.tpdo_registers_sizes.append(self.dtype_size[tpdo_register.dtype])
        tpdo_cnt = int.to_bytes(len(self.tpdo_registers), 4, "little")
        self.slave.sdo_write(self.tpdo_map_register, 0x01, tpdo_map, True)
        self.slave.sdo_write(self.tpdo_map_register, 0x00, tpdo_cnt)
        self.slave.sdo_write(self.tpdo_assign_register, 0x01, self.tpdo_map_register.to_bytes(4, "little"))
        self.slave.sdo_write(self.tpdo_assign_register, 0x00, int.to_bytes(1, 4, "little"))

    def pdo_setup(self, slave_pos: int) -> None:
        self.reset_rpdo_mapping()
        self.reset_tpdo_mapping()
        self.map_rpdo()
        self.map_tpdo()

    def check_state(self, state: int) -> None:
        if self.master.state_check(state, 50000) != pysoem.SAFEOP_STATE:
            self.master.read_state()
            if self.slave.state != state:
                print(f'{self.slave.name} did not reach {state}')
                print(f'al status code {hex(self.slave.al_status)} ({pysoem.al_status_code_to_string(self.slave.al_status)})')
                raise ILError(f'Not all slaves reached state {state}')

    def map_register(self, register: CanopenRegister):
        index = register.idx
        size_bytes = self.dtype_size[register.dtype]
        mapped_register = (index << 16) | (size_bytes * 8)
        return mapped_register.to_bytes(4, "little")

    def process_inputs(self):
        input_data = self.slave.input
        for idx, register in enumerate(self.tpdo_registers):
            tpdo_register = self.servo.dictionary.registers(1)[register]
            data_size = self.tpdo_registers_sizes[idx]
            data = input_data[:data_size]
            input_data = input_data[data_size:]
            value = convert_bytes_to_dtype(data, tpdo_register.dtype)
            print(f"{register} value: {value}")

    def process_data_loop(self):
        while True:
            self.master.send_processdata()
            self.master.receive_processdata(2000)
            self.process_inputs()
            time.sleep(0.1)

    def run(self) -> None:
        self.slave.config_func = self.pdo_setup
        self.master.config_map()
        self.check_state(pysoem.SAFEOP_STATE)
        self.master.state = pysoem.OP_STATE
        self.master.write_state()
        self.check_state(pysoem.OP_STATE)
        print('Process data started')
        try:
            self.process_data_loop()
        except KeyboardInterrupt:
            print('Process data stopped')
        self.master.state = pysoem.INIT_STATE
        self.master.write_state()
        self.master.close()


if __name__ == '__main__':
    interface_name = r'\Device\NPF_{43144EC3-59EF-408B-8D9B-4867F1324D62}'
    dictionary = "C://Users//martin.acosta//Documents//issues//INGK-672//cap-net-c_can_2.4.1.xdf"
    ProcessDataExample(interface_name, dictionary).run()