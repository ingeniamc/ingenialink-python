"""Enumerations used by the SDCP protocol."""

from enum import IntEnum, IntFlag


class SDCPOpcode(IntEnum):
    """Opcodes defined by the SDCP Core protocol."""

    IDENTIFICATION = 0x01
    READ = 0x02
    WRITE = 0x03


class SDCPFlag(IntFlag):
    """Flags defined by the SDCP Core protocol."""

    NONE = 0x00
    REPLY = 0x01
    ERROR = 0x02


class SDCPDeviceMode(IntEnum):
    """Operating modes reported by an SDCP device."""

    APPLICATION = 0x00
    BOOTLOADER = 0x01


class SDCPProfileFlags(IntFlag):
    """Optional profiles advertised by an SDCP device."""

    SECURITY = 0x0001
    REALTIME = 0x0002
    SAFETY = 0x0004
