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


_RESOURCES = join(dirname(abspath(__file__)), 'resources')
""" str: Resources folder. """


POS_ACT = il.regs.Register(address=0x006064,
                           dtype=il.REG_DTYPE.S32,
                           access=il.REG_ACCESS.RW,
                           phy=il.REG_PHY.POS)
""" Register: Position Actual. """

VEL_ACT = il.regs.Register(address=0x00606C,
                           dtype=il.REG_DTYPE.S32,
                           access=il.REG_ACCESS.RW,
                           phy=il.REG_PHY.VEL)
""" Register: Velocity Actual. """


class HomingRunner(QObject):
    """ Homing runner. """

    finished = Signal(str)
    """ Signal: Finished signal. """

    def __init__(self, servo, en_timeout, h_timeout):
        QObject.__init__(self)

        self._servo = servo
        self._en_timeout = en_timeout
        self._h_timeout = h_timeout

    def run(self):
        try:
            self._servo.mode = il.SERVO_MODE.HOMING
            self._servo.enable(self._en_timeout)
        except Exception as exc:
            self.finished.emit('Error: ' + str(exc))

        try:
            self._servo.homing_start()
            self._servo.homing_wait(self._h_timeout)

            self.finished.emit('Finished')
        except Exception as exc:
            self.finished.emit('Error: ' + str(exc))
        finally:
            self._servo.disable()


class ScopeWindow(QMainWindow):
    """ Scope Window. """

    _SERVO_TIMEOUT = 0.1
    """ int: Default servo timeout (s). """

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

    _HOMING_TIMEOUT = 15
    """ int: Default homing timeout (s). """

    stateInit, stateIdle, stateHoming, statePosition, stateVelocity = range(5)
    """ States. """

    tabHomingIndex, tabPositionIndex, tabVelocityIndex = range(3)
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

        devs = il.devices()
        for dev in devs:
            try:
                net = il.Network(dev)
            except il.exceptions.ILCreationError:
                continue

            found = net.servos()
            for servo_id in found:
                try:
                    servo = il.Servo(net, servo_id,
                                     timeout=self._SERVO_TIMEOUT)
                except il.exceptions.ILCreationError:
                    continue

                item = QStandardItem('0x{:02x} ({})'.format(servo_id, dev))
                item.setData(servo, Qt.UserRole)

                image = QImage(join(_RESOURCES, 'images', 'triton-core.png'))
                item.setData(QPixmap.fromImage(image), Qt.DecorationRole)

                model.appendRow([item])

        self.cboxServos.setModel(model)

    def setState(self, state):
        if state == self.stateInit:
            uic.loadUi(join(_RESOURCES, 'ui', 'scopewindow.ui'), self)

            self.splitter.setStretchFactor(0, 1)
            self.splitter.setStretchFactor(1, 0)

            self.tabsMotionControl.setCurrentIndex(self.tabHomingIndex)

            palette = QApplication.instance().palette()
            iconsColor = palette.color(QPalette.Text)

            self.tabsMotionControl.setTabIcon(
                    self.tabHomingIndex,
                    qta.icon('fa.home', color=iconsColor))
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

            self.tabHoming.setEnabled(True)
            self.btnHoming.setEnabled(True)

            self.tabPosition.setEnabled(True)
            self.dialPosition.setEnabled(False)
            self.btnPosition.setText('Enable')

            self.tabVelocity.setEnabled(True)
            self.dialVelocity.setEnabled(False)
            self.btnVelocity.setText('Enable')

        elif state == self.stateHoming:
            self.cboxServos.setEnabled(False)

            self.tabPosition.setEnabled(False)
            self.tabVelocity.setEnabled(False)

            self.btnHoming.setEnabled(False)
            self.lblHomingStatus.setText('Running...')

        elif state == self.statePosition:
            self._plot.setLabel('left', 'Position', 'deg')
            self._plot.setRange(yRange=[-(self._PRANGE + 10),
                                        self._PRANGE + 10])

            self.cboxServos.setEnabled(False)

            self.tabHoming.setEnabled(False)
            self.tabVelocity.setEnabled(False)

            self.btnPosition.setText('Disable')
            self.dialPosition.setEnabled(True)

        elif state == self.stateVelocity:
            self._plot.setLabel('left', 'Velocity', 'rps')
            self._plot.setRange(yRange=[-(self._VRANGE + 10),
                                        self._VRANGE + 10])

            self.cboxServos.setEnabled(False)

            self.tabHoming.setEnabled(False)
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

    @Slot(str)
    def onHomingFinished(self, result):
        self.lblHomingStatus.setText(result)
        self.setState(self.stateIdle)

    @Slot()
    def on_btnHoming_clicked(self):
        self.setState(self.stateHoming)

        self._thread = QThread()
        self._runner = HomingRunner(self.currentServo(), self._ENABLE_TIMEOUT,
                                    self._HOMING_TIMEOUT)
        self._runner.moveToThread(self._thread)
        self._thread.started.connect(self._runner.run)
        self._runner.finished.connect(self.onHomingFinished)
        self._runner.finished.connect(self._thread.quit)
        self._runner.finished.connect(self._runner.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    @Slot()
    def on_btnPosition_clicked(self):
        servo = self.currentServo()

        if self._state == self.stateIdle:
            servo.mode = il.SERVO_MODE.PP
            servo.units_pos = il.SERVO_UNITS_POS.DEG
            servo.enable(self._ENABLE_TIMEOUT)

            self.enableScope(servo, POS_ACT)
            self.setState(self.statePosition)
        else:
            self.disableScope()
            servo.disable()

            self.setState(self.stateIdle)

    @Slot(int)
    def on_dialPosition_valueChanged(self, value):
        self.currentServo().position = value

    @Slot()
    def on_btnVelocity_clicked(self):
        servo = self.currentServo()

        if self._state == self.stateIdle:
            servo.mode = il.SERVO_MODE.PV
            servo.units_vel = il.SERVO_UNITS_VEL.RPS
            servo.enable(self._ENABLE_TIMEOUT)

            self.enableScope(servo, VEL_ACT)
            self.setState(self.stateVelocity)
        else:
            self.disableScope()
            servo.disable()

            self.setState(self.stateIdle)

    @Slot(int)
    def on_dialVelocity_valueChanged(self, value):
        self.currentServo().velocity = value

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
