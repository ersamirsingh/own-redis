"""RESP (REdis Serialization Protocol) data types."""

from dataclasses import dataclass
from typing import Any, Optional, Union


@dataclass(frozen=True)
class SimpleString:
    """RESP Simple String: non-binary-safe string without CR or LF."""
    value: str


@dataclass(frozen=True)
class SimpleError:
    """RESP Error: non-binary-safe error message."""
    message: str
    code: str = "ERR"

    def __str__(self) -> str:
        return f"{self.code} {self.message}" if self.code else self.message


@dataclass(frozen=True)
class Integer:
    """RESP Integer: signed 64-bit integer."""
    value: int


@dataclass(frozen=True)
class BulkString:
    """RESP Bulk String: binary-safe string with length prefix, or None for null."""
    value: Optional[bytes]


@dataclass(frozen=True)
class Array:
    """RESP Array: ordered collection of RESP values, or None for null."""
    elements: Optional[list[Any]]


# Union of all deserialized RESP types
RespValue = Union[SimpleString, SimpleError, Integer, BulkString, Array, None]
