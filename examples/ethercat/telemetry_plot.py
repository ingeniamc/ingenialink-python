import argparse
import time
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
        self._frequency = frequency
        self._rate_start_time = time.monotonic()
        self._rate_start_count = poller.sample_count
        self._samples = {
            register.identifier: deque[tuple[float, float]]()
            for register in registers
        }
        self._plot = pg.PlotWidget(title="EtherCAT telemetry")
        self._plot.setLabel("bottom", "Time", units="s")
        self._plot.showGrid(x=True, y=True)
        self._plot.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        self._follow_checkbox = QtWidgets.QCheckBox("Follow latest samples")
        self._follow_checkbox.setChecked(True)
        self._follow_checkbox.toggled.connect(self._set_follow_latest)
        self._rate_label = QtWidgets.QLabel()
        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(self._follow_checkbox)
        controls.addStretch()
        controls.addWidget(self._rate_label)
        central_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central_widget)
        layout.addWidget(self._plot)
        layout.addLayout(controls)
        self.setCentralWidget(central_widget)
        self.resize(1000, 600)
        self._curves = {
            register.identifier: self._plot.plot(name=register.identifier, symbol="o", symbolSize=4)
            for register in registers
        }
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_plot)
        self._timer.start(20)
        self._update_rate_label()

    @QtCore.pyqtSlot(bool)
    def _set_follow_latest(self, follow_latest: bool) -> None:
        del follow_latest
        self._plot.enableAutoRange(axis="x", enable=False)

    def _update_rate_label(self) -> None:
        now = time.monotonic()
        elapsed = now - self._rate_start_time
        if elapsed >= 1.0:
            sample_count = self._poller.sample_count
            measured_frequency = (sample_count - self._rate_start_count) / elapsed
            self._rate_start_time = now
            self._rate_start_count = sample_count
            self._rate_label.setText(
                f"Configured: {self._frequency:,.0f}/s | Measured: {measured_frequency:,.0f}/s"
            )

    @QtCore.pyqtSlot()
    def _update_plot(self) -> None:
        samples = []
        while (sample := self._poller.get_sample()) is not None:
            samples.append(sample)
        self._update_rate_label()
        if not samples:
            return

        for sample in samples:
            if self._start_time is None:
                self._start_time = sample.timestamp
            elapsed = sample.timestamp - self._start_time
            for register in self._registers:
                value = sample.values[register.identifier]
                if not isinstance(value, (int, float)):
                    raise TypeError(
                        f"Telemetry register {register.identifier} did not return a number"
                    )
                self._samples[register.identifier].append((elapsed, float(value)))

        elapsed = samples[-1].timestamp - self._start_time
        for register in self._registers:
            times, values = zip(*self._samples[register.identifier])
            self._curves[register.identifier].setData(times, values)
        if self._follow_checkbox.isChecked():
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
    parser.add_argument(
        "-i",
        "--interface",
        default=r"\Device\NPF_{1EAA59CE-C1E8-4AD5-88C3-EA289CB8C986}",
        help="EtherCAT adapter name",
    )
    parser.add_argument(
        "-d",
        "--dictionary-path",
        type=Path,
        default=Path(r"C:\GIT\workspaces\tm\ws\den-net-e_dev294645.xdf3"),
    )
    parser.add_argument("-s", "--slave-id", type=int, default=1)
    parser.add_argument("-a", "--axis", type=int, default=1)
    parser.add_argument(
        "-r",
        "--register",
        action="append",
        default=None,
        help="Register to plot; repeat this option for multiple registers",
    )
    parser.add_argument("-f", "--frequency", type=float, default=2_000.0)
    parser.add_argument("-w", "--window", type=float, default=10.0)
    args = parser.parse_args()
    if args.register is None:
        args.register = ["DRV_PROT_VBUS_VALUE"]
    return args


if __name__ == "__main__":
    live_plot(setup_command())
