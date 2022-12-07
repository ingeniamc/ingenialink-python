import struct
from binascii import crc_hqx

from ingenialink.exceptions import ILWrongCRCError, ILNACKError,\
    ILWrongRegisterError
from ingenialink.constants import MCB_CMD_ACK


class MCB:
    """Motion Control Bus (MCB) is a high-speed serial protocol designed for getting low
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

    def __init__(self):
        pass

    def __del__(self):
        pass

    def create_msg(self, node, subnode, cmd, data, size):
        """Creates a command message following the MCB protocol.

        Args:
            node (int): Reserved bits used to identify the destination device.
            subnode (int): Subsystem bits used to identify the destination device.
            cmd (int): Command to lead the message.
            data (bytes): Data to be added to the message.
            size (int): Size of data.

        Returns:
            bin: MCB command message.
        """
        node_head = (node << 4) | (subnode & 0xf)
        node_head = struct.pack('<H', node_head)

        if size > self.EXTENDED_MESSAGE_SIZE:
            cmd = cmd + 1
            head = struct.pack('<H', cmd)
            head_size = struct.pack('<H', size)
            head_size = head_size + bytes(
                [0] * (self.EXTENDED_MESSAGE_SIZE - len(head_size)))
            ret = node_head + head + head_size + struct.pack(
                '<H', crc_hqx(node_head + head + head_size, 0)) + data
        else:
            head = struct.pack('<H', cmd)
            ret = node_head + head + data + struct.pack(
                '<H', crc_hqx(node_head + head + data, 0))

        return ret

    def add_cmd(self, node, subnode, cmd, data, output):
        """Creates and adds a MCB message to a given file.

        Args:
            node (int): Reserved bits used to identify the destination device.
            subnode (int): Subsystem bits used to identify the destination device.
            cmd (int): Command to lead the message.
            data (bytes): Data to be added to the message.
            output (file): File object to store the message.
        """
        if len(data) <= self.EXTENDED_MESSAGE_SIZE:
            data = data + bytes([0] * (self.EXTENDED_MESSAGE_SIZE - len(data)))
        frame = self.create_msg(node, subnode, cmd, data, len(data))
        output.write(frame)

    @classmethod
    def build_mcb_frame(cls, cmd, subnode, address, data=None):
        """Build an MCB frame.

        Args:
            cmd (int): Read/write command.
            subnode (int): Target axis of the drive.
            address (int): Register address to be read/written.
            data (bytes): Data to be written to the register.

        Returns:
            bytes: MCB frame.
        """
        if data is None:
            data = b'\x00' * cls.MCB_DATA_SIZE
        data_size = len(data)
        extended = data_size > cls.MCB_DATA_SIZE
        header_h = (cls.MCB_DEFAULT_NODE << 4) | subnode
        header_l = (address << 4) | (cmd << 1) | extended
        header = header_h.to_bytes(cls.MCB_HEADER_H_SIZE, 'little') + \
                 header_l.to_bytes(cls.MCB_HEADER_L_SIZE, 'little')
        if extended:
            config_data = data_size.to_bytes(cls.MCB_DATA_SIZE, 'little')
        else:
            config_data = data + b'\x00' * (cls.MCB_DATA_SIZE - data_size)
        frame = header + config_data
        crc = crc_hqx(frame, 0)
        frame += crc.to_bytes(cls.MCB_CRC_SIZE, 'little')
        if extended:
            frame += data
        return frame

    @classmethod
    def read_mcb_data(cls, expected_address, frame):
        """Read an MCB frame and return its data.

        Args:
            expected_address (int): Address of the expected register to be
            read.
            frame (bytes): MCB frame.

        Raises:
            ILWrongCRCError: If the received CRC code does not match
            the calculated CRC code.
            ILNACKError: If the received command is a NACK.
            ILWrongRegisterError: If the received address does not match
            the expected address.

        Returns:
            bytes: data contained in frame.
        """
        recv_add, _, cmd, data = cls.read_mcb_frame(frame)

        if cmd != MCB_CMD_ACK:
            err = frame[cls.DATA_START_BYTE:cls.DATA_END_BYTE].hex()
            raise ILNACKError(f'Communications error (NACK -> {err[::-1]})')
        if expected_address != recv_add:
            raise ILWrongRegisterError(f'Received address: {hex(recv_add)} does '
                                       f'not match expected address: '
                                       f'{hex(expected_address)}')
        return data

    @classmethod
    def read_mcb_frame(cls, frame):
        """Read an MCB frame and return its address, subnode, data and command.

        Args:
            frame (bytes): MCB frame.

        Returns:
            int: register address
            int: subnode 
            bytes: data contained in frame.
            int: command

        Raises:
            ILWrongCRCError: If the received CRC code does not match
            the calculated CRC code.
        """
        recv_crc_bytes = frame[cls.MCB_FRAME_SIZE - cls.MCB_CRC_SIZE
                               :cls.MCB_FRAME_SIZE]
        recv_crc = int.from_bytes(recv_crc_bytes, 'little')
        calc_crc = crc_hqx(frame[:cls.MCB_FRAME_SIZE - cls.MCB_CRC_SIZE], 0)
        if recv_crc != calc_crc:
            raise ILWrongCRCError
        header = frame[cls.MCB_HEADER_L_SIZE:cls.MCB_HEADER_SIZE]
        recv_add = (int.from_bytes(header, 'little')) >> 4
       
        header_l = frame[cls.MCB_HEADER_L_SIZE]
        extended = header_l & 1
        cmd = (header_l & 0xE) >> 1
        subnode = int.from_bytes(frame[:cls.MCB_HEADER_L_SIZE], 'little') & 0xF
        
        if extended:
            data_start_byte = cls.EXTENDED_DATA_START_BYTE
            data_end_byte = cls.EXTENDED_DATA_END_BYTE
        else:
            data_start_byte = cls.DATA_START_BYTE
            data_end_byte = cls.DATA_END_BYTE
        data = frame[data_start_byte:data_end_byte]   
        
        return recv_add, subnode, cmd, data
