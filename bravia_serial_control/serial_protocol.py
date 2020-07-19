import logging
from typing import Iterable, List

import serial

from .util import dump_bytes_to_str


_BRAVIA_READ_REQUEST_HEADER_BYTE = 0x83
_BRAVIA_WRITE_REQUEST_HEADER_BYTE = 0x8C

# Category byte specified in read/write requests. Seems to be the same for all
# requests.
_BRAVIA_REQUEST_CATEGORY_BYTE = 0x00

# First byte sent in response to a read/write request.
_BRAVIA_RESPONSE_HEADER_BYTE = 0x70


class BraviaSerialPort:
    """
    Implements the low-level serial protocol for communicating with a Sony
    Bravia device.
    """
    def __init__(self, serial_port: serial.Serial):
        self.serial_port = serial_port
        self._logger = logging.getLogger(__name__)

    def request_read(self, function_byte: int) -> bytes:
        """
        Sends a read request using the specified function byte. Returns a
        response payload containing the result of the read request; the format
        of its contents depend on the function byte.
        """
        _validate_function_byte(function_byte)

        message = [
            _BRAVIA_READ_REQUEST_HEADER_BYTE,
            _BRAVIA_REQUEST_CATEGORY_BYTE,
            function_byte,
            0xFF,
            0xFF,
        ]
        message.append(_calculate_checksum(message))

        self._logger.debug("Sending Bravia read request on %s: %s", self.serial_port.name, dump_bytes_to_str(message))
        self.serial_port.write(message)
        return self._get_read_request_response()

    def request_write(self, function_byte: int, payload: Iterable[int]) -> None:
        """
        Sends a write request using the specified function byte and
        corresponding payload. Does not return a response.
        """
        _validate_function_byte(function_byte)

        # Length of the payload plus the checksum
        message_length_byte = len(payload) + 1
        if message_length_byte > 255:
            raise ValueError(
                f"Payload is too large (expected length <= 254 bytes, got {len(payload)} bytes)"
            )

        message = [
            _BRAVIA_WRITE_REQUEST_HEADER_BYTE,
            _BRAVIA_REQUEST_CATEGORY_BYTE,
            function_byte,
            message_length_byte,
            *payload,
        ]
        message.append(_calculate_checksum(message))

        self._logger.debug("Sending Bravia write request on %s: %s", self.serial_port.name, dump_bytes_to_str(message))
        self.serial_port.write(message)
        self._get_write_request_response()

    def _get_read_request_response(self) -> bytes:
        initial_response_bytes = self.serial_port.read(3)
        response_header = initial_response_bytes[0]
        if response_header != _BRAVIA_RESPONSE_HEADER_BYTE:
            raise RuntimeError(
                f"Received invalid response header from Bravia: 0x{response_header:02X})"
            )

        _validate_response_answer_byte(initial_response_bytes[1])

        # Read the response payload
        payload_length = initial_response_bytes[2]
        payload_with_checksum = self.serial_port.read(size=payload_length)
        if len(payload_with_checksum) != payload_length:
            raise RuntimeError(
                (
                    f"Received payload with unexpected length (expected {payload_length} bytes, "
                    f"got {len(payload_with_checksum)} bytes)"
                )
            )

        payload_without_checksum = payload_with_checksum[:-1]

        # Checksum includes bytes from the initial response as well as the
        # payload
        _validate_payload_checksum([*initial_response_bytes, *payload_with_checksum])

        self._logger.debug(
            "Received query response from Bravia on %s: %s",
            self.serial_port.name,
            dump_bytes_to_str(payload_without_checksum),
        )

        return payload_without_checksum

    def _get_write_request_response(self) -> None:
        raw_response = self.serial_port.read(3)
        expected_raw_response_len = 3
        if len(raw_response) != expected_raw_response_len:
            raise ValueError(
                (
                    f"Expected {expected_raw_response_len} bytes in Bravia response, got "
                    f"{len(raw_response)}"
                )
            )

        response_header = raw_response[0]
        if response_header != _BRAVIA_RESPONSE_HEADER_BYTE:
            raise ValueError(
                f"Received invalid response header from Bravia (expected "
                f"0x{_BRAVIA_RESPONSE_HEADER_BYTE:02X}, got 0x{response_header:02X})"
            )

        response_answer, checksum = raw_response[1:]

        _validate_payload_checksum(raw_response)
        _validate_response_answer_byte(response_answer)

        self._logger.debug(
            "Received Bravia response on %s: %s",
            self.serial_port.name,
            dump_bytes_to_str(raw_response),
        )


def _validate_function_byte(function_byte: int) -> None:
    if function_byte < 0 or function_byte > 255:
        raise ValueError(f"Invalid function (expected 0 <= function <= 255, got {function})")


def _calculate_checksum(payload: Iterable[int]) -> None:
    # Checksum is the LSB of the sum of the payload bytes
    return sum(payload) & 0xFF


def _validate_payload_checksum(payload_with_checksum: bytes) -> None:
    # Checksum is in last byte and is
    expected_checksum = _calculate_checksum(payload_with_checksum[:-1])
    actual_checksum = payload_with_checksum[-1]
    if expected_checksum != actual_checksum:
        raise RuntimeError(
            (
                "Received invalid response checksum from Bravia (expected "
                f"0x{expected_checksum:02X}, got 0x{actual_checksum:02X})"
            )
        )


def _validate_response_answer_byte(response_answer: int) -> None:
    if response_answer == 0x00:
        # No error
        return

    error_messages = {
        0x01: "Limit Over (Abnormal End - over maximum value)",
        0x02: "Limit Over (Abnormal End - under minimum value)",
        0x03: "Command Canceled (Abnormal End)",
        0x04: "Parse Error (Data Format Error)",
    }

    error_message = error_messages.get(response_answer)
    if error_message is None:
        error_message = f"Unrecognized response answer 0x{response_answer:02X}"

    raise RuntimeError(error_message)
