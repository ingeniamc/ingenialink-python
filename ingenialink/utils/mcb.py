import io
import struct
from binascii import crc_hqx
from typing import Optional, TypeVar

from ingenialink.constants import MCB_CMD_ACK
from ingenialink.exceptions import ILNACKError, ILWrongCRCError, ILWrongRegisterError

T = TypeVar("T", bound="MCB")


class MCB:
    """Class to create and process MCB frames.

    Motion Control Bus (MCB) is a high-speed serial protocol designed for getting low
    latency and high determinism in motion control systems where control loops
    work at high update rates (tens of kHz).
    """

    EXTENDED_MESSAGE_SIZE = 8
    MCB_DEFAULT_NODE = 0xA
    MCB_HEADER_H_SIZE = 2
    MCB_HEADER_L_SIZE = 2
    MCB_HEADER_SIZE = MCB_HEADER_H_SIZE + MCB_HEADER_L_SIZE
    MCB_DATA_SIZE = 8
    MCB_CRC_SIZE = 2
    MCB_FRAME_SIZE = MCB_HEADER_SIZE + MCB_DATA_SIZE + MCB_CRC_SIZE
    EXTENDED_DATA_START_BYTE = MCB_FRAME_SIZE
    EXTENDED_DATA_END_BYTE = None
    DATA_START_BYTE = MCB_HEADER_SIZE
    DATA_END_BYTE = MCB_FRAME_SIZE - MCB_CRC_SIZE
    ERR_CODE_SIZE = 4

    def __init__(self) -> None:
        pass

    def __del__(self) -> None:
        """Delete method."""

    def create_msg(self, node: int, subnode: int, cmd: int, data: bytes, size: int) -> bytes:
        """Creates a command message following the MCB protocol.

        Args:
            node: Reserved bits used to identify the destination device.
            subnode: Subsystem bits used to identify the destination device.
            cmd: Command to lead the message.
            data: Data to be added to the message.
            size: Size of data.

        Returns:
            bin: MCB command message.
        """
        node_head = (node << 4) | (subnode & 0xF)
        node_head_bytes = struct.pack("<H", node_head)

        if size > self.EXTENDED_MESSAGE_SIZE:
            cmd = cmd + 1
            head = struct.pack("<H", cmd)
            head_size = struct.pack("<H", size)
            head_size = head_size + bytes([0] * (self.EXTENDED_MESSAGE_SIZE - len(head_size)))
            ret = (
                node_head_bytes
                + head
                + head_size
                + struct.pack("<H", crc_hqx(node_head_bytes + head + head_size, 0))
                + data
            )
        else:
            head = struct.pack("<H", cmd)
            ret = (
                node_head_bytes
                + head
                + data
                + struct.pack("<H", crc_hqx(node_head_bytes + head + data, 0))
            )

        return ret

    def add_cmd(
        self, node: int, subnode: int, cmd: int, data: bytes, output: io.BufferedWriter
    ) -> None:
        """Creates and adds a MCB message to a given file.

        Args:
            node: Reserved bits used to identify the destination device.
            subnode: Subsystem bits used to identify the destination device.
            cmd: Command to lead the message.
            data: Data to be added to the message.
            output: File object to store the message.
        """
        if len(data) <= self.EXTENDED_MESSAGE_SIZE:
            data = data + bytes([0] * (self.EXTENDED_MESSAGE_SIZE - len(data)))
        frame = self.create_msg(node, subnode, cmd, data, len(data))
        output.write(frame)

    @classmethod
    def build_mcb_frame(
        cls: type[T], cmd: int, subnode: int, address: int, data: Optional[bytes] = None
    ) -> bytes:
        """Build an MCB frame.

        Args:
            cmd: Read/write command.
            subnode: Target axis of the drive.
            address: Register address to be read/written.
            data: Data to be written to the register.

        Returns:
            MCB frame.
        """
        if data is None:
            data = b"\x00" * cls.MCB_DATA_SIZE
        data_size = len(data)
        extended = data_size > cls.MCB_DATA_SIZE
        header_h = (cls.MCB_DEFAULT_NODE << 4) | subnode
        header_l = (address << 4) | (cmd << 1) | extended
        header = header_h.to_bytes(cls.MCB_HEADER_H_SIZE, "little") + header_l.to_bytes(
            cls.MCB_HEADER_L_SIZE, "little"
        )
        if extended:
            config_data = data_size.to_bytes(cls.MCB_DATA_SIZE, "little")
        else:
            config_data = data + b"\x00" * (cls.MCB_DATA_SIZE - data_size)
        frame = header + config_data
        crc = crc_hqx(frame, 0)
        frame += crc.to_bytes(cls.MCB_CRC_SIZE, "little")
        if extended:
            frame += data
        return frame

    @classmethod
    def read_mcb_data(cls: type[T], expected_address: int, frame: bytes) -> bytes:
        """Read an MCB frame and return its data.

        Args:
            expected_address: Address of the expected register to be
            read.
            frame: MCB frame.

        Raises:
            ILNACKError: If the received command is a NACK.
            ILWrongRegisterError: If the received address does not match
            the expected address.

        Returns:
            data contained in frame.
        """
        recv_add, _, cmd, data = cls.read_mcb_frame(frame)

        if cmd != MCB_CMD_ACK:
            err_code_little = int.from_bytes(data[: cls.ERR_CODE_SIZE], byteorder="little")
            raise ILNACKError(err_code_little)
        if expected_address != recv_add:
            raise ILWrongRegisterError(
                f"Received address: {hex(recv_add)} does "
                "not match expected address: "
                f"{hex(expected_address)}"
            )
        return data

    @classmethod
    def read_mcb_frame(cls: type[T], frame: bytes) -> tuple[int, int, int, bytes]:
        """Read an MCB frame and return its address, subnode, data and command.

        Args:
            frame: MCB frame.

        Returns:
            register address
            subnode
            command
            data contained in frame.

        Raises:
            ILWrongCRCError: If the received CRC code does not match
            the calculated CRC code.
        """
        recv_crc_bytes = frame[cls.MCB_FRAME_SIZE - cls.MCB_CRC_SIZE : cls.MCB_FRAME_SIZE]
        recv_crc = int.from_bytes(recv_crc_bytes, "little")
        calc_crc = crc_hqx(frame[: cls.MCB_FRAME_SIZE - cls.MCB_CRC_SIZE], 0)
        if recv_crc != calc_crc:
            raise ILWrongCRCError
        header = frame[cls.MCB_HEADER_L_SIZE : cls.MCB_HEADER_SIZE]
        recv_add = (int.from_bytes(header, "little")) >> 4

        header_l = frame[cls.MCB_HEADER_L_SIZE]
        extended = header_l & 1
        cmd = (header_l & 0xE) >> 1
        subnode = int.from_bytes(frame[: cls.MCB_HEADER_L_SIZE], "little") & 0xF

        if extended:
            data_start_byte = cls.EXTENDED_DATA_START_BYTE
            data_end_byte = cls.EXTENDED_DATA_END_BYTE
        else:
            data_start_byte = cls.DATA_START_BYTE
            data_end_byte = cls.DATA_END_BYTE
        data = frame[data_start_byte:data_end_byte]

        return recv_add, subnode, cmd, data
