from ..net import Network, NET_PROT, NET_TRANS_PROT
from ..servo import Servo, SERVO_MODE, SERVO_STATE, SERVO_UNITS_ACC, \
    SERVO_UNITS_TORQUE, SERVO_UNITS_POS, SERVO_UNITS_VEL
from ..registers import *
from ..const import *
from ..exceptions import *
from ..dict_ import Dictionary
from ingenialink.utils._utils import *
from .._ingenialink import lib, ffi

import xml.etree.ElementTree as ET
from xml.dom import minidom
import io

import ingenialogger
logger = ingenialogger.get_logger(__name__)


class EthercatServo(Servo):
    def __init__(self, net, target, dictionary_path):
        super(EthercatServo, self).__init__(net, target)
        self._dictionary = cstr(dictionary_path) if dictionary_path else ffi.NULL
        self.__servo_interface = ffi.new('il_servo_t **')
        self.__net = net

        self._state_cb = {}
        self._emcy_cb = {}

        if not hasattr(self, '_errors') or not self._errors:
            self._errors = self._get_all_errors(self._dictionary)

    @classmethod
    def _from_existing(cls, servo, dictionary):
        """ Create a new class instance from an existing servo.

        Args:
            servo (Servo): Servo instance.
            dictionary (str): Path to the dictionary file.

        Returns:
            Servo: Instance of servo.

        """
        inst = cls.__new__(cls)
        inst.__servo_interface = ffi.gc(servo, lib.il_servo_fake_destroy)

        inst._state_cb = {}
        inst._emcy_cb = {}
        if not hasattr(inst, '_errors') or not inst._errors:
            inst._errors = inst._get_all_errors(dictionary)

        return inst

    def _get_all_errors(self, dictionary):
        """ Obtain all errors defined in the dictionary.

        Args:
            dictionary: Path to the dictionary file.

        Returns:
            dict: Current errors definde in the dictionary.
        """
        errors = dict()
        if str(dictionary) != "<cdata 'void *' NULL>":
            tree = ET.parse(dictionary)
            for error in tree.iter("Error"):
                label = error.find(".//Label")
                id = int(error.attrib['id'], 0)
                errors[id] = [
                    error.attrib['id'],
                    error.attrib['affected_module'],
                    error.attrib['error_type'].capitalize(),
                    label.text
                ]
        return errors

    def get_reg(self, reg, subnode):
        """ Obtain Register object and its identifier.

        Args:
            reg (Register, str): Register.
            subnode (int): Subnode.

        Returns:
            tuple (Register, string): Actual Register instance and its
                                        identifier.
        """
        _reg = ffi.NULL
        _id = ffi.NULL
        if isinstance(reg, Register):
            _reg = reg._reg
        elif isinstance(reg, str):
            _dict = self.dictionary
            if not _dict:
                raise ValueError('No dictionary loaded')
            if reg not in _dict.get_regs(subnode):
                raise_err(lib.IL_REGNOTFOUND, 'Register not found ({})'.format(reg))
            _reg = _dict.get_regs(subnode)[reg]._reg
        else:
            raise TypeError('Invalid register')
        return _reg, _id

    def raw_read(self, reg, subnode=1):
        """ Raw read from servo.

        Args:
            reg (Register): Register.

        Returns:
            int: Otained value

        Raises:
            TypeError: If the register type is not valid.
        """
        return self.read(reg, subnode=subnode)

    def read(self, reg, subnode=1):
        """ Read from servo.

        Args:
            reg (str, Register): Register.

        Returns:
            float: Obtained value

        Raises:
            TypeError: If the register type is not valid.
        """
        if isinstance(reg, Register):
            _reg = reg
        elif isinstance(reg, str):
            _dict = self.dictionary
            if not _dict:
                raise ValueError('No dictionary loaded')
            if reg not in _dict.get_regs(subnode):
                raise_err(lib.IL_REGNOTFOUND, 'Register not found ({})'.format(reg))
            _reg = _dict.get_regs(subnode)[reg]
        else:
            raise TypeError('Invalid register')

        # Obtain data pointer and function to call
        t, f = self._raw_read[_reg.dtype]
        v = ffi.new(t)

        r = f(self.__servo_interface, _reg._reg, ffi.NULL, v)
        raise_err(r)

        try:
            if self.dictionary:
                _reg = self.dictionary.get_regs(subnode)[reg]
        except Exception as e:
            pass
        if _reg.dtype == REG_DTYPE.STR:
            value = self.__net.extended_buffer
        else:
            value = v[0]

        if isinstance(value, str):
            value = value.replace('\x00', '')
        return value

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
        self.write(reg, data, confirm, extended, subnode)

    def write(self, reg, data, confirm=True, extended=0, subnode=1):
        """ Write to servo.

        Args:
            reg (Register): Register.
            data (int): Data.
            confirm (bool, optional): Confirm write.
            extended (int, optional): Extended frame.

        Raises:
            TypeError: If any of the arguments type is not valid or
                unsupported.
        """
        if isinstance(reg, Register):
            _reg = reg
        elif isinstance(reg, str):
            _dict = self.dictionary
            if not _dict:
                raise ValueError('No dictionary loaded')
            if reg not in _dict.get_regs(subnode):
                raise_err(lib.IL_REGNOTFOUND, 'Register not found ({})'.format(reg))
            _reg = _dict.get_regs(subnode)[reg]
        else:
            raise TypeError('Invalid register')

        # Auto cast floats if register is not float
        if isinstance(data, float) and _reg.dtype != REG_DTYPE.FLOAT:
            data = int(data)

        # Obtain function to call
        f = self._raw_write[_reg.dtype]

        r = f(self.__servo_interface, _reg._reg, ffi.NULL, data, confirm, extended)
        raise_err(r)

    def destroy(self):
        """ Destroy servo instance.

        Returns:
            int: Result code.
        """
        r = lib.il_servo_destroy(self.__servo_interface)
        return r

    def reset(self):
        """ Reset servo.

        Notes:
            You may need to reconnect the network after reset.
        """
        r = lib.il_servo_reset(self.__servo_interface)
        raise_err(r)

    def get_state(self, subnode=1):
        """ Obtain state of the servo.

        Args:
            subnode (int, optional): Subnode.

        Returns:
            tuple: Servo state and state flags.
        """
        state = ffi.new('il_servo_state_t *')
        flags = ffi.new('int *')

        lib.il_servo_state_get(self.__servo_interface, state, flags, subnode)

        return SERVO_STATE(state[0]), flags[0]

    def state_subs_stop(self, stop):
        """ Stop servo state subscriptions.

        Args:
            stop (int): start: 0, stop: 1.

        Returns:
            int: Result code.
        """
        return lib.il_servo_state_subs_stop(self.__servo_interface, stop)

    def enable(self, timeout=2., subnode=1):
        """ Enable PDS.

        Args:
            timeout (int, float, optional): Timeout (s).
            subnode (int, optional): Subnode.
        """
        r = lib.il_servo_enable(self.__servo_interface, to_ms(timeout), subnode)
        raise_err(r)

    def disable(self, subnode=1):
        """ Disable PDS. """
        r = lib.il_servo_disable(self.__servo_interface, subnode)
        raise_err(r)

    def fault_reset(self, subnode=1):
        """ Fault reset.

        Args:
            subnode (int, optional): Subnode.
        """
        r = lib.il_servo_fault_reset(self.__servo_interface, subnode)
        raise_err(r)

    def switch_on(self, timeout=2.):
        """ Switch on PDS.

        This function switches on the PDS but it does not enable the motor.
        For most application cases, you should only use the `enable`
        function.

        Args:
            timeout (int, float, optional): Timeout (s).
        """
        r = lib.il_servo_switch_on(self.__servo_interface, to_ms(timeout))
        raise_err(r)

    def homing_start(self):
        """ Start the homing procedure. """
        r = lib.il_servo_homing_start(self.__servo_interface)
        raise_err(r)

    def homing_wait(self, timeout):
        """ Wait until homing completes.

        Notes:
            The homing itself has a configurable timeout. The timeout given
            here is purely a 'communications' timeout, e.g. it could happen
            that the statusword change is never received. This timeout
            should be >= than the programmed homing timeout.

        Args:
            timeout (int, float): Timeout (s).
        """
        r = lib.il_servo_homing_wait(self.__servo_interface, to_ms(timeout))
        raise_err(r)

    def store_parameters(self, subnode=1):
        """ Store all the current parameters of the target subnode.

        Args:
            subnode (int): Subnode of the axis.

        Raises:
            ILError: Invalid subnode.
            ILObjectNotExist: Failed to write to the registers.
        """
        if subnode == 0:
            # Store all
            r = 0
            try:
                self.write(reg=STORE_COCO_ALL,
                           data=PASSWORD_STORE_ALL,
                           subnode=subnode)
                logger.info('Store all successfully done.')
            except Exception as e:
                logger.warning('Store all COCO failed. Trying MOCO...')
                r = -1
            if r < 0:
                if self._dictionary.subnodes > SINGLE_AXIS_MINIMUM_SUBNODES:
                    # Multiaxis
                    for dict_subnode in self._dictionary.subnodes:
                        self.write(reg=STORE_MOCO_ALL_REGISTERS[dict_subnode],
                                   data=PASSWORD_STORE_ALL,
                                   subnode=dict_subnode)
                        logger.info('Store axis {} successfully done.'.format(
                            dict_subnode))
                else:
                    # Single axis
                    self.write(reg=STORE_MOCO_ALL_REGISTERS[1],
                               data=PASSWORD_STORE_ALL,
                               subnode=1)
                    logger.info('Store all successfully done.')
        elif subnode > 0:
            # Store axis
            self.write(reg=STORE_MOCO_ALL_REGISTERS[subnode],
                       data=PASSWORD_STORE_ALL,
                       subnode=subnode)
            logger.info('Store axis {} successfully done.'.format(subnode))
        else:
            raise ILError('Invalid subnode.')

    def restore_parameters(self):
        """ Restore all the current parameters of all the slave to default.

        Raises:
            ILError: Invalid subnode.
            ILObjectNotExist: Failed to write to the registers.
        """
        self.write(reg=RESTORE_COCO_ALL,
                   data=PASSWORD_RESTORE_ALL,
                   subnode=0)
        logger.info('Restore all successfully done.')

    def store_comm(self):
        """ Store all servo current communications to the NVM. """
        r = lib.il_servo_store_comm(self.__servo_interface)
        raise_err(r)

    def store_app(self):
        """ Store all servo current application parameters to the NVM. """
        r = lib.il_servo_store_app(self.__servo_interface)
        raise_err(r)

    def _dict_load(self, dictionary):
        """ Load dictionary.

        Args:
            dictionary (str): Dictionary.
        """
        r = lib.il_servo_dict_load(self.__servo_interface, cstr(dictionary))
        if not hasattr(self, '_errors') or not self._errors:
            self._errors = self._get_all_errors(dictionary)
        raise_err(r)

    def load_configuration(self, dictionary, subnode=0):
        """ Load configuration from dictionary file to the servo drive.

        Args:
            dictionary (str): Dictionary.
            subnode (int, optional): Subnode.

        """
        r = lib.il_servo_dict_storage_write(self.__servo_interface, cstr(dictionary),
                                            subnode)
        if not hasattr(self, '_errors') or not self._errors:
            self._errors = self._get_all_errors(dictionary)
        raise_err(r)
        return r

    def save_configuration(self, new_path, subnode=0):
        """ Read all dictionary registers content and save it to a
            new dictionary.

        Args:
            new_path (str): Dictionary.

        """
        prod_code, rev_number = get_drive_identification(self, subnode)

        r = lib.il_servo_dict_storage_read(self.__servo_interface)
        raise_err(r)

        self.dictionary.save(new_path)

        tree = ET.parse(new_path)
        xml_data = tree.getroot()

        body = xml_data.find('Body')
        device = xml_data.find('Body/Device')
        categories = xml_data.find('Body/Device/Categories')
        errors = xml_data.find('Body/Errors')

        if 'ProductCode' in device.attrib and prod_code is not None:
            device.attrib['ProductCode'] = str(prod_code)
        if 'RevisionNumber' in device.attrib and rev_number is not None:
            device.attrib['RevisionNumber'] = str(rev_number)

        registers_category = xml_data.find('Body/Device/Registers')
        registers = xml_data.findall('Body/Device/Registers/Register')
        if registers_category is None:
            registers_category = xml_data.find(
                'Body/Device/Axes/Axis/Registers')
            registers = xml_data.findall(
                'Body/Device/Axes/Axis/Registers/Register')

        for register in registers:
            if register.attrib['subnode'] != str(
                    subnode) and subnode > 0 and register in registers_category:
                registers_category.remove(register)
            cleanup_register(register)

        device.remove(categories)
        body.remove(errors)

        image = xml_data.find('./DriveImage')
        if image is not None:
            xml_data.remove(image)

        xmlstr = minidom.parseString(ET.tostring(xml_data)).toprettyxml(
            indent="  ", newl='')

        config_file = io.open(new_path, "w", encoding='utf8')
        config_file.write(xmlstr)
        config_file.close()

        return r

    def reload_errors(self, dictionary):
        """ Force to reload all dictionary errors.

        Args:
            dictionary (str): Dictionary.
        """
        self._errors = self._get_all_errors(dictionary)

    def emcy_subscribe(self, cb):
        """ Subscribe to emergency messages.

        Args:
            cb: Callback

        Returns:
            int: Assigned slot.
        """
        cb_handle = ffi.new_handle(cb)

        slot = lib.il_servo_emcy_subscribe(
            self.__servo_interface, lib._on_emcy_cb, cb_handle)
        if slot < 0:
            raise_err(slot)

        self._emcy_cb[slot] = cb_handle

        return slot

    def emcy_unsubscribe(self, slot):
        """ Unsubscribe from emergency messages.

        Args:
            slot (int): Assigned slot when subscribed.
        """
        lib.il_servo_emcy_unsubscribe(self.__servo_interface, slot)

        del self._emcy_cb[slot]

    def subscribe_to_servo_status(self, cb):
        """ Subscribe to state changes.

        Args:
            cb: Callback

        Returns:
            int: Assigned slot.
        """
        cb_handle = ffi.new_handle(cb)

        slot = lib.il_servo_state_subscribe(
            self.__servo_interface, lib._on_state_change_cb, cb_handle)
        if slot < 0:
            raise_err(slot)

        self._state_cb[slot] = cb_handle

        return slot

    def unsubscribe_to_servo_status(self, slot):
        """ Unsubscribe from state changes.

        Args:
            slot (int): Assigned slot when subscribed.
        """
        lib.il_servo_state_unsubscribe(self.__servo_interface, slot)

        del self._state_cb[slot]

    def disturbance_write_data(self, channels, dtypes, data_arr):
        """ Write disturbance data.

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
        sample_size = 0
        for dtype_val in dtypes:
            sample_size += dtype_size(dtype_val)
        samples_for_write = DIST_FRAME_SIZE // sample_size
        number_writes = num_samples // samples_for_write
        rest_samples = num_samples % samples_for_write
        for i in range(number_writes):
            for index, channel in enumerate(channels):
                self.net.disturbance_channel_data(
                    channel,
                    dtypes[index],
                    data_arr[index][i * samples_for_write:(i + 1) * samples_for_write])
            self.net.disturbance_data_size = sample_size * samples_for_write
            self.write(DIST_DATA, sample_size * samples_for_write, False, 1, subnode=0)
        for index, channel in enumerate(channels):
            self.net.disturbance_channel_data(
                channel,
                dtypes[index],
                data_arr[index][number_writes * samples_for_write:num_samples])
        self.net.disturbance_data_size = rest_samples * sample_size
        self.write(DIST_DATA, rest_samples * sample_size, False, 1, subnode=0)

    def wait_reached(self, timeout):
        """ Wait until the servo does a target reach.

        Args:
            timeout (int, float): Timeout (s).
        """
        r = lib.il_servo_wait_reached(self.__servo_interface, to_ms(timeout))
        raise_err(r)

    def units_update(self):
        """ Update units scaling factors.

        Notes:
            This must be called if any encoder parameter, rated torque or
            pole pitch are changed, otherwise, the readings conversions
            will not be correct.
        """
        r = lib.il_servo_units_update(self.__servo_interface)
        raise_err(r)

    def units_factor(self, reg):
        """ Obtain units scale factor for the given register.

        Args:
            reg (Register): Register.

        Returns:
            float: Scale factor for the given register.
        """
        return lib.il_servo_units_factor(self.__servo_interface, reg._reg)

    @property
    def net(self):
        """ Obtain servo network.

        Returns:
            Network: Current servo network.
        """
        return self.__net

    @net.setter
    def net(self, value):
        """ Set servo network.

        Args:
            value (Network): Network to be setted as servo Network.
        """
        self.__net = value

    @property
    def name(self):
        """ Obtain servo name.

        Returns:
            str: Name.
        """
        name = ffi.new('char []', lib.IL_SERVO_NAME_SZ)

        r = lib.il_servo_name_get(self.__servo_interface, name, ffi.sizeof(name))
        raise_err(r)

        return pstr(name)

    @name.setter
    def name(self, name):
        """ Set servo name.

        Args:
            name (str): Name.
        """
        name_ = ffi.new('char []', cstr(name))

        r = lib.il_servo_name_set(self.__servo_interface, name_)
        raise_err(r)

    @property
    def dictionary(self):
        """ Obtain dictionary of the servo. """
        _dict = lib.il_servo_dict_get(self.servo_interface)

        return Dictionary._from_dict(_dict) if _dict else None

    @dictionary.setter
    def dictionary(self, value):
        self._dictionary = value

    @property
    def info(self):
        """ Obtain servo information.

        Returns:
            dict: Servo information.
        """
        info = ffi.new('il_servo_info_t *')

        r = lib.il_servo_info_get(self.__servo_interface, info)
        raise_err(r)

        PRODUCT_ID_REG = Register(identifier='', address=0x06E1,
                                  dtype=REG_DTYPE.U32,
                                  access=REG_ACCESS.RO, cyclic='CONFIG',
                                  units='0')

        product_id = self.read(PRODUCT_ID_REG)

        return {'serial': info.serial,
                'name': pstr(info.name),
                'sw_version': pstr(info.sw_version),
                'hw_variant': pstr(info.hw_variant),
                'prod_code': product_id,
                'revision': info.revision}

    @property
    def units_torque(self):
        """ SERVO_UNITS_TORQUE: Torque units. """
        return SERVO_UNITS_TORQUE(lib.il_servo_units_torque_get(self.__servo_interface))

    @units_torque.setter
    def units_torque(self, units):
        lib.il_servo_units_torque_set(self.__servo_interface, units.value)

    @property
    def units_pos(self):
        """ SERVO_UNITS_POS: Position units. """
        return SERVO_UNITS_POS(lib.il_servo_units_pos_get(self.__servo_interface))

    @units_pos.setter
    def units_pos(self, units):
        lib.il_servo_units_pos_set(self.__servo_interface, units.value)

    @property
    def units_vel(self):
        """ SERVO_UNITS_VEL: Velocity units. """
        return SERVO_UNITS_VEL(lib.il_servo_units_vel_get(self.__servo_interface))

    @units_vel.setter
    def units_vel(self, units):
        lib.il_servo_units_vel_set(self.__servo_interface, units.value)

    @property
    def units_acc(self):
        """ SERVO_UNITS_ACC: Acceleration units. """
        return SERVO_UNITS_ACC(lib.il_servo_units_acc_get(self.__servo_interface))

    @units_acc.setter
    def units_acc(self, units):
        lib.il_servo_units_acc_set(self.__servo_interface, units.value)

    @property
    def mode(self):
        """ Obtains Operation mode.

        Returns:
            SERVO_MODE: Current operation mode.
        """
        mode = ffi.new('il_servo_mode_t *')

        r = lib.il_servo_mode_get(self.__servo_interface, mode)
        raise_err(r)

        return SERVO_MODE(mode[0])

    @mode.setter
    def mode(self, mode):
        """ Set Operation mode.

        Args:
            mode (SERVO_MODE): Operation mode.
        """
        r = lib.il_servo_mode_set(self.__servo_interface, mode.value)
        raise_err(r)

    @property
    def errors(self):
        """ Obtain drive errors.

        Returns:
            dict: Current errors.
        """
        return self._errors

    @property
    def servo_interface(self):
        """ Obtain servo interface. """
        return self.__servo_interface

    @servo_interface.setter
    def servo_interface(self, value):
        """ Set servo interface. """
        self.__servo_interface = value

    @property
    def subnodes(self):
        """ Obtain number of subnodes.

        Returns:
            int: Current number of subnodes.
        """
        return int(ffi.cast('int', lib.il_servo_subnodes_get(self.__servo_interface)))

    @property
    def ol_voltage(self):
        """ Get open loop voltage.

        Returns:
            float: Open loop voltage (% relative to DC-bus, -1...1).
        """
        voltage = ffi.new('double *')
        r = lib.il_servo_ol_voltage_get(self.__servo_interface, voltage)
        raise_err(r)

        return voltage[0]

    @ol_voltage.setter
    def ol_voltage(self, voltage):
        """ Set the open loop voltage (% relative to DC-bus, -1...1).

        Args:
            float: Open loop voltage.
        """
        r = lib.il_servo_ol_voltage_set(self.__servo_interface, voltage)
        raise_err(r)

    @property
    def ol_frequency(self):
        """ Get open loop frequency.

        Returns:
            float: Open loop frequency (mHz).
        """
        frequency = ffi.new('double *')
        r = lib.il_servo_ol_frequency_get(self.__servo_interface, frequency)
        raise_err(r)

        return frequency[0]

    @ol_frequency.setter
    def ol_frequency(self, frequency):
        """ Set the open loop frequency (mHz).

        Args:
            float: Open loop frequency.
        """
        r = lib.il_servo_ol_frequency_set(self.__servo_interface, frequency)
        raise_err(r)

    @property
    def torque(self):
        """ Get actual torque.

        Returns:
            float: Actual torque.
        """
        torque = ffi.new('double *')
        r = lib.il_servo_torque_get(self.__servo_interface, torque)
        raise_err(r)

        return torque[0]

    @torque.setter
    def torque(self, torque):
        """ Set the target torque.

        Args:
            float: Target torque.
        """
        r = lib.il_servo_torque_set(self.__servo_interface, torque)
        raise_err(r)

    @property
    def position(self):
        """ Get actual position.

        Returns:
            float: Actual position.
        """
        position = ffi.new('double *')
        r = lib.il_servo_position_get(self.__servo_interface, position)
        raise_err(r)

        return position[0]

    @position.setter
    def position(self, pos):
        """ Set the target position.

        Notes:
            Position can be either a single position, or a tuple/list
            containing in the first position the position, and in the
            second a dictionary with the following options:

                - immediate (bool): If True, the servo will go to the
                  position immediately, otherwise it will push the position
                  to the buffer. Defaults to True.
                - relative (bool): If True, the position will be taken as
                  relative, otherwise it will be taken as absolute.
                  Defaults to False.
                - sp_timeout (int, float): Set-point acknowledge
                  timeout (s).

        Args:
            pos (float): Target position.
        """
        immediate = 1
        relative = 0
        sp_timeout = lib.IL_SERVO_SP_TIMEOUT_DEF

        if isinstance(pos, (tuple, list)):
            if len(pos) != 2 or not isinstance(pos[1], dict):
                raise TypeError('Unexpected position')

            if 'immediate' in pos[1]:
                immediate = int(pos[1]['immediate'])

            if 'relative' in pos[1]:
                relative = int(pos[1]['relative'])

            if 'sp_timeout' in pos[1]:
                sp_timeout = to_ms(pos[1]['sp_timeout'])

            pos = pos[0]

        r = lib.il_servo_position_set(self.__servo_interface, pos, immediate, relative,
                                      sp_timeout)
        raise_err(r)

    @property
    def position_res(self):
        """ Get position resolution.

        Returns:
            int: Position resolution (c/rev/s, c/ppitch/s).
        """
        res = ffi.new('uint32_t *')
        r = lib.il_servo_position_res_get(self.__servo_interface, res)
        raise_err(r)

        return res[0]

    @property
    def velocity(self):
        """ Get actual velocity.

        Returns:
            float: Actual velocity.
        """
        velocity = ffi.new('double *')
        r = lib.il_servo_velocity_get(self.__servo_interface, velocity)
        raise_err(r)

        return velocity[0]

    @velocity.setter
    def velocity(self, velocity):
        """ Set the target velocity.

        Args:
            velocity (float): Target velocity.
        """
        r = lib.il_servo_velocity_set(self.__servo_interface, velocity)
        raise_err(r)

    @property
    def velocity_res(self):
        """ Get velocity resolution.

        Returns:
            int: Velocity resolution (c/rev, c/ppitch).
        """
        res = ffi.new('uint32_t *')
        r = lib.il_servo_velocity_res_get(self.__servo_interface, res)
        raise_err(r)

        return res[0]

