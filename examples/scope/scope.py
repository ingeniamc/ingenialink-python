import sys
from os.path import join, dirname, abspath

from qtpy import uic
from qtpy.QtCore import Qt, QObject, QTimer, Signal, Slot, QThread
from qtpy.QtGui import (QStandardItemModel, QStandardItem, QImage, QPixmap,
                        QPalette)
from qtpy.QtWidgets import QApplication, QMainWindow

import qtawesome as qta
import qtmodern.styles
import qtmodern.windows

import numpy as np
import ingenialink as il

from enum import IntEnum


_RESOURCES = join(dirname(abspath(__file__)), 'resources')
""" str: Resources folder. """


POS_ACT = il.Register(address=0x0030,
                      identifier="POSITION_ACTUAL",
                      dtype=il.REG_DTYPE.S32,
                      access=il.REG_ACCESS.RW,
                      phy=il.REG_PHY.POS,
                      units="",
                      cyclic="")
""" Register: Position Actual. """

VEL_ACT = il.Register(address=0x0031,
                      identifier="VELOCITY_ACTUAL",
                      dtype=il.REG_DTYPE.S32,
                      access=il.REG_ACCESS.RW,
                      phy=il.REG_PHY.VEL,
                      units="",
                      cyclic="")
""" Register: Velocity Actual. """

class SERVO_MODE(IntEnum):
    """ Operation Mode. """
    VOLTAGE = 0,
    VELOCITY = 3,
    CYCLIC_VELOCITY = 35,
    PROFILE_VELOCITY = 19,
    POSITION = 4,
    CYCLIC_POSITION = 36,
    PROFILE_POSITION = 20,
    PROFILE_POSITION_S_CURVE = 68

class ScopeWindow(QMainWindow):
    """ Scope Window. """

    _FPS = 30
    """ int: Plot refresh rate (fps). """

    _N_SAMPLES = 1000
    """ int: Number of samples. """

    _POLLER_T_S = 10e-3
    """ float: Poller sampling period (s). """

    _POLLER_BUF_SZ = 100
    """ int: Poller buffer size. """

    _PRANGE = 360
    """ int: Position range (+/-) deg. """

    _VRANGE = 40
    """ int: Velocity range (+/-) rps. """

    _ENABLE_TIMEOUT = 2
    """ int: Enable timeout (s). """

    stateInit, stateIdle, statePosition, stateVelocity = range(4)
    """ States. """

    tabPositionIndex, tabVelocityIndex = range(2)
    """ Motion control tabs. """

    def __init__(self):
        QMainWindow.__init__(self)

        self.setState(self.stateInit)
        self.setState(self.stateIdle)

        self._timerPlotUpdate = QTimer()
        self._timerPlotUpdate.timeout.connect(self.on_timerPlotUpdate_expired)

        self._enabled = False

        # TODO: should be done asynchronously!
        self.loadServos()

    def loadServos(self):
        model = QStandardItemModel()

        net, servo = il.lucky(il.NET_PROT.ETH,
                              "resources/eve-net_1.7.1.xdf",
                              address_ip='192.168.2.22',
                              port_ip=1061,
                              protocol=2)

        if net is not None and servo is not None:
            item = QStandardItem('0x{:02x} ({})'.format(1, "Everest"))
            item.setData(servo, Qt.UserRole)

            image = QImage(join(_RESOURCES, 'images', 'eve-xcr.png'))
            item.setData(QPixmap.fromImage(image), Qt.DecorationRole)

            model.appendRow([item])

            self.cboxServos.setModel(model)

    def setState(self, state):
        if state == self.stateInit:
            uic.loadUi(join(_RESOURCES, 'ui', 'scopewindow.ui'), self)

            self.splitter.setStretchFactor(0, 1)
            self.splitter.setStretchFactor(1, 0)

            self.tabsMotionControl.setCurrentIndex(self.tabPositionIndex)

            palette = QApplication.instance().palette()
            iconsColor = palette.color(QPalette.Text)

            self.tabsMotionControl.setTabIcon(
                    self.tabPositionIndex,
                    qta.icon('fa.arrows', color=iconsColor))
            self.tabsMotionControl.setTabIcon(
                    self.tabVelocityIndex,
                    qta.icon('fa.tachometer', color=iconsColor))

            self.dialPosition.setMinimum(-self._PRANGE)
            self.dialPosition.setMaximum(self._PRANGE)
            self.dialPosition.setValue(0)

            self.dialVelocity.setMinimum(-self._VRANGE)
            self.dialVelocity.setMaximum(self._VRANGE)
            self.dialVelocity.setValue(0)

            self.scope.setBackground(None)

            self._plot = self.scope.getPlotItem()
            self._plot.enableAutoRange('y', False)
            self._plot.enableAutoRange('x', True)
            self._plot.setDownsampling(mode='peak')
            self._plot.setClipToView(True)
            self._plot.setLabel('bottom', 'Time', 's')
            self._plot.setLabel('left', 'Position', 'deg')
            self._plot.setRange(yRange=[-(self._PRANGE + 10),
                                        self._PRANGE + 10])
            self._plot.showGrid(x=True, y=True)

            self._curve = self.scope.getPlotItem().plot()
            self._curve.setPen(color='y', width=2)

        elif state == self.stateIdle:
            self.cboxServos.setEnabled(True)

            self.tabPosition.setEnabled(True)
            self.dialPosition.setEnabled(False)
            self.btnPosition.setText('Enable')

            self.tabVelocity.setEnabled(True)
            self.dialVelocity.setEnabled(False)
            self.btnVelocity.setText('Enable')

        elif state == self.statePosition:
            self._plot.setLabel('left', 'Position', 'deg')
            self._plot.setRange(yRange=[-(self._PRANGE + 10),
                                        self._PRANGE + 10])

            self.cboxServos.setEnabled(False)

            self.tabVelocity.setEnabled(False)

            self.btnPosition.setText('Disable')
            self.dialPosition.setEnabled(True)

        elif state == self.stateVelocity:
            self._plot.setLabel('left', 'Velocity', 'rps')
            self._plot.setRange(yRange=[-(self._VRANGE + 10),
                                        self._VRANGE + 10])

            self.cboxServos.setEnabled(False)

            self.tabPosition.setEnabled(False)

            self.btnVelocity.setText('Disable')
            self.dialVelocity.setEnabled(True)

        self._state = state

    def currentServo(self):
        index = self.cboxServos.model().index(self.cboxServos.currentIndex(), 0)
        servo = self.cboxServos.model().data(index, Qt.UserRole)

        return servo

    def enableScope(self, servo, reg):
        self._poller = il.poller.Poller(servo, 1)
        self._poller.configure(self._POLLER_T_S, self._POLLER_BUF_SZ)
        self._poller.ch_configure(0, reg)

        self._data = np.zeros(self._N_SAMPLES)
        self._time = np.arange(-self._N_SAMPLES * self._POLLER_T_S, 0,
                               self._POLLER_T_S)

        self._timerPlotUpdate.start(1000 / self._FPS)

        self._poller.start()

    def disableScope(self):
        self._poller.stop()
        self._timerPlotUpdate.stop()

    @Slot()
    def on_btnPosition_clicked(self):
        servo = self.currentServo()

        if self._state == self.stateIdle:
            servo.raw_write("DRV_OP_CMD", 20)  # Profile Position
            servo.enable(self._ENABLE_TIMEOUT)

            self.enableScope(servo, POS_ACT)
            self.setState(self.statePosition)
        else:
            self.disableScope()
            servo.disable()

            self.setState(self.stateIdle)

    @Slot(int)
    def on_dialPosition_valueChanged(self, value):
        self.currentServo().raw_write("CL_POS_SET_POINT_VALUE", value)

    @Slot()
    def on_btnVelocity_clicked(self):
        servo = self.currentServo()

        if self._state == self.stateIdle:
            servo.raw_write("DRV_OP_CMD", 19)   # Profile Velocity
            servo.enable(self._ENABLE_TIMEOUT)

            self.enableScope(servo, VEL_ACT)
            self.setState(self.stateVelocity)
        else:
            self.disableScope()
            servo.disable()

            self.setState(self.stateIdle)

    @Slot(int)
    def on_dialVelocity_valueChanged(self, value):
        self.currentServo().raw_write("CL_VEL_SET_POINT_VALUE", value)

    @Slot()
    def on_timerPlotUpdate_expired(self):
        t, d, _ = self._poller.data
        samples = len(t)

        if samples:
            self._time = np.roll(self._time, -samples)
            self._time[-samples:] = t
            self._data = np.roll(self._data, -samples)
            self._data[-samples:] = d[0]

            self._curve.setData(self._time, self._data)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # load main window (applying modern style)
    qtmodern.styles.dark(app)

    mw = qtmodern.windows.ModernWindow(ScopeWindow())
    mw.show()

    sys.exit(app.exec_())
