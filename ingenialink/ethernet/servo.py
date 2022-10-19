import ipaddress
import threading
import time

from .._ingenialink import lib
from ingenialink.exceptions import ILError
from ingenialink.constants import PASSWORD_STORE_RESTORE_TCP_IP, \
    MCB_CMD_READ, MCB_CMD_WRITE, MONITORING_BUFFER_SIZE, ETH_MAX_WRITE_SIZE
from ingenialink.ethernet.register import EthernetRegister, REG_DTYPE, REG_ACCESS
from ingenialink.servo import Servo, SERVO_STATE
from ingenialink.utils.mcb import MCB
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes, \
    raise_err, convert_ip_to_int
from ingenialink.constants import PASSWORD_STORE_ALL, DEFAULT_PDS_TIMEOUT
from ingenialink.canopen import constants
from ingenialink.ethernet.dictionary import EthernetDictionary

import ingenialogger

logger = ingenialogger.get_logger(__name__)

COMMS_ETH_IP = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00A1, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
)
COMMS_ETH_NET_MASK = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00A2, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
)
COMMS_ETH_NET_GATEWAY = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00A3, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
)

MONITORING_DIST_ENABLE = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00C0, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
)

DISTURBANCE_ENABLE = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00C7, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
)

MONITORING_REMOVE_DATA = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00EA, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.WO
)

MONITORING_NUMBER_MAPPED_REGISTERS = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00E3, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
)

MONITORING_BYTES_PER_BLOCK = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00E4, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
)

MONITORING_ACTUAL_NUMBER_BYTES = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00B7, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)

MONITORING_DATA = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00B2, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
)

DISTURBANCE_REMOVE_DATA = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00EB, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.WO
)

DISTURBANCE_NUMBER_MAPPED_REGISTERS = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00E8, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
)

DIST_DATA = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00B4, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.WO
)

DIST_NUMBER_SAMPLES = EthernetRegister(
    identifier='', units='', subnode=0, address=0x00C4, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
)

STORE_MOCO_ALL_REGISTERS = {
    1: EthernetRegister(
        identifier='', units='', subnode=1, address=0x06DB,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    ),
    2: EthernetRegister(
        identifier='', units='', subnode=2, address=0x06DB,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    ),
    3: EthernetRegister(
        identifier='', units='', subnode=3, address=0x06DB,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )
}

STORE_COCO_ALL = EthernetRegister(
    identifier='', units='', subnode=0, address=0x06DB, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
)

CONTROL_WORD_REGISTERS = {
    1: EthernetRegister(
        identifier='', units='', subnode=1, address=0x0010,
        cyclic='CYCLIC_RX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    ),
    2: EthernetRegister(
        identifier='', units='', subnode=2, address=0x0010,
        cyclic='CYCLIC_RX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    ),
    3: EthernetRegister(
        identifier='', units='', subnode=3, address=0x0010,
        cyclic='CYCLIC_RX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    )
}

SERIAL_NUMBER_REGISTERS = {
    0: EthernetRegister(
        identifier='', units='', subnode=0, address=0x06E6,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    ),
    1: EthernetRegister(
        identifier='', units='', subnode=1, address=0x06E6,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    )
}

SOFTWARE_VERSION_REGISTERS = {
    0: EthernetRegister(
        identifier='', units='', subnode=0, address=0x06E4,
        cyclic='CONFIG', dtype=REG_DTYPE.STR, access=REG_ACCESS.RO
    ),
    1: EthernetRegister(
        identifier='', units='', subnode=1, address=0x06E4,
        cyclic='CONFIG', dtype=REG_DTYPE.STR, access=REG_ACCESS.RO
    )
}

PRODUCT_ID_REGISTERS = {
    0: EthernetRegister(
        identifier='', units='', subnode=0, address=0x06E1,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    ),
    1: EthernetRegister(
        identifier='', units='', subnode=1, address=0x06E1,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    )
}

REVISION_NUMBER_REGISTERS = {
    0: EthernetRegister(
        identifier='', units='', subnode=0, address=0x06E2,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    ),
    1: EthernetRegister(
        identifier='', units='', subnode=1, address=0x06E2,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    )
}


class EthernetServo(Servo):
    """Servo object for all the Ethernet slave functionalities.

    Args:
        socket (socket):
        dictionary_path (str): Path to the dictionary.
        servo_status_listener (bool): Toggle the listener of the servo for
            its status, errors, faults, etc.

    """
    STATUS_WORD_REGISTERS = {
        1: EthernetRegister(
            identifier='', units='', subnode=1, address=0x0011,
            cyclic='CYCLIC_TX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
        ),
        2: EthernetRegister(
            identifier='', units='', subnode=2, address=0x0011,
            cyclic='CYCLIC_TX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
        ),
        3: EthernetRegister(
            identifier='', units='', subnode=3, address=0x0011,
            cyclic='CYCLIC_TX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
        )
    }
    RESTORE_COCO_ALL = EthernetRegister(
        identifier='', units='', subnode=0, address=0x06DC, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )
    RESTORE_MOCO_ALL_REGISTERS = {
        1: EthernetRegister(
            identifier='', units='', subnode=1, address=0x06DC,
            cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
        ),
        2: EthernetRegister(
            identifier='', units='', subnode=2, address=0x06DC,
            cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
        ),
        3: EthernetRegister(
            identifier='', units='', subnode=3, address=0x06DC,
            cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
        )
    }

    def __init__(self, socket, dictionary_path=None,
                 servo_status_listener=False):
        self.socket = socket
        self.ip_address, self.port = self.socket.getpeername()
        if dictionary_path is not None:
            self._dictionary = EthernetDictionary(dictionary_path)
        else:
            self._dictionary = None
        self.__lock = threading.RLock()
        super(EthernetServo, self).__init__(self.ip_address)

    def store_tcp_ip_parameters(self):
        """Stores the TCP/IP values. Affects IP address,
        subnet mask and gateway"""
        self.write(reg=STORE_COCO_ALL,
                   data=PASSWORD_STORE_RESTORE_TCP_IP,
                   subnode=0)
        logger.info('Store TCP/IP successfully done.')

    def restore_tcp_ip_parameters(self):
        """Restores the TCP/IP values back to default. Affects
        IP address, subnet mask and gateway"""
        self.write(reg=self.RESTORE_COCO_ALL,
                   data=PASSWORD_STORE_RESTORE_TCP_IP,
                   subnode=0)
        logger.info('Restore TCP/IP successfully done.')

    def change_tcp_ip_parameters(self, ip_address, subnet_mask, gateway):
        """Stores the TCP/IP values. Affects IP address,
        network mask and gateway

        .. note::
            The drive needs a power cycle after this
            in order for the changes to be properly applied.

        Args:
            ip_address (str): IP Address to be changed.
            subnet_mask (str): Subnet mask to be changed.
            gateway (str): Gateway to be changed.

        Raises:
            ValueError: If the drive or gateway IP is not a
            valid IP address.
            ValueError: If the drive IP and gateway IP are not
            on the same network.
            NetmaskValueError: If the subnet_mask is not a valid
            netmask.

        """
        drive_ip = ipaddress.ip_address(ip_address)
        gateway_ip = ipaddress.ip_address(gateway)
        net = ipaddress.IPv4Network(f'{drive_ip}/{subnet_mask}', strict=False)

        if gateway_ip not in net:
            raise ValueError(f'Drive IP {ip_address} and Gateway IP {gateway} '
                             f'are not on the same network.')

        int_ip_address = convert_ip_to_int(ip_address)
        int_subnet_mask = convert_ip_to_int(subnet_mask)
        int_gateway = convert_ip_to_int(gateway)

        self.write(COMMS_ETH_IP, int_ip_address)
        self.write(COMMS_ETH_NET_MASK, int_subnet_mask)
        self.write(COMMS_ETH_NET_GATEWAY, int_gateway)

        try:
            self.store_tcp_ip_parameters()
        except ILError:
            self.store_parameters()

    def write(self, reg, data, subnode=1):
        """Writes data to a register.

        Args:
            reg (EthernetRegister, str): Target register to be written.
            data (int, str, float): Data to be written.
            subnode (int): Target axis of the drive.

        """
        _reg = self._get_reg(reg, subnode)
        if isinstance(data, float) and _reg.dtype != REG_DTYPE.FLOAT:
            data = int(data)
        data_bytes = convert_dtype_to_bytes(data, _reg.dtype)
        self._send_mcb_frame(MCB_CMD_WRITE, _reg.address, _reg.subnode, data_bytes)

    def read(self, reg, subnode=1):
        """Read a register value from servo.

        Args:
            reg (str, Register): Register.
            subnode (int): Target axis of the drive.

        Returns:
            int, float or str: Value stored in the register.
        """
        _reg = self._get_reg(reg, subnode)
        data = self._send_mcb_frame(MCB_CMD_READ, _reg.address, _reg.subnode)
        return convert_bytes_to_dtype(data, _reg.dtype)

    def _send_mcb_frame(self, cmd, reg, subnode, data=None):
        """Send an MCB frame to the drive.

        Args:
            cmd (int): Read/write command.
            reg (int): Register address to be read/written.
            subnode (int): Target axis of the drive.
            data (bytes): Data to be written to the register.

        Returns:
            bytes: The response frame.
        """
        frame = MCB.build_mcb_frame(cmd, subnode, reg, data)
        self.__lock.acquire()
        self.socket.sendall(frame)
        response = self.socket.recv(1024)
        self.__lock.release()
        return MCB.read_mcb_data(reg, response)

    def monitoring_disable(self):
        """Disable monitoring process."""
        self.write(MONITORING_DIST_ENABLE, data=0, subnode=0)

    def monitoring_remove_data(self):
        """Remove monitoring data."""
        self.write(MONITORING_REMOVE_DATA,
                   data=1, subnode=0)

    def monitoring_set_mapped_register(self, channel, address, subnode,
                                       dtype, size):
        """Set monitoring mapped register.

        Args:
            channel (int): Identity channel number.
            address (int): Register address to map.
            subnode (int): Subnode to be targeted.
            dtype (int): Register data type.
            size (int): Size of data in bytes.

        """
        self.__monitoring_channels_size[channel] = size
        self.__monitoring_channels_dtype[channel] = REG_DTYPE(dtype)
        data = self.__monitoring_disturbance_data_to_map_register(subnode,
                                                                  address,
                                                                  dtype,
                                                                  size)
        self.write(self.__monitoring_map_register(), data=data,
                   subnode=0)
        self.__monitoring_update_num_mapped_registers()
        self.__monitoring_num_mapped_registers = \
            self.monitoring_get_num_mapped_registers()
        self.write(MONITORING_NUMBER_MAPPED_REGISTERS,
                   data=self.monitoring_number_mapped_registers,
                   subnode=subnode)

    def monitoring_get_num_mapped_registers(self):
        """Obtain the number of monitoring mapped registers.

        Returns:
            int: Actual number of mapped registers.

        """
        return self.read('MON_CFG_TOTAL_MAP', 0)

    @staticmethod
    def __monitoring_disturbance_data_to_map_register(subnode, address,
                                                      dtype, size):
        """Arrange necessary data to map a monitoring/disturbance register.

        Args:
            subnode (int): Subnode to be targeted.
            address (int): Register address to map.
            dtype (int): Register data type.
            size (int): Size of data in bytes.

        """
        data_h = address | subnode << 12
        data_l = dtype << 8 | size
        return (data_h << 16) | data_l

    def __monitoring_map_register(self):
        """Get the first available Monitoring Mapped Register slot.

        Returns:
            str: Monitoring Mapped Register ID.

        """
        if self.monitoring_number_mapped_registers < 10:
            register_id = f'MON_CFG_REG' \
                          f'{self.monitoring_number_mapped_registers}_MAP'
        else:
            register_id = f'MON_CFG_REFG' \
                          f'{self.monitoring_number_mapped_registers}_MAP'
        return register_id

    def __monitoring_update_num_mapped_registers(self):
        """Update the number of mapped monitoring registers."""
        self.__monitoring_num_mapped_registers += 1
        self.write('MON_CFG_TOTAL_MAP',
                   data=self.__monitoring_num_mapped_registers,
                   subnode=0)

    @property
    def monitoring_number_mapped_registers(self):
        """Get the number of mapped monitoring registers."""
        return self.__monitoring_num_mapped_registers

    def monitoring_remove_all_mapped_registers(self):
        """Remove all monitoring mapped registers."""
        self.write(MONITORING_NUMBER_MAPPED_REGISTERS, data=0, subnode=0)
        self.__monitoring_num_mapped_registers = \
            self.monitoring_get_num_mapped_registers()
        self.__monitoring_channels_size = {}
        self.__monitoring_channels_dtype = {}

    def monitoring_get_bytes_per_block(self):
        """Obtain Bytes x Block configured.

        Returns:
            int: Actual number of Bytes x Block configured.

        """
        return self.read(MONITORING_BYTES_PER_BLOCK, subnode=0)

    def monitoring_actual_number_bytes(self):
        """Get the number of monitoring bytes left to be read."""
        return self.read(MONITORING_ACTUAL_NUMBER_BYTES, subnode=0)

    @property
    def monitoring_data_size(self):
        """Obtain monitoring data size.

        Returns:
            int: Current monitoring data size in bytes.

        """
        number_of_samples = self.read('MON_CFG_WINDOW_SAMP', subnode=0)
        return self.monitoring_get_bytes_per_block() * number_of_samples

    def monitoring_read_data(self):
        """Obtain processed monitoring data.

        Returns:
            array: Actual processed monitoring data.

        """
        num_available_bytes = self.monitoring_actual_number_bytes()
        self.__monitoring_data = []
        while num_available_bytes > 0:
            if num_available_bytes < MONITORING_BUFFER_SIZE:
                limit = num_available_bytes
            else:
                limit = MONITORING_BUFFER_SIZE
            tmp_data = self.__monitoring_read_data()[:limit]
            self.__monitoring_data.append(tmp_data)
            num_available_bytes = self.monitoring_actual_number_bytes()
        self.__monitoring_process_data()

    def __monitoring_read_data(self):
        """Read monitoring data frame."""
        return self._send_mcb_frame(MCB_CMD_READ,
                                    MONITORING_DATA.address,
                                    MONITORING_DATA.subnode)

    def __monitoring_process_data(self):
        """Arrange monitoring data."""
        data_bytes = bytearray()
        for i in range(len(self.__monitoring_data)):
            data_bytes += self.__monitoring_data[i]
        bytes_per_block = self.monitoring_get_bytes_per_block()
        number_of_blocks = len(data_bytes) // bytes_per_block
        number_of_channels = self.monitoring_get_num_mapped_registers()
        res = [[] for _ in range(number_of_channels)]
        for block in range(number_of_blocks):
            block_data = data_bytes[block * bytes_per_block:
                                    block * bytes_per_block +
                                    bytes_per_block]
            for channel in range(number_of_channels):
                channel_data_size = self.__monitoring_channels_size[channel]
                val = convert_bytes_to_dtype(
                        block_data[:channel_data_size],
                        self.__monitoring_channels_dtype[channel])
                res[channel].append(val)
                block_data = block_data[channel_data_size:]
        self.__processed_monitoring_data = res

    def monitoring_channel_data(self, channel, dtype=None):
        """Obtain processed monitoring data of a channel.

        Args:
            channel (int): Identity channel number.
            dtype (REG_DTYPE): Data type of the register to map.

        Note:
            The dtype argument is not necessary for this function, it
            was added to maintain compatibility with IPB's implementation
            of monitoring.

        Returns:
            List: Monitoring data.

        """
        return self.__processed_monitoring_data[channel]

    def disturbance_enable(self):
        """Enable disturbance process."""
        self.write(DISTURBANCE_ENABLE, data=1, subnode=0)

    def disturbance_disable(self):
        """Disable disturbance process."""
        self.write(DISTURBANCE_ENABLE, data=0, subnode=0)

    def disturbance_remove_data(self):
        """Remove disturbance data."""
        self.write(DISTURBANCE_REMOVE_DATA,
                   data=1, subnode=0)
        self.disturbance_data = bytearray()
        self.disturbance_data_size = 0

    def disturbance_set_mapped_register(self, channel, address, subnode,
                                        dtype, size):
        """Set monitoring mapped register.

        Args:
            channel (int): Identity channel number.
            address (int): Register address to map.
            subnode (int): Subnode to be targeted.
            dtype (int): Register data type.
            size (int): Size of data in bytes.

        """
        self.__disturbance_channels_size[channel] = size
        self.__disturbance_channels_dtype[channel] = REG_DTYPE(dtype).name
        data = self.__monitoring_disturbance_data_to_map_register(subnode,
                                                                  address,
                                                                  dtype,
                                                                  size)
        self.write(self.__disturbance_map_register(), data=data,
                   subnode=0)
        self.__disturbance_update_num_mapped_registers()
        self.__disturbance_num_mapped_registers = \
            self.disturbance_get_num_mapped_registers()
        self.write(DISTURBANCE_NUMBER_MAPPED_REGISTERS,
                   data=self.disturbance_number_mapped_registers,
                   subnode=subnode)

    def disturbance_get_num_mapped_registers(self):
        """Obtain the number of disturbance mapped registers.

        Returns:
            int: Actual number of mapped registers.

        """
        return self.read('DIST_CFG_MAP_REGS', 0)

    def __disturbance_map_register(self):
        """Get the first available Disturbance Mapped Register slot.

        Returns:
            str: Disturbance Mapped Register ID.

        """
        return f'DIST_CFG_REG{self.disturbance_number_mapped_registers}_MAP'

    def __disturbance_update_num_mapped_registers(self):
        """Update the number of mapped disturbance registers."""
        self.__disturbance_num_mapped_registers += 1
        self.write('DIST_CFG_MAP_REGS',
                   data=self.__disturbance_num_mapped_registers,
                   subnode=0)

    @property
    def disturbance_number_mapped_registers(self):
        """Get the number of mapped disturbance registers."""
        return self.__disturbance_num_mapped_registers

    @property
    def disturbance_data(self):
        """Obtain disturbance data.

        Returns:
            array: Current disturbance data.

        """
        return self.__disturbance_data

    @disturbance_data.setter
    def disturbance_data(self, value):
        """Set disturbance data.

        Args:
            value (array): Array with the disturbance to send.

        """
        self.__disturbance_data = value

    @property
    def disturbance_data_size(self):
        """Obtain disturbance data size.

        Returns:
            int: Current disturbance data size.

        """
        return self.__disturbance_data_size

    @disturbance_data_size.setter
    def disturbance_data_size(self, value):
        """Set disturbance data size.

        Args:
            value (int): Disturbance data size in bytes.

        """
        self.__disturbance_data_size = value

    def disturbance_remove_all_mapped_registers(self):
        """Remove all disturbance mapped registers."""
        self.write(DISTURBANCE_NUMBER_MAPPED_REGISTERS,
                   data=0, subnode=0)
        self.__disturbance_num_mapped_registers = \
            self.disturbance_get_num_mapped_registers()
        self.__disturbance_channels_size = {}
        self.__disturbance_channels_dtype = {}

    def disturbance_write_data(self, channels, dtypes, data_arr):
        """Write disturbance data.

        Args:
            channels (int or list of int): Channel identifier.
            dtypes (int or list of int): Data type.
            data_arr (list or list of list): Data array.

        """
        if not isinstance(channels, list):
            channels = [channels]
        if not isinstance(dtypes, list):
            dtypes = [dtypes]
        if not isinstance(data_arr[0], list):
            data_arr = [data_arr]
        num_samples = len(data_arr[0])
        self.write(DIST_NUMBER_SAMPLES, num_samples, subnode=0)
        data = bytearray()
        for sample_idx in range(num_samples):
            for channel in range(len(data_arr)):
                val = convert_dtype_to_bytes(
                    data_arr[channel][sample_idx], dtypes[channel])
                data += val
        chunks = [data[i:i + ETH_MAX_WRITE_SIZE]
                  for i in range(0, len(data), ETH_MAX_WRITE_SIZE)]
        for chunk in chunks:
            self._send_mcb_frame(MCB_CMD_WRITE, DIST_DATA.address,
                                 DIST_DATA.subnode, chunk)
        self.disturbance_data = data
        self.disturbance_data_size = len(data)

    def get_state(self, subnode=1):
        """SERVO_STATE: Current drive state."""
        return self.__state[subnode], None

    def subscribe_to_status(self, callback):
        """Subscribe to state changes.

            Args:
                callback (function): Callback function.

            Returns:
                int: Assigned slot.

        """
        if callback in self.__observers_servo_state:
            logger.info('Callback already subscribed.')
            return
        self.__observers_servo_state.append(callback)

    def unsubscribe_from_status(self, callback):
        """Unsubscribe from state changes.

        Args:
            callback (function): Callback function.

        """
        if callback not in self.__observers_servo_state:
            logger.info('Callback not subscribed.')
            return
        self.__observers_servo_state.remove(callback)

    def store_parameters(self, subnode=None):
        """Store all the current parameters of the target subnode.

        Args:
            subnode (int): Subnode of the axis. `None` by default which stores
            all the parameters.

        Raises:
            ILError: Invalid subnode.
            ILObjectNotExist: Failed to write to the registers.

        """
        r = 0
        try:
            if subnode is None:
                # Store all
                try:
                    self.write(reg=STORE_COCO_ALL,
                               data=PASSWORD_STORE_ALL,
                               subnode=0)
                    logger.info('Store all successfully done.')
                except ILError as e:
                    logger.warning(f'Store all COCO failed. Reason: {e}. '
                                   f'Trying MOCO...')
                    r = -1
                if r < 0:
                    for dict_subnode in range(1, self.dictionary.subnodes):
                        self.write(
                            reg=STORE_MOCO_ALL_REGISTERS[dict_subnode],
                            data=PASSWORD_STORE_ALL,
                            subnode=dict_subnode)
                        logger.info(f'Store axis {dict_subnode} successfully'
                                    f' done.')
            elif subnode == 0:
                # Store subnode 0
                raise ILError('The current firmware version does not '
                              'have this feature implemented.')
            elif subnode > 0 and subnode in STORE_MOCO_ALL_REGISTERS:
                # Store axis
                self.write(reg=STORE_MOCO_ALL_REGISTERS[subnode],
                           data=PASSWORD_STORE_ALL,
                           subnode=subnode)
                logger.info(f'Store axis {subnode} successfully done.')
            else:
                raise ILError('Invalid subnode.')
        finally:
            time.sleep(1.5)

    def disable(self, subnode=1, timeout=DEFAULT_PDS_TIMEOUT):
        """Disable PDS.

        Args:
            subnode (int): Subnode of the drive.
            timeout (int): Timeout in milliseconds.

        Raises:
            ILTimeoutError: The servo could not be disabled due to timeout.
            ILError: Failed to disable PDS.

        """
        r = 0

        status_word = self.read(self.STATUS_WORD_REGISTERS[subnode],
                                subnode=subnode)
        state = self.status_word_decode(status_word)
        self._set_state(state, subnode)

        while self.status[subnode].value != lib.IL_SERVO_STATE_DISABLED:
            state = self.status_word_decode(status_word)
            self._set_state(state, subnode)

            if self.status[subnode].value in [
                lib.IL_SERVO_STATE_FAULT,
                lib.IL_SERVO_STATE_FAULTR,
            ]:
                # Try fault reset if faulty
                self.fault_reset(subnode=subnode)
                status_word = self.read(self.STATUS_WORD_REGISTERS[subnode],
                                        subnode=subnode)
                state = self.status_word_decode(status_word)
                self._set_state(state, subnode)
            elif self.status[subnode].value != lib.IL_SERVO_STATE_DISABLED:
                # Check state and command action to reach disabled
                self.write(CONTROL_WORD_REGISTERS[subnode],
                           constants.IL_MC_PDS_CMD_DV, subnode=subnode)

                # Wait until status word changes
                r = self.status_word_wait_change(status_word, timeout,
                                                 subnode=subnode)
                if r < 0:
                    raise_err(r)
                status_word = self.read(self.STATUS_WORD_REGISTERS[subnode],
                                        subnode=subnode)
                state = self.status_word_decode(status_word)
                self._set_state(state, subnode)
        raise_err(r)

    def enable(self, subnode=1, timeout=DEFAULT_PDS_TIMEOUT):
        """Enable PDS.

        Args:
            subnode (int): Subnode of the drive.
            timeout (int): Timeout in milliseconds.

       Raises:
            ILTimeoutError: The servo could not be enabled due to timeout.
            ILError: Failed to enable PDS.

        """
        r = 0

        status_word = self.read(self.STATUS_WORD_REGISTERS[subnode],
                                subnode=subnode)
        state = self.status_word_decode(status_word)
        self._set_state(state, subnode)

        # Try fault reset if faulty
        if self.status[subnode].value in [
            lib.IL_SERVO_STATE_FAULT,
            lib.IL_SERVO_STATE_FAULTR,
        ]:
            self.fault_reset(subnode=subnode)

        while self.status[subnode].value != lib.IL_SERVO_STATE_ENABLED:
            status_word = self.read(self.STATUS_WORD_REGISTERS[subnode],
                                    subnode=subnode)
            state = self.status_word_decode(status_word)
            self._set_state(state, subnode)
            if self.status[subnode].value != lib.IL_SERVO_STATE_ENABLED:
                # Check state and command action to reach enabled
                cmd = constants.IL_MC_PDS_CMD_EO
                if self.status[subnode].value == lib.IL_SERVO_STATE_FAULT:
                    raise_err(lib.IL_ESTATE)
                elif self.status[subnode].value == lib.IL_SERVO_STATE_NRDY:
                    cmd = constants.IL_MC_PDS_CMD_DV
                elif self.status[subnode].value == \
                        lib.IL_SERVO_STATE_DISABLED:
                    cmd = constants.IL_MC_PDS_CMD_SD
                elif self.status[subnode].value == lib.IL_SERVO_STATE_RDY:
                    cmd = constants.IL_MC_PDS_CMD_SOEO

                self.write(CONTROL_WORD_REGISTERS[subnode], cmd,
                           subnode=subnode)

                # Wait for state change
                r = self.status_word_wait_change(status_word, timeout,
                                                 subnode=subnode)
                if r < 0:
                    raise_err(r)

                # Read the current status word
                status_word = self.read(self.STATUS_WORD_REGISTERS[subnode],
                                        subnode=subnode)
                state = self.status_word_decode(status_word)
                self._set_state(state, subnode)
        raise_err(r)

    @staticmethod
    def status_word_decode(status_word):
        """Decodes the status word to a known value.

        Args:
            status_word (int): Read value for the status word.

        Returns:
            SERVO_STATE: Status word value.

        """
        if (status_word & constants.IL_MC_PDS_STA_NRTSO_MSK) == \
                constants.IL_MC_PDS_STA_NRTSO:
            state = lib.IL_SERVO_STATE_NRDY
        elif (status_word & constants.IL_MC_PDS_STA_SOD_MSK) == \
                constants.IL_MC_PDS_STA_SOD:
            state = lib.IL_SERVO_STATE_DISABLED
        elif (status_word & constants.IL_MC_PDS_STA_RTSO_MSK) == \
                constants.IL_MC_PDS_STA_RTSO:
            state = lib.IL_SERVO_STATE_RDY
        elif (status_word & constants.IL_MC_PDS_STA_SO_MSK) == \
                constants.IL_MC_PDS_STA_SO:
            state = lib.IL_SERVO_STATE_ON
        elif (status_word & constants.IL_MC_PDS_STA_OE_MSK) == \
                constants.IL_MC_PDS_STA_OE:
            state = lib.IL_SERVO_STATE_ENABLED
        elif (status_word & constants.IL_MC_PDS_STA_QSA_MSK) == \
                constants.IL_MC_PDS_STA_QSA:
            state = lib.IL_SERVO_STATE_QSTOP
        elif (status_word & constants.IL_MC_PDS_STA_FRA_MSK) == \
                constants.IL_MC_PDS_STA_FRA:
            state = lib.IL_SERVO_STATE_FAULTR
        elif (status_word & constants.IL_MC_PDS_STA_F_MSK) == \
                constants.IL_MC_PDS_STA_F:
            state = lib.IL_SERVO_STATE_FAULT
        else:
            state = lib.IL_SERVO_STATE_NRDY
        return SERVO_STATE(state)

    def _set_state(self, state, subnode):
        """Sets the state internally.

        Args:
            state (SERVO_STATE): Current servo state.
            subnode (int): Subnode of the drive.

        """
        current_state = self.__state[subnode]
        if current_state != state:
            self.status[subnode] = state
            for callback in self.__observers_servo_state:
                callback(state, None, subnode)

    def status_word_wait_change(self, status_word, timeout, subnode=1):
        """Waits for a status word change.

        Args:
            status_word (int): Status word to wait for.
            timeout (int): Maximum value to wait for the change.
            subnode (int): Subnode of the drive.

        Returns:
            int: Error code.

        """
        r = 0
        start_time = int(round(time.time() * 1000))
        actual_status_word = self.read(self.STATUS_WORD_REGISTERS[subnode],
                                       subnode=subnode)
        while actual_status_word == status_word:
            current_time = int(round(time.time() * 1000))
            time_diff = (current_time - start_time)
            if time_diff > timeout:
                r = lib.IL_ETIMEDOUT
                return r
            actual_status_word = self.read(
                self.STATUS_WORD_REGISTERS[subnode],
                subnode=subnode)
        return r

    def fault_reset(self, subnode=1, timeout=DEFAULT_PDS_TIMEOUT):
        """Executes a fault reset on the drive.

        Args:
            subnode (int): Subnode of the drive.
            timeout (int): Timeout in milliseconds.

        Raises:
            ILTimeoutError: If fault reset spend too much time.
            ILError: Failed to fault reset.

        """
        r = 0
        status_word = self.read(self.STATUS_WORD_REGISTERS[subnode],
                                subnode=subnode)
        state = self.status_word_decode(status_word)
        if state.value in [
            lib.IL_SERVO_STATE_FAULT,
            lib.IL_SERVO_STATE_FAULTR,
        ]:
            # Check if faulty, if so try to reset (0->1)
            self.write(CONTROL_WORD_REGISTERS[subnode], 0,
                       subnode=subnode)
            self.write(CONTROL_WORD_REGISTERS[subnode],
                       constants.IL_MC_CW_FR, subnode=subnode)
            # Wait until status word changes
            r = self.status_word_wait_change(status_word, timeout,
                                             subnode=subnode)
            status_word = self.read(self.STATUS_WORD_REGISTERS[subnode],
                                    subnode=subnode)
            state = self.status_word_decode(status_word)
        self._set_state(state, subnode)
        raise_err(r)

    def is_alive(self):
        """Checks if the servo responds to a reading a register.

        Returns:
            bool: Return code with the result of the read.

        """
        _is_alive = True
        try:
            self.read(self.STATUS_WORD_REGISTERS[1])
        except ILError as e:
            _is_alive = False
            logger.error(e)
        return _is_alive

    def reload_errors(self, dictionary):
        """Force to reload all dictionary errors.

        Args:
            dictionary (str): Dictionary.

        """
        pass

    def replace_dictionary(self, dictionary):
        """Deletes and creates a new instance of the dictionary.

        Args:
            dictionary (str): Dictionary.

        """
        self._dictionary = EthernetDictionary(dictionary)

    def __read_coco_moco_register(self, register_coco, register_moco):
        """Reads the COCO register and if it does not exist,
        reads the MOCO register

        Args:
            register_coco (EthernetRegister): COCO Register to be read.
            register_moco (EthernetRegister): MOCO Register to be read.

        Returns:
            int: Read value of the register.

        """
        try:
            return self.read(register_coco, subnode=0)
        except ILError:
            pass

        try:
            return self.read(register_moco, subnode=1)
        except ILError:
            pass

    @property
    def dictionary(self):
        """Returns dictionary object"""
        return self._dictionary

    @property
    def status(self):
        """tuple: Servo status and state flags."""
        return self.__state

    @property
    def info(self):
        """dict: Servo information."""
        serial_number = self.__read_coco_moco_register(
            SERIAL_NUMBER_REGISTERS[0], SERIAL_NUMBER_REGISTERS[1])
        sw_version = self.__read_coco_moco_register(
            SOFTWARE_VERSION_REGISTERS[0], SOFTWARE_VERSION_REGISTERS[1])
        product_code = self.__read_coco_moco_register(
            PRODUCT_ID_REGISTERS[0], PRODUCT_ID_REGISTERS[1])
        revision_number = self.__read_coco_moco_register(
            REVISION_NUMBER_REGISTERS[0], REVISION_NUMBER_REGISTERS[1])
        hw_variant = 'A'

        return {
            'name': self.name,
            'serial_number': serial_number,
            'firmware_version': sw_version,
            'product_code': product_code,
            'revision_number': revision_number,
            'hw_variant': hw_variant
        }

    @property
    def errors(self):
        """dict: Errors."""
        return self._dictionary.errors.errors

    @property
    def subnodes(self):
        """int: Number of subnodes."""
        return self._dictionary.subnodes
