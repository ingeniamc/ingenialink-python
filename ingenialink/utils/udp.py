import binascii
import socket
import struct

import ingenialogger

from ingenialink.exceptions import ILUDPError

logger = ingenialogger.get_logger(__name__)


class UDP:
    """Class to create a UDP connection.

    UDP Contains all the basic operations for the lightweight data
    transport protocol based off the MCB protocol.
    """

    def __init__(self, port: int, ip: str) -> None:
        self.port = port
        self.ip = ip
        self.rcv_buffer_size = 512
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        self.socket.settimeout(8)
        self.socket.connect((ip, port))

    def __del__(self) -> None:
        """Delete method."""
        try:
            self.socket.close()
        except Exception as e:
            logger.error("Socket already closed. Exception: %s", e)

    def close(self) -> None:
        """Closes the socket."""
        self.socket.close()
        logger.info("Socket closed")

    def write(self, frame: bytes) -> None:
        """Sends a message through the established socket.

        Args:
            frame: Frame to be sent.
        """
        self.socket.sendto(frame, (self.ip, self.port))
        self.check_ack()

    def read(self) -> bytes:
        """Reads a message from the socket.

        Returns:
            Data read from the buffer.
        """
        data, _ = self.socket.recvfrom(self.rcv_buffer_size)
        return data

    def check_ack(self) -> int:
        """Checks if the received message has a valid ACK.

        Raises:
            Exception: no ACK received.

        Returns:
            Command code of the message.
        """
        rcv = self.read()
        ret_cmd = self.unmsg(rcv)
        if ret_cmd != 3:
            self.socket.close()
            raise Exception(f"No ACK received (command received {ret_cmd})")
        return ret_cmd

    @staticmethod
    def unmsg(in_frame: bytes) -> int:
        """Decodes the a given frame.

        Base uart frame (subnode [4 bits], node [12 bits],
        Addr [12 bits], cmd [3 bits], pending [1 bit],
        Data [8 bytes]) and CRC [2 bytes] is 14 bytes long

        Args:
            in_frame: Input frame.

        Raises:
            ILUDPError: if CRC error.

        Returns:
            Command from the given message.
        """
        header = in_frame[2:4]
        cmd = struct.unpack("<H", header)[0] >> 1
        cmd = cmd & 0x7

        # CRC is computed with header and data (removing Tx CRC)
        crc = binascii.crc_hqx(in_frame[0:12], 0)
        crcread = struct.unpack("<H", in_frame[12:14])[0]
        if crcread != crc:
            raise ILUDPError("CRC error")

        return int(cmd)

    @staticmethod
    def raw_msg(node: int, subnode: int, cmd: int, data: bytes, size: int) -> bytes:
        """Creates a raw message with the proper format.

        Args:
            node: Node ID.
            subnode: Subnode to be targeted.
            cmd: Command of the message.
            data: Data of the message.
            size: Size of the message.

        Returns:
            Message frame.
        """
        node_head = (node << 4) | (subnode & 0xF)
        node_head_bytes = struct.pack("<H", node_head)

        if size > 8:
            cmd = cmd + 1
            head = struct.pack("<H", cmd)
            head_size = struct.pack("<H", size)
            head_size = head_size + bytes([0] * (8 - len(head_size)))
            return (
                node_head_bytes
                + head
                + head_size
                + struct.pack("<H", binascii.crc_hqx(node_head_bytes + head + head_size, 0))
                + data
            )
        else:
            head = struct.pack("<H", cmd)
            return (
                node_head_bytes
                + head
                + data
                + struct.pack("<H", binascii.crc_hqx(node_head_bytes + head + data, 0))
            )

    def raw_cmd(self, node: int, subnode: int, cmd: int, data: bytes) -> None:
        """Creates a frame message and sends it.

        Args:
            node: Node ID.
            subnode: Subnode to be targeted.
            cmd: Command of the message.
            data: Data of the message.
        """
        if len(data) <= 8:
            data = data + bytes([0] * (8 - len(data)))
        frame = self.raw_msg(node, subnode, cmd, data, len(data))
        self.write(frame)
