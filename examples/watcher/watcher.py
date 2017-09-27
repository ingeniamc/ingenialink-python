import sys

from qtpy.QtCore import Qt, QThread, QTimer, Signal, Slot, QObject
from qtpy.QtGui import QStandardItemModel, QStandardItem
from qtpy.QtWidgets import (QApplication, QDialog, QFormLayout, QLabel,
                            QDataWidgetMapper, QLineEdit)

import ingenialink as il


POS_ACTUAL = il.Register(0x6064, 0x00, il.DTYPE_S32, il.ACCESS_RW, il.PHY_POS)
""" Register: actual position. """

VEL_ACTUAL = il.Register(0x606C, 0x00, il.DTYPE_S32, il.ACCESS_RW, il.PHY_VEL)
""" Register: actual velocity. """


class RegisterUpdater(QObject):
    """ Register updater.

        Args:
            axis (Axis): Axis instance.
            watched (dict): Dictionary of watched registers.
            base_period (int, float): Updater base period.
    """

    finished = Signal()
    """ Signal: Update finished signal. """

    def __init__(self, axis, watched, base_period):
        QObject.__init__(self)

        self._axis = axis
        self._watched = watched
        self._base_period = base_period

    @Slot()
    def update(self):
        """ Updates registers contents. """

        for reg, cfg in self._watched.items():
            cfg['current'] += self._base_period

            if cfg['current'] >= cfg['period']:
                cfg['curr_data'] = str(self._axis.read(reg))
                cfg['current'] = 0

        self.finished.emit()


class RegisterWatcher(QObject):
    """ Register watcher.

        Args:
            axis (Axis): Axis instance.
    """

    def __init__(self, axis):
        QObject.__init__(self)

        self._axis = axis

        self._watched = {}
        self._running = False

        self._timer = QTimer()
        self._timer.timeout.connect(self.onTimerExpired)

    @Slot()
    def onUpdaterFinished(self):
        """ Updates all items that changed once the updater has finished. """

        for reg, cfg in self._watched.items():
                if cfg['curr_data'] != cfg['item'].data():
                    cfg['item'].setData(cfg['curr_data'], Qt.DisplayRole)

    @Slot()
    def onTimerExpired(self):
        """ Triggers the updater on each timer expiration. """

        self._updater.update()

    def start(self, base_period):
        """ Starts the register watcher.

            Args:
                base_period (int, float): Base period.
        """

        if self._running:
            raise RuntimeError('Watcher already started')

        self._thread = QThread()
        self._updater = RegisterUpdater(self._axis, self._watched, base_period)
        self._updater.finished.connect(self.onUpdaterFinished)
        self._updater.moveToThread(self._thread)
        self._thread.start()

        self._timer.start(base_period)

        self._running = True

    def stop(self):
        """ Stops the register watcher. """

        if self._running:
            self._timer.stop()

            self._thread.exit()
            self._thread.wait()

    def add(self, reg, period, item):
        """ Adds a register to the register watcher.

            Args:
                reg (Register): Register to be watched.
                period (int, float): Update period (ms).
                item (QStandardItem): Associated item.
        """

        if self._running:
            raise RuntimeError('Cannot add a register while running')

        self._watched[reg] = {'period': period,
                              'item': item,
                              'current': 0,
                              'curr_data': ''}

    def remove(self, reg):
        """ Remove a register from the register watcher.

            Args:
                reg (Register): Register to be removed.
        """

        if self._running:
            raise RuntimeError('Cannot remove a register while running')

        del self._watching[reg]


class WatcherDialog(QDialog):
    """ Watcher Dialog. """

    _AXIS_TIMEOUT = 100
    """ int: Default axis timeout (ms). """

    _DEV = '/dev/ttyACM0'
    """ str: Default device. """

    def __init__(self):
        QDialog.__init__(self)

        # setup UI
        self.form = QFormLayout(self)
        self.editPosition = QLineEdit('')
        self.form.addRow(QLabel('Position'), self.editPosition)
        self.editVelocity = QLineEdit('')
        self.form.addRow(QLabel('Velocity'), self.editVelocity)

        # configure network (take first available axis)
        self._net = il.Network(self._DEV)
        self._axis = il.Axis(self._net, self._net.axes()[0],
                             self._AXIS_TIMEOUT)

        # create data model
        model = QStandardItemModel()
        pos = QStandardItem()
        vel = QStandardItem()
        model.appendRow([pos, vel])

        # configure and start watcher
        self._watcher = RegisterWatcher(self._axis)
        self._watcher.add(POS_ACTUAL, 500, pos)
        self._watcher.add(VEL_ACTUAL, 100, vel)
        self._watcher.start(100)

        # map model fields to widgets
        self._mapper = QDataWidgetMapper()
        self._mapper.setModel(model)
        self._mapper.addMapping(self.editPosition, 0)
        self._mapper.addMapping(self.editVelocity, 1)
        self._mapper.toFirst()

    def closeEvent(self, event):
        self._watcher.stop()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    wd = WatcherDialog()
    wd.show()

    sys.exit(app.exec_())
