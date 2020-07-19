import logging
from enum import Enum
from typing import Iterable, List

import serial

from .serial_protocol import BraviaSerialPort
from .util import dump_bytes_to_str


_BRAVIA_POWER_STATE_FUNCTION_BYTE = 0x00

_BRAVIA_INPUT_MODE_FUNCTION_BYTE = 0x02

_BRAVIA_PICTURE_MODE_FUNCTION_BYTE = 0x20
_BRAVIA_SET_PICTURE_MODE_DIRECT_BYTE = 0x01


class PictureMode(Enum):
    VIVID = 0x00
    STANDARD = 0x01
    CINEMA_HOME = 0x02
    CUSTOM = 0x03
    CINEMA_PRO = 0x06
    SPORTS = 0x07
    GAME = 0x08
    GRAPHICS = 0x09


# Most-significant nibble: byte 0 of read/write request payload,
# least-significant nibble: byte 1 of read/write request payload.
class InputMode(Enum):
    SCART_1 = 0x21
    SCART_2 = 0x22
    SCART_3 = 0x23
    COMPONENT_1 = 0x31
    COMPONENT_2 = 0x32
    COMPONENT_3 = 0x33
    HDMI_1 = 0x41
    HDMI_2 = 0x42
    HDMI_3 = 0x43
    HDMI_4 = 0x44
    HDMI_5 = 0x45
    PC = 0x51
    SHARED_INPUT = 0x71


class BraviaDevice:
    """
    Provides a high-level interface for controlling a Sony Bravia device.
    """
    def __init__(self, bravia_serial_port: BraviaSerialPort):
        self.bravia_serial_port = bravia_serial_port
        self._logger = logging.getLogger(__name__)

    def get_power_mode(self) -> bool:
        """
        Returns True if the connected Bravia device is powered on or False if it
        is powered off.
        """
        response_bytes = self.bravia_serial_port.request_read(_BRAVIA_POWER_STATE_FUNCTION_BYTE)
        if response_bytes[0] == 0x00:
            return False
        if response_bytes[0] == 0x01:
            return True

        raise ValueError(f"Got unexpected power state byte from Bravia: {response_bytes[0]:02X}")

    def set_power_mode(self, power_mode: bool) -> None:
        """
        Sets the Bravia device's power mode to on if True is passed in or off if
        False is passed in.
        """
        self.bravia_serial_port.request_write(
            _BRAVIA_POWER_STATE_FUNCTION_BYTE, [0x01 if power_mode else 0x00]
        )

    def set_picture_mode(self, picture_mode: PictureMode) -> None:
        self.bravia_serial_port.request_write(
            _BRAVIA_PICTURE_MODE_FUNCTION_BYTE,
            [
                _BRAVIA_SET_PICTURE_MODE_DIRECT_BYTE,
                picture_mode.value,
            ],
        )

    def get_input_mode(self) -> InputMode:
        response_bytes = self.bravia_serial_port.request_read(_BRAVIA_INPUT_MODE_FUNCTION_BYTE)
        input_mode_enum_value = ((response_bytes[0] & 0x0F) << 4) | (response_bytes[1] & 0x0F)
        return InputMode(input_mode_enum_value)

    def set_input_mode(self, input_mode: InputMode) -> None:
        byte0 = (input_mode.value & 0xF0) >> 4
        byte1 = input_mode.value & 0x0F
        self.bravia_serial_port.request_write(
            _BRAVIA_INPUT_MODE_FUNCTION_BYTE,
            [
                byte0,  # Input type (e.g. HDMI)
                byte1,  # Input number (e.g. 2 -> second HDMI input)
            ],
        )
