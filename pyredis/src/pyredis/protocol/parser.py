"""RESP2 Streaming Protocol Parser."""

from typing import Any, List, Optional, Tuple, Union
from pyredis.core.exceptions import ProtocolError
from pyredis.protocol.types import (
    Array,
    BulkString,
    Integer,
    RespValue,
    SimpleError,
    SimpleString,
)

CRLF = b"\r\n"


class RespParser:
    """Streaming, zero-copy buffer parser for RESP2 protocol."""

    def __init__(self) -> None:
        self._buffer: bytearray = bytearray()
        self._pos: int = 0

    def feed(self, data: bytes) -> None:
        """Append incoming network bytes to parser buffer."""
        # Compact buffer if read position has consumed significant data
        if self._pos > 65536:
            self._buffer = self._buffer[self._pos:]
            self._pos = 0
        self._buffer.extend(data)

    def is_empty(self) -> bool:
        """Check if buffer has no remaining bytes to parse."""
        return self._pos >= len(self._buffer)

    def remaining_bytes(self) -> int:
        """Return number of unconsumed bytes in buffer."""
        return len(self._buffer) - self._pos

    def parse_next(self) -> Optional[RespValue]:
        """Attempt to parse next RESP value. Returns None if more data is needed."""
        if self._pos >= len(self._buffer):
            return None

        saved_pos = self._pos
        try:
            val, consumed = self._parse_value(self._pos)
            if consumed == 0:
                self._pos = saved_pos
                return None
            self._pos += consumed
            return val
        except ProtocolError:
            raise
        except Exception as e:
            self._pos = saved_pos
            raise ProtocolError(f"Protocol parsing error: {e}") from e

    def _read_line(self, start: int) -> Tuple[Optional[bytes], int]:
        """Find CRLF starting from start. Returns (line_bytes_without_crlf, total_bytes_consumed)."""
        idx = self._buffer.find(CRLF, start)
        if idx == -1:
            return None, 0
        line = bytes(self._buffer[start:idx])
        consumed = (idx - start) + 2  # include \r\n
        return line, consumed

    def _parse_value(self, start: int) -> Tuple[Optional[RespValue], int]:
        """Parse single RESP value starting from index start."""
        if start >= len(self._buffer):
            return None, 0

        prefix = chr(self._buffer[start])

        if prefix == "+":
            line, consumed = self._read_line(start + 1)
            if line is None:
                return None, 0
            return SimpleString(line.decode("utf-8", errors="replace")), consumed + 1

        elif prefix == "-":
            line, consumed = self._read_line(start + 1)
            if line is None:
                return None, 0
            text = line.decode("utf-8", errors="replace")
            code, _, message = text.partition(" ")
            if not message:
                message = code
                code = "ERR"
            return SimpleError(message=message, code=code), consumed + 1

        elif prefix == ":":
            line, consumed = self._read_line(start + 1)
            if line is None:
                return None, 0
            try:
                num = int(line)
            except ValueError:
                raise ProtocolError(f"Invalid integer: {line!r}")
            return Integer(num), consumed + 1

        elif prefix == "$":
            # Bulk string
            len_line, consumed = self._read_line(start + 1)
            if len_line is None:
                return None, 0
            try:
                length = int(len_line)
            except ValueError:
                raise ProtocolError(f"Invalid bulk string length: {len_line!r}")

            if length == -1:
                # Null bulk string
                return BulkString(None), consumed + 1

            if length < -1:
                raise ProtocolError(f"Negative bulk string length: {length}")

            data_start = start + 1 + consumed
            data_end = data_start + length

            # Need length bytes + \r\n (2 bytes)
            if len(self._buffer) < data_end + 2:
                return None, 0

            if self._buffer[data_end : data_end + 2] != CRLF:
                raise ProtocolError("Bulk string does not terminate with CRLF")

            payload = bytes(self._buffer[data_start:data_end])
            total_consumed = 1 + consumed + length + 2
            return BulkString(payload), total_consumed

        elif prefix == "*":
            # Array
            len_line, consumed = self._read_line(start + 1)
            if len_line is None:
                return None, 0
            try:
                count = int(len_line)
            except ValueError:
                raise ProtocolError(f"Invalid array length: {len_line!r}")

            if count == -1:
                return Array(None), consumed + 1

            if count < -1:
                raise ProtocolError(f"Negative array length: {count}")

            elements: List[Any] = []
            curr = start + 1 + consumed

            for _ in range(count):
                elem, elem_consumed = self._parse_value(curr)
                if elem_consumed == 0:
                    return None, 0
                elements.append(elem)
                curr += elem_consumed

            return Array(elements), curr - start

        else:
            # Inline command support (e.g. "PING\r\n", "SET k v\r\n")
            line, consumed = self._read_line(start)
            if line is None:
                return None, 0
            parts = [BulkString(part) for part in line.split() if part]
            if not parts:
                return None, consumed
            return Array(parts), consumed

    def get_command(self) -> Optional[List[bytes]]:
        """Convenience method: parses next item and converts Array of BulkStrings into List[bytes]."""
        parsed = self.parse_next()
        if parsed is None:
            return None

        if isinstance(parsed, Array):
            if parsed.elements is None:
                return None
            result: List[bytes] = []
            for elem in parsed.elements:
                if isinstance(elem, BulkString):
                    result.append(elem.value if elem.value is not None else b"")
                elif isinstance(elem, SimpleString):
                    result.append(elem.value.encode("utf-8"))
                elif isinstance(elem, Integer):
                    result.append(str(elem.value).encode("utf-8"))
                elif isinstance(elem, bytes):
                    result.append(elem)
                elif isinstance(elem, str):
                    result.append(elem.encode("utf-8"))
                else:
                    result.append(str(elem).encode("utf-8"))
            return result

        if isinstance(parsed, SimpleString):
            return [parsed.value.encode("utf-8")]

        if isinstance(parsed, BulkString) and parsed.value is not None:
            return [parsed.value]

        return None
