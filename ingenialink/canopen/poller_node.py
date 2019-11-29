from .._utils import raise_null, raise_err, to_ms
from ._ingenialink import ffi, lib
from .registers import _get_reg_id
from .constants import *

from threading import Timer, Thread, Event


class Timer():
    def __init__(self, time, cb):
        self.cb = cb
        self.time = time
        self.thread = Timer(self.time, self.handle_function)

    def handle_function(self):
        self.cb()
        self.thread = Timer(self.time, self.handle_function)
        self.thread.start()

    def start(self):
        self.thread.start()

    def cancel(self):
        self.thread.cancel()


class Poller(object):
    """ Register poller for CANOpen communications.

        Args:
            servo (Servo): Servo.
            number_channels (int): Number of channels.

        Raises:
            ILCreationError: If the poller could not be created.
    """

    def __init__(self, servo, number_channels):
        self.__servo = servo
        self.__number_channels = number_channels
        self.__sz = 0
        self.__refresh_time = 0
        self.__timer = None
        self.__running = False
        self.__mappings = []
        self.__mappings_enabled = []
        self.reset_acq()

    def reset_acq(self):
        self.__acq = {
            "t": [],
            "d": []
        }

    def start(self):
        """ Start poller. """

        r = lib.il_poller_start(self._poller)
        raise_err(r)

    def stop(self):
        """ Stop poller. """

        lib.il_poller_stop(self._poller)

    @property
    def data(self):
        """ tuple (list, list, bool): Time vector, array of data vectors and a
            flag indicating if data was lost.
        """

        lib.il_poller_data_get(self._poller, self._acq)
        acq = ffi.cast('il_poller_acq_t *', self._acq[0])

        t = list(acq.t[0:acq.cnt])

        d = []
        for ch in range(self.__number_channels):
            if acq.d[ch] != ffi.NULL:
                d.append(list(acq.d[ch][0:acq.cnt]))
            else:
                d.append(None)

        return t, d, bool(acq.lost)

    def configure(self, t_s, sz):
        """ Configure.

            Args:
                t_s (int, float): Polling period (s).
                sz (int): Buffer size.
        """
        if self.__running:
            print("Poller is running")
            raise_err(IL_ESTATE)

        # Configure data and sizes with empty data
        self.reset_acq()
        self.__sz = sz
        self.__refresh_time = to_ms(t_s)
        self.__acq['t'] = [0] * sz
        for channel in range(0, self.__number_channels):
            data_channel = [0] * sz
            self.__acq['d'].append(data_channel)
            self.__mappings.append('')
            self.__mappings_enabled.append(False)

        return 0

    def ch_configure(self, channel, reg):
        """ Configure a poller channel mapping.

            Args:
                channel (int): Channel to be configured.
                reg (Register): Register to associate to the given channel.

            Raises:
                TypeError: If the register is not valid.
        """

        if self.__running:
            print("Poller is running")
            raise_err(IL_ESTATE)

        if channel > self.__number_channels:
            print("Channel out of range")
            raise_err(IL_EINVAL)

        # Obtain register
        _reg = self.__servo.get_reg(reg)

        # Reg identifier obtained and set enabled
        self.__mappings[channel] = _reg.identifier
        self.__mappings_enabled[channel] = True

        return 0

    def ch_disable(self, ch):
        """ Disable a channel.

            Args:
                ch (int): Channel to be disabled.
        """

        r = lib.il_poller_ch_disable(self._poller, ch)
        raise_err(r)

    def ch_disable_all(self):
        """ Disable all channels. """

        r = lib.il_poller_ch_disable_all(self._poller)
        raise_err(r)
