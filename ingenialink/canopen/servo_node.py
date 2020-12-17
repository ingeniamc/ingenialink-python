import time
import threading
import canopen
import struct
import xml.etree.ElementTree as ET

from .._utils import *
from .constants import *
from ..servo import SERVO_STATE
from .._ingenialink import ffi, lib
from .dictionary import DictionaryCANOpen
from .registers import Register, REG_DTYPE, REG_ACCESS

SERIAL_NUMBER = Register(
    identifier='', units='', subnode=1, idx="0x26E6", subidx="0x00", cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)
PRODUCT_CODE = Register(
    identifier='', units='', subnode=1, idx="0x26E1", subidx="0x00", cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)
SOFTWARE_VERSION = Register(
    identifier='', units='', subnode=1, idx="0x26E4", subidx="0x00", cyclic='CONFIG',
    dtype=REG_DTYPE.STR, access=REG_ACCESS.RO
)
REVISION_NUMBER = Register(
    identifier='', units='', subnode=1, idx="0x26E2", subidx="0x00", cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)

STATUS_WORD_REGISTERS = {
    1: Register(
        identifier='', units='', subnode=1, idx="0x6041", subidx="0x00", cyclic='CYCLIC_TX',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
    ),
    2: Register(
        identifier='', units='', subnode=2, idx="0x6841", subidx="0x00", cyclic='CYCLIC_TX',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
    ),
    3: Register(
        identifier='', units='', subnode=3, idx="0x7041", subidx="0x00", cyclic='CYCLIC_TX',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
    )
}

CONTROL_WORD_REGISTERS = {
    1: Register(
        identifier='', units='', subnode=1, idx="0x2010", subidx="0x00", cyclic='CYCLIC_RX',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    ),
    2: Register(
        identifier='', units='', subnode=2, idx="0x2810", subidx="0x00", cyclic='CYCLIC_RX',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    ),
    3: Register(
        identifier='', units='', subnode=3, idx="0x3010", subidx="0x00", cyclic='CYCLIC_RX',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    )
}

STORE_ALL_REGISTERS = {
    1: Register(
        identifier='', units='', subnode=1, idx="0x26DB", subidx="0x00", cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    ),
    2: Register(
        identifier='', units='', subnode=2, idx="0x2EDB", subidx="0x00", cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    ),
    3: Register(
        identifier='', units='', subnode=3, idx="0x36DB", subidx="0x00", cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )
}


class DriveStatusThread(threading.Thread):
    def __init__(self, parent):
        """ Constructor, setting initial variables """
        super(DriveStatusThread, self).__init__()
        self.__parent = parent
        self.__stop = False

    def run(self):
        while not self.__stop:
            for subnode in range(1, self.__parent.subnodes):
                try:
                    status_word = self.__parent.raw_read(STATUS_WORD_REGISTERS[subnode], subnode=subnode)
                    state = self.__parent.status_word_decode(status_word)
                    self.__parent.set_state(state, subnode=subnode)
                except Exception as e:
                    print('IL: Error getting drive status. Exception: {}'.format(e))
            time.sleep(1.5)

    def activate_stop_flag(self):
        self.__stop = True


class Servo(object):
    def __init__(self, net, node, dict, boot_mode=False):
        self.__net = net
        self.__node = node
        self.__dict = DictionaryCANOpen(dict)
        self.__info = {}
        self.__state = {
            1: lib.IL_SERVO_STATE_NRDY,
            2: lib.IL_SERVO_STATE_NRDY,
            3: lib.IL_SERVO_STATE_NRDY
        }
        self.__observers = []
        self.__lock = threading.RLock()
        self.__units_torque = None
        self.__units_pos = None
        self.__units_vel = None
        self.__units_acc = None
        self.__name = "Drive"
        self.__drive_status_thread = None
        if not boot_mode:
            self.init_info()

    def init_info(self):
        serial_number = self.raw_read(SERIAL_NUMBER)
        product_code = self.raw_read(PRODUCT_CODE)
        sw_version = self.raw_read(SOFTWARE_VERSION)
        revision_number = self.raw_read(REVISION_NUMBER)
        hw_variant = 'A'
        # Set the current state of servo
        status_word = self.raw_read(STATUS_WORD_REGISTERS[1])
        state = self.status_word_decode(status_word)
        self.set_state(state, 1)
        self.__info = {
            'serial': serial_number,
            'name': self.__name,
            'sw_version': sw_version,
            'hw_variant': hw_variant,
            'prod_code': product_code,
            'revision': revision_number
        }
        self.__drive_status_thread = DriveStatusThread(self)
        self.__drive_status_thread.start()

    def stop_drive_status_thread(self):
        if self.__drive_status_thread is not None and self.__drive_status_thread.is_alive():
            self.__drive_status_thread.activate_stop_flag()
            self.__drive_status_thread.join()
            self.__drive_status_thread = None

    def emcy_subscribe(self, callback):
        pass

    def emcy_unsubscribe(self, callback):
        pass

    def get_reg(self, reg, subnode=1):
        if isinstance(reg, Register):
            _reg = reg
        elif isinstance(reg, str):
            _dict = self.__dict
            if not _dict:
                raise ValueError('No dictionary loaded')
            if reg not in _dict.regs[subnode]:
                raise TypeError('Invalid register')
            _reg = _dict.regs[subnode][reg]
        else:
            raise TypeError('Invalid register')
        return _reg

    def raw_read(self, reg, subnode=1):
        """ Raw read from servo.

            Args:
                reg (Register): Register.

            Returns:
                int: Otained value

            Raises:
                TypeError: If the register type is not valid.
        """
        _reg = self.get_reg(reg, subnode)

        access = _reg.access
        if access == REG_ACCESS.WO:
            raise TypeError('Register is Write-only')

        value = None
        dtype = _reg.dtype
        error_raised = None
        try:
            self.__lock.acquire()
            if dtype == REG_DTYPE.S8:
                value = int.from_bytes(
                    self.__node.sdo.upload(int(str(_reg.idx), 16), int(str(_reg.subidx), 16)),
                    "little",
                    signed=True
                )
            elif dtype == REG_DTYPE.S16:
                value = int.from_bytes(
                    self.__node.sdo.upload(int(str(_reg.idx), 16), int(str(_reg.subidx), 16)),
                    "little",
                    signed=True
                )
            elif dtype == REG_DTYPE.S32:
                value = int.from_bytes(
                    self.__node.sdo.upload(int(str(_reg.idx), 16), int(str(_reg.subidx), 16)),
                    "little",
                    signed=True
                )
            elif dtype == REG_DTYPE.FLOAT:
                [value] = struct.unpack('f', self.__node.sdo.upload(int(str(_reg.idx), 16), int(str(_reg.subidx), 16)))
            elif dtype == REG_DTYPE.STR:
                value = self.__node.sdo.upload(int(str(_reg.idx), 16), int(str(_reg.subidx), 16)).decode("utf-8")
            else:
                value = int.from_bytes(
                    self.__node.sdo.upload(int(str(_reg.idx), 16), int(str(_reg.subidx), 16)),
                    "little"
                )
        except Exception as e:
            print(_reg.identifier + " : " + str(e))
            error_raised = Exception("Read error")
        finally:
            self.__lock.release()

        if error_raised is not None:
            raise error_raised

        return value

    def read(self, reg, subnode=1):
        """ Read from servo.

            Args:
                reg (str, Register): Register.

            Returns:
                float: Otained value

            Raises:
                TypeError: If the register type is not valid.
        """
        return self.raw_read(reg, subnode=subnode)

    def change_sdo_timeout(self, value):
        self.__node.sdo.RESPONSE_TIMEOUT = value

    def write(self, reg, data, confirm=True, extended=0, subnode=1):
        return self.raw_write(reg, data, confirm=True, extended=0, subnode=subnode)

    def raw_write(self, reg, data, confirm=True, extended=0, subnode=1):
        """ Raw write to servo.

            Args:
                reg (Register): Register.
                data (int): Data.
                confirm (bool, optional): Confirm write.
                extended (int, optional): Extended frame.

            Raises:
                TypeError: If any of the arguments type is not valid or
                    unsupported.
        """

        _reg = self.get_reg(reg, subnode)

        if _reg.access == REG_ACCESS.RO:
            raise TypeError('Register is Read-only')

        # auto cast floats if register is not float
        if _reg.dtype == REG_DTYPE.FLOAT:
            data = float(data)
        elif _reg.dtype == REG_DTYPE.DOMAIN:
            pass
        else:
            data = int(data)

        error_raised = None
        try:
            self.__lock.acquire()
            if _reg.dtype == REG_DTYPE.FLOAT:
                self.__node.sdo.download(int(str(_reg.idx), 16), int(str(_reg.subidx), 16),
                                         struct.pack('f', data))
            elif _reg.dtype == REG_DTYPE.DOMAIN:
                self.__node.sdo.download(int(str(_reg.idx), 16), int(str(_reg.subidx), 16), data)
            else:
                bytes_length = 2
                signed = False
                if _reg.dtype == REG_DTYPE.U8:
                    bytes_length = 1
                elif _reg.dtype == REG_DTYPE.S8:
                    bytes_length = 1
                    signed = True
                elif _reg.dtype == REG_DTYPE.U16:
                    bytes_length = 2
                elif _reg.dtype == REG_DTYPE.S16:
                    bytes_length = 2
                    signed = True
                elif _reg.dtype == REG_DTYPE.U32:
                    bytes_length = 4
                elif _reg.dtype == REG_DTYPE.S32:
                    bytes_length = 4
                    signed = True

                self.__node.sdo.download(int(str(_reg.idx), 16), int(str(_reg.subidx), 16),
                                         data.to_bytes(bytes_length, byteorder='little', signed=signed))
        except Exception as e:
            print(_reg.identifier + " : " + str(e))
            error_raised = Exception("Write error")
        finally:
            self.__lock.release()

        if error_raised is not None:
            raise error_raised

    def get_all_registers(self):
        for obj in self.__node.object_dictionary.values():
            print('0x%X: %s' % (obj.index, obj.name))
            if isinstance(obj, canopen.objectdictionary.Record):
                for subobj in obj.values():
                    print('  %d: %s' % (subobj.subindex, subobj.name))

    def dict_storage_read(self, new_path):
        """Read all dictionary registers content and put it to the dictionary
        storage."""

        with open(self.__dict.dict, 'r') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()

        axis = tree.findall('*/Device/Axes/Axis')
        if axis:
            # Multiaxis
            registers = root.findall('./Body/Device/Axes/Axis/Registers/Register')
        else:
            # Single axis
            registers = root.findall('./Body/Device/Registers/Register')

        for element in registers:
            try:
                if element.attrib['access'] == 'rw':
                    subnode = int(element.attrib['subnode'])
                    storage = self.raw_read(element.attrib['id'], subnode=subnode)
                    element.set('storage', str(storage))

                    # Update register object
                    reg = self.__dict.regs[subnode][element.attrib['id']]
                    reg.storage = storage
                    reg.storage_valid = 1
            except BaseException as e:
                print("Exception during dict_storage_read, register " + element.attrib['id'] + ": ", str(e))

        tree.write(new_path)
        xml_file.close()

    def dict_storage_write(self, path):
        """Write current dictionary storage to the servo drive."""
        with open(path, 'r') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()

        axis = tree.findall('*/Device/Axes/Axis')
        if axis:
            # Multiaxis
            registers = root.findall('./Body/Device/Axes/Axis/Registers/Register')
        else:
            # Single axis
            registers = root.findall('./Body/Device/Registers/Register')

        for element in registers:
            try:
                if 'storage' in element.attrib and element.attrib['access'] == 'rw':
                    self.raw_write(element.attrib['id'], float(element.attrib['storage']),
                                   subnode=int(element.attrib['subnode'])
                                   )
            except BaseException as e:
                print("Exception during dict_storage_write, register " + element.attrib['id'] + ": ", str(e))

    def store_all(self, subnode=1):
        """ Store all servo current parameters to the NVM. """
        r = 0
        try:
            self.raw_write(STORE_ALL_REGISTERS[subnode], 0x65766173, subnode=subnode)
        except:
            r = -1
        return r

    def dict_load(self, dict_f):
        """ Load dictionary.

            Args:
                dict_f (str): Dictionary.
        """
        try:
            self.__dict = DictionaryCANOpen(dict_f)
        except Exception as e:
            print("Error loading a dictionary")

    def state_subscribe(self, cb):
        """ Subscribe to state changes.

            Args:
                cb: Callback

            Returns:
                int: Assigned slot.
        """
        r = len(self.__observers)
        self.__observers.append(cb)
        return r

    def status_word_decode(self, status_word):
        if (status_word & IL_MC_PDS_STA_NRTSO_MSK) == IL_MC_PDS_STA_NRTSO:
            state = lib.IL_SERVO_STATE_NRDY
        elif (status_word & IL_MC_PDS_STA_SOD_MSK) == IL_MC_PDS_STA_SOD:
            state = lib.IL_SERVO_STATE_DISABLED
        elif (status_word & IL_MC_PDS_STA_RTSO_MSK) == IL_MC_PDS_STA_RTSO:
            state = lib.IL_SERVO_STATE_RDY
        elif (status_word & IL_MC_PDS_STA_SO_MSK) == IL_MC_PDS_STA_SO:
            state = lib.IL_SERVO_STATE_ON
        elif (status_word & IL_MC_PDS_STA_OE_MSK) == IL_MC_PDS_STA_OE:
            state = lib.IL_SERVO_STATE_ENABLED
        elif (status_word & IL_MC_PDS_STA_QSA_MSK) == IL_MC_PDS_STA_QSA:
            state = lib.IL_SERVO_STATE_QSTOP
        elif (status_word & IL_MC_PDS_STA_FRA_MSK) == IL_MC_PDS_STA_FRA:
            state = lib.IL_SERVO_STATE_FAULTR
        elif (status_word & IL_MC_PDS_STA_F_MSK) == IL_MC_PDS_STA_F:
            state = lib.IL_SERVO_STATE_FAULT
        else:
            state = lib.IL_SERVO_STATE_NRDY
        return SERVO_STATE(state)

    def set_state(self, state, subnode):
        current_state = self.__state[subnode]
        if current_state != state:
            self.state[subnode] = state
            for callback in self.__observers:
                callback(state, None, subnode)

    def status_word_wait_change(self, status_word, timeout, subnode=1):
        r = 0
        start_time = int(round(time.time() * 1000))
        actual_status_word = self.raw_read(STATUS_WORD_REGISTERS[subnode], subnode=1)
        while actual_status_word == status_word:
            current_time = int(round(time.time() * 1000))
            time_diff = (current_time - start_time)
            if time_diff > timeout:
                r = lib.IL_ETIMEDOUT
                return r
            actual_status_word = self.raw_read(STATUS_WORD_REGISTERS[subnode], subnode=1)
        return r

    def fault_reset(self, subnode=1):
        r = 0
        retries = 0
        status_word = self.raw_read(STATUS_WORD_REGISTERS[subnode], subnode=subnode)
        state = self.status_word_decode(status_word)
        self.set_state(state, subnode)
        while self.state[subnode].value == lib.IL_SERVO_STATE_FAULT or self.state[subnode].value == lib.IL_SERVO_STATE_FAULTR:
            # Check if faulty, if so try to reset (0->1)
            if retries == FAULT_RESET_RETRIES:
                return lib.IL_ESTATE

            status_word = self.raw_read(STATUS_WORD_REGISTERS[subnode], subnode=subnode)
            self.raw_write(CONTROL_WORD_REGISTERS[subnode], 0, subnode=subnode)
            self.raw_write(CONTROL_WORD_REGISTERS[subnode], IL_MC_CW_FR, subnode=subnode)
            # Wait until statusword changes
            r = self.status_word_wait_change(status_word, PDS_TIMEOUT, subnode=1)
            if r < 0:
                return r
            retries += 1
        return r

    def enable(self, timeout=2000, subnode=1):
        """ Enable PDS. """
        r = 0

        status_word = self.raw_read(STATUS_WORD_REGISTERS[subnode], subnode=subnode)
        state = self.status_word_decode(status_word)
        self.set_state(state, subnode)

        # Try fault reset if faulty
        if self.state[subnode].value == lib.IL_SERVO_STATE_FAULT or self.state[subnode].value == lib.IL_SERVO_STATE_FAULTR:
            r = self.fault_reset(subnode=subnode)
            if r < 0:
                return r

        while self.state[subnode].value != lib.IL_SERVO_STATE_ENABLED:
            status_word = self.raw_read(STATUS_WORD_REGISTERS[subnode], subnode=subnode)
            state = self.status_word_decode(status_word)
            self.set_state(state, subnode)
            if self.state[subnode].value != lib.IL_SERVO_STATE_ENABLED:
                # Check state and commandaction to reach enabled
                cmd = IL_MC_PDS_CMD_EO
                if self.state[subnode].value == lib.IL_SERVO_STATE_FAULT:
                    return lib.IL_ESTATE
                elif self.state[subnode].value == lib.IL_SERVO_STATE_NRDY:
                    cmd = IL_MC_PDS_CMD_DV
                elif self.state[subnode].value == lib.IL_SERVO_STATE_DISABLED:
                    cmd = IL_MC_PDS_CMD_SD
                elif self.state[subnode].value == lib.IL_SERVO_STATE_RDY:
                    cmd = IL_MC_PDS_CMD_SOEO

                self.raw_write(CONTROL_WORD_REGISTERS[subnode], cmd, subnode=subnode)

                # Wait for state change
                r = self.status_word_wait_change(status_word, PDS_TIMEOUT, subnode=1)
                if r < 0:
                    return r

                # Read the current status word
                status_word = self.raw_read(STATUS_WORD_REGISTERS[subnode], subnode=subnode)
                state = self.status_word_decode(status_word)
                self.set_state(state, subnode)
        raise_err(r)

    def disable(self, subnode=1):
        """ Disable PDS. """
        r = 0

        status_word = self.raw_read(STATUS_WORD_REGISTERS[subnode], subnode=subnode)
        state = self.status_word_decode(status_word)
        self.set_state(state, subnode)

        while self.state[subnode].value != lib.IL_SERVO_STATE_DISABLED:
            state = self.status_word_decode(status_word)
            self.set_state(state, subnode)

            if self.state[subnode].value == lib.IL_SERVO_STATE_FAULT or self.state[subnode].value == lib.IL_SERVO_STATE_FAULTR:
                # Try fault reset if faulty
                r = self.fault_reset(subnode=subnode)
                if r < 0:
                    return r
                status_word = self.raw_read(STATUS_WORD_REGISTERS[subnode], subnode=subnode)
                state = self.status_word_decode(status_word)
                self.set_state(state, subnode)
            elif self.state[subnode].value != lib.IL_SERVO_STATE_DISABLED:
                # Check state and command action to reach disabled
                self.raw_write(CONTROL_WORD_REGISTERS[subnode], IL_MC_PDS_CMD_DV, subnode=subnode)

                # Wait until statusword changes
                r = self.status_word_wait_change(status_word, PDS_TIMEOUT, subnode=1)
                if r < 0:
                    return r
                status_word = self.raw_read(STATUS_WORD_REGISTERS[subnode], subnode=subnode)
                state = self.status_word_decode(status_word)
                self.set_state(state, subnode)
        raise_err(r)

    def get_state(self, subnode=1):
        return self.__state[subnode], None

    @property
    def name(self):
        """ name: Drive name. """
        return self.__name

    @name.setter
    def name(self, new_name):
        self.__name = new_name

    @property
    def dict(self):
        """ Dictionary: Dictionary. """
        return self.__dict

    @property
    def node(self):
        """ int: Node. """
        return self.__node

    @property
    def errors(self):
        """ dict: Errors. """
        return self.__dict.errors.errors

    @property
    def info(self):
        """ dict: Servo information. """
        return self.__info

    @property
    def state(self):
        """ tuple: Servo state and state flags. """
        return self.__state

    @state.setter
    def state(self, new_state):
        self.__state = new_state

    @property
    def units_torque(self):
        """ SERVO_UNITS_TORQUE: Torque units. """
        return self.__units_torque

    @units_torque.setter
    def units_torque(self, units):
        self.__units_torque = units

    @property
    def units_pos(self):
        """ SERVO_UNITS_POS: Position units. """
        return self.__units_pos

    @units_pos.setter
    def units_pos(self, units):
        self.__units_pos = units

    @property
    def units_vel(self):
        """ SERVO_UNITS_VEL: Velocity units. """
        return self.__units_vel

    @units_vel.setter
    def units_vel(self, units):
        self.__units_vel = units

    @property
    def units_acc(self):
        """ SERVO_UNITS_ACC: Acceleration units. """
        return self.__units_acc

    @units_acc.setter
    def units_acc(self, units):
        self.__units_acc = units

    @property
    def subnodes(self):
        """ SUBNODES: Number of subnodes. """
        return self.__dict.subnodes