import sys

from qtpy.QtCore import Qt, QThread, QTimer, Signal, Slot, QObject
from qtpy.QtGui import QStandardItemModel, QStandardItem
from qtpy.QtWidgets import (QApplication, QDialog, QFormLayout, QLabel,
                            QDataWidgetMapper, QLineEdit)

import ingenialink as il


POS_ACT = il.IPBRegister(address=0x0030,
                         identifier="CL_POS_FBK_VALUE",
                         dtype=il.REG_DTYPE.S32,
                         access=il.REG_ACCESS.RW,
                         phy=il.REG_PHY.POS,
                         units="",
                         cyclic="")
"""Register: Position Actual."""


VEL_ACT = il.IPBRegister(address=0x0031,
                         identifier="CL_VEL_FBK_VALUE",
                         dtype=il.REG_DTYPE.S32,
                         access=il.REG_ACCESS.RW,
                         phy=il.REG_PHY.VEL,
                         units="",
                         cyclic="")

"""Register: Velocity Actual."""


class RegisterUpdater(QObject):
    """Register updater.

        Args:
            servo (Servo): Servo instance.
            watched (dict): Dictionary of watched registers.
            base_period (int, float): Updater base period.
    """

    finished = Signal()
    """Signal: Update finished signal."""

    def __init__(self, servo, watched, base_period):
        QObject.__init__(self)

        self._servo = servo
        self._watched = watched
        self._base_period = base_period

    @Slot()
    def update(self):
        """Updates registers contents."""

        for reg, cfg in self._watched.items():
            cfg['current'] += self._base_period

            if cfg['current'] >= cfg['period']:
                try:
                    cfg['curr_data'] = self._servo.read(reg.identifier)
                except:
                    pass
                cfg['current'] = 0

        self.finished.emit()


class RegisterWatcher(QObject):
    """Register watcher.

        Args:
            servo (Servo): Servo instance.
    """

    def __init__(self, servo):
        QObject.__init__(self)

        self._servo = servo

        self._watched = {}
        self._running = False

        self._timer = QTimer()
        self._timer.timeout.connect(self.onTimerExpired)

    @Slot()
    def onUpdaterFinished(self):
        """Updates all items that changed once the updater has finished."""

        for reg, cfg in self._watched.items():
                if cfg['curr_data'] != cfg['item'].data():
                    cfg['item'].setData(cfg['curr_data'], Qt.DisplayRole)

    @Slot()
    def onTimerExpired(self):
        """Triggers the updater on each timer expiration."""

        self._thread = QThread()
        self._updater = RegisterUpdater(self._servo, self._watched,
                                        self._base_period)
        self._updater.moveToThread(self._thread)
        self._thread.started.connect(self._updater.update)
        self._updater.finished.connect(self.onUpdaterFinished)
        self._updater.finished.connect(self._thread.quit)
        self._updater.finished.connect(self._updater.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def start(self, base_period):
        """Starts the register watcher.

            Args:
                base_period (int, float): Base period.
        """

        if self._running:
            raise RuntimeError('Watcher already started')

        self._base_period = 100
        self._timer.start(self._base_period)

        self._running = True

    def stop(self):
        """Stops the register watcher."""

        if self._running:
            self._timer.stop()
            self._running = False

    def add(self, reg, period, item):
        """Adds a register to the register watcher.

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
        """Remove a register from the register watcher.

            Args:
                reg (Register): Register to be removed.
        """

        if self._running:
            raise RuntimeError('Cannot remove a register while running')

        del self._watching[reg]


class WatcherDialog(QDialog):
    """Watcher Dialog."""

    def __init__(self):
        QDialog.__init__(self)

        # setup UI
        self.form = QFormLayout(self)
        self.editPosition = QLineEdit('')
        self.form.addRow(QLabel('Position'), self.editPosition)
        self.editVelocity = QLineEdit('')
        self.form.addRow(QLabel('Velocity'), self.editVelocity)

        # configure network (take first available servo)
        self._net, self._servo = il.lucky(
            il.NET_PROT.ETH,
            "../../resources/dictionaries/eve-net_1.7.1.xdf",
            address_ip='192.168.2.22',
            port_ip=1061,
            protocol=2)

        # create data model
        model = QStandardItemModel()
        pos = QStandardItem()
        vel = QStandardItem()
        model.appendRow([pos, vel])

        # configure and start watcher
        self._watcher = RegisterWatcher(self._servo)
        self._watcher.add(POS_ACT, 1000, pos)
        self._watcher.add(VEL_ACT, 1000, vel)
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
