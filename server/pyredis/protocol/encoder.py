"""RESP2 Protocol Encoder."""

from typing import Any, Optional, Sequence, Union
from pyredis.protocol.types import (
    Array,
    BulkString,
    Integer,
    SimpleError,
    SimpleString,
)

CRLF = b"\r\n"


class RespEncoder:
    """Serializes Python and RESP types into RESP2 wire format."""

    @staticmethod
    def encode_simple_string(val: str) -> bytes:
        """Encode simple string: +<string>\r\n."""
        return f"+{val}\r\n".encode("utf-8")

    @staticmethod
    def encode_error(message: str, code: str = "ERR") -> bytes:
        """Encode error: -<code message>\r\n."""
        prefix = f"{code} " if code and not message.startswith(f"{code} ") else ""
        return f"-{prefix}{message}\r\n".encode("utf-8")

    @staticmethod
    def encode_integer(val: int) -> bytes:
        """Encode signed 64-bit integer: :<number>\r\n."""
        return f":{val}\r\n".encode("utf-8")

    @staticmethod
    def encode_bulk_string(val: Optional[Union[str, bytes]]) -> bytes:
        """Encode binary-safe bulk string: $<length>\r\n<bytes>\r\n or $-1\r\n."""
        if val is None:
            return b"$-1\r\n"
        if isinstance(val, str):
            raw = val.encode("utf-8")
        else:
            raw = val
        return f"${len(raw)}\r\n".encode("utf-8") + raw + CRLF

    @classmethod
    def encode_array(cls, elements: Optional[Sequence[Any]]) -> bytes:
        """Encode array: *<length>\r\n<elem1>...<elemN> or *-1\r\n."""
        if elements is None:
            return b"*-1\r\n"
        parts = [f"*{len(elements)}\r\n".encode("utf-8")]
        for item in elements:
            parts.append(cls.encode(item))
        return b"".join(parts)

    @classmethod
    def encode(cls, value: Any) -> bytes:
        """Dynamically encode any supported Python or RESP value to bytes."""
        if value is None:
            return b"$-1\r\n"
        if isinstance(value, SimpleString):
            return cls.encode_simple_string(value.value)
        if isinstance(value, SimpleError):
            return cls.encode_error(value.message, value.code)
        if isinstance(value, Exception):
            msg = str(value)
            # Preserve existing Redis error codes if present (e.g. WRONGTYPE)
            if " " in msg:
                code, rest = msg.split(" ", 1)
                if code.isupper():
                    return cls.encode_error(rest, code)
            return cls.encode_error(msg)
        if isinstance(value, Integer):
            return cls.encode_integer(value.value)
        if isinstance(value, bool):
            # In Redis, booleans are represented as integers (1 or 0)
            return cls.encode_integer(1 if value else 0)
        if isinstance(value, int):
            return cls.encode_integer(value)
        if isinstance(value, BulkString):
            return cls.encode_bulk_string(value.value)
        if isinstance(value, (str, bytes)):
            return cls.encode_bulk_string(value)
        if isinstance(value, Array):
            return cls.encode_array(value.elements)
        if isinstance(value, (list, tuple)):
            return cls.encode_array(value)
        if isinstance(value, set):
            return cls.encode_array(sorted(list(value), key=lambda x: str(x)))
        if isinstance(value, dict):
            # Flatten dict to [k1, v1, k2, v2, ...]
            flat = []
            for k, v in value.items():
                flat.append(k)
                flat.append(v)
            return cls.encode_array(flat)

        # Fallback: convert to string and encode as bulk string
        return cls.encode_bulk_string(str(value))
