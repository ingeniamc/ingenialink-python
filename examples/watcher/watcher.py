import sys

from qtpy.QtCore import Qt, QTimer, Slot, QObject
from qtpy.QtGui import QStandardItemModel, QStandardItem
from qtpy.QtWidgets import (QApplication, QDialog, QFormLayout, QLabel,
                            QDataWidgetMapper, QLineEdit)

import ingenialink as il


POS_ACTUAL = il.Register(0x6064, 0x00, il.DTYPE_S32, il.ACCESS_RW, il.PHY_POS)
""" Register: actual position. """

VEL_ACTUAL = il.Register(0x606C, 0x00, il.DTYPE_S32, il.ACCESS_RW, il.PHY_VEL)
""" Register: actual velocity. """


class RegisterWatcher(QObject):
    def __init__(self, axis):
        QObject.__init__(self)

        self._axis = axis
        self._watched = {}

        self._timer = QTimer()
        self._timer.timeout.connect(self.onTimerExpired)

    @Slot()
    def onTimerExpired(self):
        for reg, cfg in self._watched.items():
            cfg['current'] += self._base_period

            if cfg['current'] >= cfg['period']:
                curr_data = str(self._axis.read(reg))
                if curr_data != cfg['item'].data():
                    cfg['item'].setData(curr_data, Qt.DisplayRole)

                cfg['current'] = 0

    def start(self, base_period):
        self._base_period = base_period
        self._timer.start(self._base_period)

    def stop(self):
        self._timer.stop()

    def add(self, reg, period, item):
        self._watched[reg] = {'period': period,
                              'item': item,
                              'current': 0}

    def remove(self, reg):
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
