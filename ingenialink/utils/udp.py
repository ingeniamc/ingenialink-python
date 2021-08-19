import socket
import struct
import binascii

from ..exceptions import *

import ingenialogger
logger = ingenialogger.get_logger(__name__)


class UDP:
    def __init__(self, port, ip):
        self.port = port
        self.ip = ip
        self.rcv_buffer_size = 512
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        self.socket.settimeout(8)
        self.socket.connect((ip, port))

    def __del__(self):
        try:
            self.socket.close()
        except Exception as e:
            logger.error('Socket already closed. Exception: %s', e)

    def close(self):
        self.socket.close()
        logger.info('Socket closed')

    def write(self, frame):
        self.socket.sendto(frame, (self.ip, self.port))
        self.check_ack()

    def read(self):
        data, address = self.socket.recvfrom(self.rcv_buffer_size)
        return data

    def check_ack(self):
        rcv = self.read()
        ret_cmd = self.unmsg(rcv)
        if ret_cmd != 3:
            self.socket.close()
            raise Exception('No ACK received (command received %d)' % ret_cmd)
        return ret_cmd

    @staticmethod
    def unmsg(in_frame):
        # Base uart frame (subnode [4 bits], node [12 bits],
        # Addr [12 bits], cmd [3 bits], pending [1 bit],
        # Data [8 bytes]) and CRC [2 bytes] is 14 bytes long
        header = in_frame[2:4]
        cmd = struct.unpack('<H', header)[0] >> 1
        cmd = cmd & 0x7

        # CRC is computed with header and data (removing Tx CRC)
        crc = binascii.crc_hqx(in_frame[0:12], 0)
        crcread = struct.unpack('<H', in_frame[12:14])[0]
        if crcread != crc:
            raise ILUDPException('CRC error')

        return cmd

    @staticmethod
    def raw_msg(node, subnode, cmd, data, size):
        node_head = (node << 4) | (subnode & 0xf)
        node_head = struct.pack('<H', node_head)

        if size > 8:
            cmd = cmd + 1
            head = struct.pack('<H', cmd)
            head_size = struct.pack('<H', size)
            head_size = head_size + bytes([0] * (8 - len(head_size)))
            ret = node_head + head + head_size + struct.pack('<H',
                                                             binascii.crc_hqx(node_head + head + head_size, 0)) + data
        else:
            head = struct.pack('<H', cmd)
            ret = node_head + head + data + struct.pack('<H', binascii.crc_hqx(node_head + head + data, 0))

        return ret

    def raw_cmd(self, node, subnode, cmd, data):
        if len(data) > 8:
            frame = self.raw_msg(node, subnode, cmd, data, len(data))
        else:
            data = data + bytes([0] * (8 - len(data)))
            frame = self.raw_msg(node, subnode, cmd, data, len(data))

        self.write(frame)
