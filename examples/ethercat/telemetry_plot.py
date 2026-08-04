import argparse
from collections import deque
from pathlib import Path

import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethercat.telemetry import EthercatTelemetry, TelemetryPoller
from ingenialink.register import Register


class TelemetryPlot(QtWidgets.QMainWindow):
    """Display live EtherCAT telemetry values with pyqtgraph."""

    def __init__(
        self,
        poller: TelemetryPoller,
        registers: list[Register],
        window: float,
        frequency: float,
    ) -> None:
        super().__init__()
        self._poller = poller
        self._registers = registers
        self._window = window
        self._start_time: float | None = None
        self._samples = {
            register.identifier: deque[tuple[float, float]](maxlen=max(2, int(window * frequency)))
            for register in registers
        }
        self._plot = pg.PlotWidget(title="EtherCAT telemetry")
        self._plot.setLabel("bottom", "Time", units="s")
        self._plot.showGrid(x=True, y=True)
        self.setCentralWidget(self._plot)
        self.resize(1000, 600)
        self._curves = {
            register.identifier: self._plot.plot(name=register.identifier) for register in registers
        }
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_plot)
        self._timer.start(20)

    @QtCore.pyqtSlot()
    def _update_plot(self) -> None:
        sample = self._poller.get_latest_sample()
        if sample is None:
            return
        if self._start_time is None:
            self._start_time = sample.timestamp

        elapsed = sample.timestamp - self._start_time
        for register in self._registers:
            value = sample.values[register.identifier]
            if not isinstance(value, (int, float)):
                raise TypeError(f"Telemetry register {register.identifier} did not return a number")
            self._samples[register.identifier].append((elapsed, float(value)))
            times, values = zip(*self._samples[register.identifier])
            self._curves[register.identifier].setData(times, values)
        self._plot.setXRange(max(0.0, elapsed - self._window), max(self._window, elapsed))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802, D102
        self._timer.stop()
        self._poller.stop()
        super().closeEvent(event)


def live_plot(args: argparse.Namespace) -> None:
    """Plot EtherCAT telemetry registers while the drive is running.

    Args:
        args: Parsed command-line arguments.
    """
    net = EthercatNetwork(args.interface)
    servo = net.connect_to_slave(args.slave_id, args.dictionary_path)
    telemetry = EthercatTelemetry(servo)
    registers = [servo.dictionary.get_register(uid, axis=args.axis) for uid in args.register]
    frequency = telemetry.configure(registers, desired_frequency=args.frequency)
    poller = TelemetryPoller(telemetry, registers)
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = TelemetryPlot(poller, registers, args.window, frequency)
    telemetry.start()
    poller.start()
    window.show()
    try:
        application.exec()
    finally:
        poller.stop()
        telemetry.stop()
        net.disconnect_from_slave(servo)


def setup_command() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Live EtherCAT telemetry plot")
    parser.add_argument("-i", "--interface", required=True, help="EtherCAT adapter name")
    parser.add_argument("-d", "--dictionary-path", type=Path, required=True)
    parser.add_argument("-s", "--slave-id", type=int, default=1)
    parser.add_argument("-a", "--axis", type=int, default=1)
    parser.add_argument(
        "-r",
        "--register",
        action="append",
        default=None,
        help="Register to plot; repeat this option for multiple registers",
    )
    parser.add_argument("-f", "--frequency", type=float, default=100.0)
    parser.add_argument("-w", "--window", type=float, default=10.0)
    args = parser.parse_args()
    if args.register is None:
        args.register = ["DRV_PROT_VBUS_VALUE"]
    return args


if __name__ == "__main__":
    live_plot(setup_command())
