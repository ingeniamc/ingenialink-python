import socket

import ingenialogger

from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT
from ingenialink.ethernet.network import NET_STATE, EthernetNetwork
from ingenialink.exceptions import ILError
from ingenialink.virtual.servo import VirtualServo

logger = ingenialogger.get_logger(__name__)


class VirtualNetwork(EthernetNetwork):
    """Network for all virtual drive communications."""

    def connect_to_slave(  # type: ignore [override]
        self,
        target: str,
        dictionary: str,
        port: int = 1061,
        connection_timeout: float = DEFAULT_ETH_CONNECTION_TIMEOUT,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> VirtualServo:
        """Connects to a slave through the given network settings.

        Args:
            dictionary: Path to the target dictionary file.
            target: IP of the target slave.
            port: Port to connect to the slave.
            connection_timeout: Time in seconds of the connection timeout.
            servo_status_listener: Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener: Toggle the listener of the network
                status, connection and disconnection.

        Returns:
            VirtualServo: Instance of the servo connected.

        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(connection_timeout)
        sock.connect((target, port))
        servo = VirtualServo(sock, dictionary, servo_status_listener)
        try:
            servo.get_state()
        except ILError as e:
            servo.stop_status_listener()
            raise ILError(f"Drive not found in IP {target}.") from e
        self.servos.append(servo)
        self._set_servo_state(target, NET_STATE.CONNECTED)

        if net_status_listener:
            self.start_status_listener()
        else:
            self.stop_status_listener()

        return servo
