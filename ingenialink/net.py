from enum import Enum
from time import sleep

from ._ingenialink import lib, ffi
from ingenialink.utils._utils import cstr, pstr, raise_null, raise_err, to_ms, deprecated
from ingenialink.utils.udp import UDP
from .registers import REG_DTYPE

import numpy as np
import os

import ingenialogger
logger = ingenialogger.get_logger(__name__)

CMD_CHANGE_CPU = 0x67E4


class NET_PROT(Enum):
    """ Network Protocol. """

    EUSB = lib.IL_NET_PROT_EUSB
    MCB = lib.IL_NET_PROT_MCB
    ETH = lib.IL_NET_PROT_ETH
    ECAT = lib.IL_NET_PROT_ECAT
    CAN = 5


class NET_STATE(Enum):
    """ Network State. """

    CONNECTED = lib.IL_NET_STATE_CONNECTED
    DISCONNECTED = lib.IL_NET_STATE_DISCONNECTED
    FAULTY = lib.IL_NET_STATE_FAULTY


class NET_DEV_EVT(Enum):
    """ Device Event. """

    ADDED = lib.IL_NET_DEV_EVT_ADDED
    REMOVED = lib.IL_NET_DEV_EVT_REMOVED


class EEPROM_TOOL_MODE(Enum):
    """ EEPROM tool mode. """

    MODE_NONE = 0
    MODE_READBIN = 1
    MODE_READINTEL = 2
    MODE_WRITEBIN = 3
    MODE_WRITEINTEL = 4
    MODE_WRITEALIAS = 5
    MODE_INFO = 6


class NET_TRANS_PROT(Enum):
    """ Transmission protocol. """

    TCP = 1
    UDP = 2


def devices(prot):
    """ Obtain a list of network devices.

    Args:
        prot (NET_PROT): Protocol.

    Returns:
        list: List of network devices.

    Raises:
        TypeError: If the protocol type is invalid.
    """
    if not isinstance(prot, NET_PROT):
        raise TypeError('Invalid protocol')

    devs = lib.il_net_dev_list_get(prot.value)

    found = []
    curr = devs

    while curr:
        found.append(pstr(curr.port))
        curr = curr.next

    lib.il_net_dev_list_destroy(devs)

    return found


@deprecated
def eeprom_tool(ifname, mode, filename):
    """ Tool to modify and verify drive EEPROM.

    Args:
        ifname (str): Interface name.
        mode (int): EEPROM tool mode.
        filename (str): Path to the EEPROM file.

    Returns:
        int: Result code.

    """
    net__ = ffi.new('il_net_t **')
    ifname = cstr(ifname) if ifname else ffi.NULL
    filename = cstr(filename) if filename else ffi.NULL

    return lib.il_net_eeprom_tool(net__, ifname, 1, mode.value, filename)


@deprecated
def master_startup(ifname, if_address_ip):
    """ Start SOEM master.

    Args:
        ifname (str): Interface name.
        if_address_ip (str): Interface address IP.

    Returns:
        int: Result code.
    """
    net__ = ffi.new('il_net_t **')
    ifname = cstr(ifname) if ifname else ffi.NULL
    if_address_ip = cstr(if_address_ip) if if_address_ip else ffi.NULL

    return lib.il_net_master_startup(net__, ifname, if_address_ip), net__


@deprecated
def num_slaves_get(ifname):
    ifname = cstr(ifname) if ifname else ffi.NULL
    return lib.il_net_num_slaves_get(ifname)


@deprecated
def master_stop(net):
    """
    Stop SOEM master.

    Returns:
        int: Result code.
    """
    return lib.il_net_master_stop(net)


@deprecated
def update_firmware_moco(node, subnode, ip, port, moco_file):
    """ Update MOCO firmware through UDP protocol.

    Args:
        node: Network node.
        subnode: Drive subnode.
        ip: Drive address IP.
        port: Drive port.
        moco_file: Path to the firmware file.

    Returns:
        int: Result code.
    """
    r = 1
    upd = UDP(port, ip)

    if moco_file and os.path.isfile(moco_file):
        moco_in = open(moco_file, "r")

        logger.info("Loading firmware...")
        try:
            for line in moco_in:
                words = line.split()

                # Get command and address
                cmd = int(words[1] + words[0], 16)
                data = b''
                data_start_byte = 2
                while data_start_byte in range(data_start_byte, len(words)):
                    # Load UDP data
                    data = data + bytes([int(words[data_start_byte], 16)])
                    data_start_byte = data_start_byte + 1

                # Send message
                upd.raw_cmd(node, subnode, cmd, data)

                if cmd == CMD_CHANGE_CPU:
                    sleep(1)

            logger.info("Bootloading process succeeded")
        except Exception as e:
            logger.error('Error during bootloading process. %s', e)
            r = -2
    else:
        logger.error('File not found')
        r = -1

    return r


@deprecated
def update_firmware(ifname, filename, is_summit=False, slave=1):
    """ Update firmware through FoE.

    Args:
        ifname: Interface name.
        filename: Path to the firmware file.
        is_summit:  [true] -> Everest
                    [false] -> Capitan or Low-Power drives
        slave: Slave number in the network.

    Returns:
        int: Result code.
    """
    net__ = ffi.new('il_net_t **')
    ifname = cstr(ifname) if ifname else ffi.NULL
    filename = cstr(filename) if filename else ffi.NULL
    return net__, lib.il_net_update_firmware(net__, ifname, slave,
                                             filename, is_summit)


@deprecated
def force_error(ifname, if_address_ip):
    """ Force state machine error.

    Args:
        ifname: Interface name.
        if_address_ip: Interface address IP.

    Returns:
        int: Result code.
    """
    net__ = ffi.new('il_net_t **')
    ifname = cstr(ifname) if ifname else ffi.NULL
    if_address_ip = cstr(if_address_ip) if if_address_ip else ffi.NULL

    return lib.il_net_force_error(net__, ifname, if_address_ip)


@ffi.def_extern()
def _on_found_cb(ctx, servo_id):
    """ On found callback shim. """
    self = ffi.from_handle(ctx)
    self._on_found(int(servo_id))


@ffi.def_extern()
def _on_evt_cb(ctx, evt, port):
    """ On event callback shim. """
    self = ffi.from_handle(ctx)
    self._on_evt(NET_DEV_EVT(evt), pstr(port))


class Network(object):
    """ Basic declaration of a common Network object. """
    def __init__(self):
        self.__servos = []

    @classmethod
    def _from_existing(cls, net):
        """ Create a new class instance from an existing network.

        Args:
            net (Network): Instance to copy.

        Returns:
            Network: New instanced class.

        """
        inst = cls.__new__(cls)
        inst._net = ffi.gc(net, lib.il_net_fake_destroy)

        return inst

    def monitoring_channel_data(self, channel, dtype):
        """ Obtain processed monitoring data of a channel.

        Args:
            channel (int): Identity channel number.
            dtype (REG_DTYPE): Data type of the register to map.

        Returns:
            array: Monitoring data.
        """
        data_arr = []
        size = int(self.monitoring_data_size)
        bytes_per_block = self.monitoring_get_bytes_per_block()
        if dtype == REG_DTYPE.U16:
            data_arr = lib.il_net_monitoring_channel_u16(self._net, channel)
        elif dtype == REG_DTYPE.S16:
            data_arr = lib.il_net_monitoring_channel_s16(self._net, channel)
        elif dtype == REG_DTYPE.U32:
            data_arr = lib.il_net_monitoring_channel_u32(self._net, channel)
        elif dtype == REG_DTYPE.S32:
            data_arr = lib.il_net_monitoring_channel_s32(self._net, channel)
        elif dtype == REG_DTYPE.FLOAT:
            data_arr = lib.il_net_monitoring_channel_flt(self._net, channel)
        ret_arr = []
        for i in range(0, int(size / bytes_per_block)):
            ret_arr.append(data_arr[i])
        return ret_arr

    def monitoring_remove_all_mapped_registers(self):
        """ Remove all monitoring mapped registers.

        Returns:
            int: Result code.
        """
        return lib.il_net_remove_all_mapped_registers(self._net)

    def monitoring_set_mapped_register(self, channel, reg_idx, dtype):
        """ Set monitoring mapped register.

        Args:
            channel (int): Identity channel number.
            reg_idx (int): Register address to map.
            dtype (REG_DTYPE): Data type of the register to map.

        Returns:
            int: Result code.
        """
        return lib.il_net_set_mapped_register(self._net, channel,
                                              reg_idx, dtype)

    def monitoring_get_num_mapped_registers(self):
        """ Obtain the number of mapped registers.

        Returns:
            int: Actual number of mapped registers.
        """
        return lib.il_net_num_mapped_registers_get(self._net)

    def monitoring_enable(self):
        """ Enable monitoring process.

        Returns:
            int: Result code.
        """
        return lib.il_net_enable_monitoring(self._net)

    def monitoring_disable(self):
        """ Disable monitoring process.

        Returns:
            int: Result code.
        """
        return lib.il_net_disable_monitoring(self._net)

    def monitoring_read_data(self):
        """ Obtain processed monitoring data.

        Returns:
            array: Actual processed monitoring data.
        """
        return lib.il_net_read_monitoring_data(self._net)

    def monitoring_get_bytes_per_block(self):
        """ Obtain Bytes x Block configured.

        Returns:
            int: Actual number of Bytes x Block configured.
        """
        return lib.il_net_monitornig_bytes_per_block_get(self._net)

    # Disturbance
    def disturbance_channel_data(self, channel, dtype, data_arr):
        """ Send disturbance data.

        Args:
            channel (int): Identity channel number.
            dtype (REG_DTYPE): Data type of the register mapped.
            data_arr (array): Data that will be sent to the drive.

        Returns:
            int: Return code.

        """
        if dtype == REG_DTYPE.U16:
            lib.il_net_disturbance_data_u16_set(self._net, channel, data_arr)
        elif dtype == REG_DTYPE.S16:
            lib.il_net_disturbance_data_s16_set(self._net, channel, data_arr)
        elif dtype == REG_DTYPE.U32:
            lib.il_net_disturbance_data_u32_set(self._net, channel, data_arr)
        elif dtype == REG_DTYPE.S32:
            lib.il_net_disturbance_data_s32_set(self._net, channel, data_arr)
        elif dtype == REG_DTYPE.FLOAT:
            lib.il_net_disturbance_data_flt_set(self._net, channel, data_arr)
        return 0

    def disturbance_remove_all_mapped_registers(self):
        """ Remove all disturbance mapped registers.

        Returns:
            int: Return code.
        """
        return lib.il_net_disturbance_remove_all_mapped_registers(self._net)

    def disturbance_set_mapped_register(self, channel, address, dtype):
        """ Set disturbance mapped register.

        Args:
            channel (int): Identity channel number.
            address (int): Register address to map.
            dtype (REG_DTYPE): Data type of the register to map.

        Returns:
            int: Return code.
        """
        return lib.il_net_disturbance_set_mapped_register(self._net, channel,
                                                          address, dtype)

    # SDOs
    def read_sdo(self, idx, subidx, dtype, slave=1):
        """ Read SDO from network.

        Args:
            idx (int): Register index.
            subidx (int): Register subindex.
            dtype (REG_DTYPE): Register data type.
            slave (int, Optional): Identifier of an slave in the network.

        Returns:
            float: Obtained value

        Raises:
            TypeError: If the register type is not valid.
        """
        v = ffi.new('double *')
        r = lib.il_net_SDO_read(self._net, slave, idx, subidx, dtype, v)
        raise_err(r)

        value = v[0]
        return value

    def read_string_sdo(self, idx, subidx, size, slave=1):
        """ Read string SDO from network.

        Args:
            idx (int): Register index.
            subidx (int): Register subindex.
            size (int): Size in bytes to read.
            slave (int, Optional): Identifier of an slave in the network.

        Returns:
            str: Obtained value

        Raises:
            TypeError: If the register type is not valid.
        """
        v = ffi.new("char[" + str(size) + "]")
        r = lib.il_net_SDO_read_string(self._net, slave, idx, subidx, size, v)
        raise_err(r)

        value = pstr(v)
        return value

    def write_sdo(self, idx, subidx, dtype, value, slave=1):
        """ Write SDO from network.

        Args:
            idx (int): Register index.
            subidx (int): Register subindex.
            dtype (REG_DTYPE): Register data type.
            value (float): Value to write.
            slave (int, Optional): Identifier of an slave in the network.

        Returns:
            float: Obtained value

        Raises:
            TypeError: If the register type is not valid.
        """
        r = lib.il_net_SDO_write(self._net, slave, idx, subidx, dtype, value)
        raise_err(r)

    def destroy_network(self):
        """ Destroy network instance. """
        lib.il_net_destroy(self._net)

    def set_reconnection_retries(self, retries):
        """ Set the number of reconnection retries in our application.

        Args:
            retries (int): Number of reconnection retries.
        """
        return lib.il_net_set_reconnection_retries(self._net, retries)

    def set_recv_timeout(self, timeout):
        """ Set receive communications timeout.

        Args:
            timeout (int): Timeout in ms.
        Returns:
            int: Result code.
        """
        return lib.il_net_set_recv_timeout(self._net, timeout)

    def set_status_check_stop(self, stop):
        """ Start/Stop the internal monitor of the drive status.

        Args:
            stop (int): 0 to START, 1 to STOP.
        Returns:
            int: Result code.
        """
        return lib.il_net_set_status_check_stop(self._net, stop)

    def close_socket(self):
        """ Closes the established network socket. """
        return lib.il_net_close_socket(self._net)

    def subscribe_to_network_status(self, on_evt):
        """ Calls given function everytime a connection/disconnection event is
        raised.

        Args:
            on_evt (Callback): Function that will be called every time an event
            is raised.
        """
        if self.prot == NET_PROT.ETH or self.prot == NET_PROT.ECAT:
            status = self.status
            while True:
                if status != self.status:
                    if self.status == 0:
                        on_evt(NET_DEV_EVT.ADDED)
                    elif self.status == 1:
                        on_evt(NET_DEV_EVT.REMOVED)
                    status = self.status
                sleep(1)

    def stop_network_monitor(self):
        """ Stop monitoring network events. """
        lib.il_net_mon_stop(self._net)

    @deprecated('start_network_monitor')
    def net_mon_status(self, on_evt):
        """ Calls given function everytime a connection/disconnection event is
        raised.

        Args:
            on_evt (Callback): Function that will be called every time an event
            is raised.
        """
        if self.prot == NET_PROT.ETH or self.prot == NET_PROT.ECAT:
            status = self.status
            while True:
                if status != self.status:
                    if self.status == 0:
                        on_evt(NET_DEV_EVT.ADDED)
                    elif self.status == 1:
                        on_evt(NET_DEV_EVT.REMOVED)
                    status = self.status
                sleep(1)

    @deprecated('stop_network_monitor')
    def net_mon_stop(self):
        """ Stop monitoring network events. """
        lib.il_net_mon_stop(self._net)

    @deprecated
    def set_if_params(self, ifname, if_address_ip):
        """ Set ethernet interface parameters.

        Args:
            ifname (str): Interface name.
            if_address_ip (str): Interface address IP.

        Returns:

        """
        return lib.il_net_set_if_params(self._net, ifname, if_address_ip)

    @deprecated
    def master_startup(self, ifname, if_address_ip):
        """ Start SOEM master.

        Args:
            ifname (str): Interface name.
            if_address_ip (str): Interface address IP.

        Returns:
            int: Result code.
        """
        ifname = cstr(ifname) if ifname else ffi.NULL
        if_address_ip = cstr(if_address_ip) if if_address_ip else ffi.NULL

        return lib.il_net_master_startup(self._net, ifname, if_address_ip)

    @deprecated
    def connect(self):
        """ Connect network. """
        r = lib.il_net_connect(self._net)
        raise_err(r)

    @deprecated
    def disconnect(self):
        """ Disconnect network. """
        lib.il_net_disconnect(self._net)

    @deprecated
    def master_stop(self):
        """ Stop SOEM master.

        Returns:
            int: Result code.
        """
        return lib.il_net_master_stop(self._net)

    @property
    def prot(self):
        """ Obtain network protocol.

        Returns:
            str: Current network protocol used.
        """
        return NET_PROT(lib.il_net_prot_get(self._net))

    @property
    def state(self):
        """ Obtain network state.

        Returns:
            str: Current network state.
        """
        return NET_STATE(lib.il_net_state_get(self._net))

    @property
    def status(self):
        """ Obtain network status.

        Returns:
            str: Current network status.
        """
        return lib.il_net_status_get(self._net)

    @property
    def port(self):
        """ Obtain network port.

        Returns:
            str: Current network port.
        """
        port = lib.il_net_port_get(self._net)
        return pstr(port)

    @property
    def extended_buffer(self):
        """ Obtain extended buffer data.

        Returns:
            str: Current extended buffer data.
        """
        ext_buff = lib.il_net_extended_buffer_get(self._net)
        return pstr(ext_buff)

    @property
    def monitoring_data(self):
        """ Obtain monitoring data.

        Returns:
            array: Current monitoring data.
        """
        monitoring_data = lib.il_net_monitornig_data_get(self._net)
        size = int(self.monitoring_data_size / 2)
        ret_arr = []
        for i in range(0, size):
            ret_arr.append(monitoring_data[i])
        return ret_arr

    @property
    def monitoring_data_size(self):
        """ Obtain monitoring data size.

        Returns:
            int: Current monitoring data size.
        """
        return lib.il_net_monitornig_data_size_get(self._net)

    @property
    def disturbance_data(self):
        """ Obtain disturbance data.

        Returns:
            array: Current disturbance data.
        """
        disturbance_data = lib.il_net_disturbance_data_get(self._net)
        size = int(self.disturbance_data_size / 2)
        ret_arr = []
        for i in range(0, size):
            ret_arr.append(disturbance_data[i])
        return ret_arr

    @disturbance_data.setter
    def disturbance_data(self, value):
        """ Set disturbance data.

        Args:
            value (array): Array with the disturbance to send.
        """
        disturbance_arr = value
        disturbance_arr = \
            np.pad(disturbance_arr,
                   (0, int(self.disturbance_data_size / 2) - len(value)),
                   'constant')
        lib.il_net_disturbance_data_set(self._net, disturbance_arr.tolist())

    @property
    def disturbance_data_size(self):
        """ Obtain disturbance data size.

        Returns:
            int: Current disturbance data size.
        """
        return lib.il_net_disturbance_data_size_get(self._net)

    @disturbance_data_size.setter
    def disturbance_data_size(self, value):
        """ Set disturbance data size.

        Args:
            value (int): Disturbance data size in bytes.
        """
        lib.il_net_disturbance_data_size_set(self._net, value)

    @property
    def servos(self):
        return self.__servos

    @servos.setter
    def servos(self, value):
        self.__servos = value


class NetworkMonitor(object):
    """ Network Monitor.

    Args:
        prot (NET_PROT): Protocol.

    Raises:
        TypeError: If the protocol type is invalid.
        ILCreationError: If the monitor cannot be created.
    """
    def __init__(self, prot):
        if not isinstance(prot, NET_PROT):
            raise TypeError('Invalid protocol')

        mon = lib.il_net_dev_mon_create(prot.value)
        raise_null(mon)

        self._mon = ffi.gc(mon, lib.il_net_dev_mon_destroy)

    def start(self, on_evt):
        """ Start the monitor.

        Args:
            on_evt (callback): Callback function.
        """
        self._on_evt = on_evt
        self._handle = ffi.new_handle(self)

        r = lib.il_net_dev_mon_start(self._mon, lib._on_evt_cb, self._handle)
        raise_err(r)

    def stop(self):
        """ Stop the monitor. """
        lib.il_net_dev_mon_stop(self._mon)



