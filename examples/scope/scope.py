import sys
from os.path import join, dirname, abspath

from PyQt5 import uic
from qtpy.QtCore import Qt, QTimer, Slot
from qtpy.QtGui import QStandardItemModel, QStandardItem, QImage, QPixmap
from qtpy.QtWidgets import QApplication

import numpy as np
import qtmodern.styles
import qtmodern.windows
import ingenialink as il


_RESOURCES = join(dirname(abspath(__file__)), 'resources')
""" str: Resources folder. """

VEL_ACTUAL = il.Register(0x606C, 0x00, il.DTYPE_S32, il.ACCESS_RW, il.PHY_VEL)
""" Register: Velocity actual. """

# load scope UI
Ui_ScopeWindow, QtBaseClass = uic.loadUiType(join(_RESOURCES, 'ui',
                                                  'scopewindow.ui'))


class ScopeWindow(QtBaseClass, Ui_ScopeWindow):
    """ Scope Window. """

    _AXIS_TIMEOUT = 100
    """ int: Default axis timeout (ms). """

    _FPS = 30
    """ int: Plot refresh rate (fps). """

    _N_SAMPLES = 1000
    """ int: Number of samples. """

    _POLLER_T_S = 10
    """ int: Poller sampling period (ms). """

    _POLLER_BUF_SZ = 100
    """ int: Poller buffer size. """

    _VRANGE = 40
    """ int: Velocity range (+/-). """

    def __init__(self):
        QtBaseClass.__init__(self)
        Ui_ScopeWindow.__init__(self)

        self.setupUi(self)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

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
        self._plot.setLabel('left', 'Velocity', 'rps')
        self._plot.setRange(yRange=[-(self._VRANGE + 10),
                                    self._VRANGE + 10])
        self._plot.showGrid(x=True, y=True)

        self._curve = self.scope.getPlotItem().plot()
        self._curve.setPen(color='y', width=2)

        self._timerPlotUpdate = QTimer()
        self._timerPlotUpdate.timeout.connect(self.on_timerPlotUpdate_expired)

        self._enabled = False

        self.loadAxes()

    def loadAxes(self):
        model = QStandardItemModel()

        devs = il.devices()
        for dev in devs:
            try:
                net = il.Network(dev)
            except il.exceptions.IngeniaLinkCreationError:
                continue

            found = net.axes()
            for axis_id in found:
                try:
                    axis = il.Axis(net, axis_id, timeout=self._AXIS_TIMEOUT)
                except il.exceptions.IngeniaLinkCreationError:
                    continue

                item = QStandardItem('0x{:02x} ({})'.format(axis_id, dev))
                item.setData(axis, Qt.UserRole)

                image = QImage(join(_RESOURCES, 'images', 'triton-core.png'))
                item.setData(QPixmap.fromImage(image), Qt.DecorationRole)

                model.appendRow([item])

        self.cboxAxes.setModel(model)

    def currentAxis(self):
        index = self.cboxAxes.model().index(self.cboxAxes.currentIndex(), 0)
        axis = self.cboxAxes.model().data(index, Qt.UserRole)

        return axis

    @Slot()
    def on_btnPower_clicked(self):
        axis = self.currentAxis()

        if not self._enabled:
            # enable axis (PV mode, using RPS)
            axis.mode = il.MODE_PV
            axis.units_vel = il.UNITS_VEL_RPS
            axis.enable()

            # configure poller and plot updates
            self._poller = il.Poller(axis, VEL_ACTUAL, self._POLLER_T_S,
                                     self._POLLER_BUF_SZ)

            self._data = np.zeros(self._N_SAMPLES)
            self._time = np.arange(-self._N_SAMPLES * self._POLLER_T_S / 1000,
                                   0, self._POLLER_T_S / 1000)

            self._timerPlotUpdate.start(1000 / self._FPS)

            self._poller.start()

            # update GUI
            self.cboxAxes.setEnabled(False)
            self.btnPower.setText('Disable')
            self.dialVelocity.setEnabled(True)

            self._enabled = True
        else:
            # disable poller and plot updates
            self._poller.stop()
            self._timerPlotUpdate.stop()
            axis.disable()

            # update GUI
            self.cboxAxes.setEnabled(True)
            self.btnPower.setText('Enable')
            self.dialVelocity.setEnabled(False)

            self._enabled = False

    @Slot(int)
    def on_dialVelocity_valueChanged(self, value):
        self.currentAxis().velocity = value

    @Slot()
    def on_timerPlotUpdate_expired(self):
        t, d = self._poller.data
        samples = len(d)

        if samples:
            self._data = np.roll(self._data, -samples)
            self._data[-samples:] = d
            self._time = np.roll(self._time, -samples)
            self._time[-samples:] = t

            self._curve.setData(self._time, self._data)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # enable High DPI support
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        app.setAttribute(Qt.AA_UseHighDpiPixmaps)

    # load main window (applying modern style)
    qtmodern.styles.dark(app)

    mw = qtmodern.windows.ModernWindow(ScopeWindow())
    mw.setTitle('Scope')
    mw.show()

    sys.exit(app.exec_())
