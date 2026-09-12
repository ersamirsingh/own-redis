"""Unit tests for RESP2 parser and encoder."""

import pytest
from pyredis.core.exceptions import ProtocolError
from pyredis.protocol import (
    Array,
    BulkString,
    Integer,
    RespEncoder,
    RespParser,
    SimpleError,
    SimpleString,
)


class TestRespEncoder:
    """Test RESP2 encoder."""

    def test_encode_simple_string(self) -> None:
        assert RespEncoder.encode_simple_string("OK") == b"+OK\r\n"
        assert RespEncoder.encode(SimpleString("PONG")) == b"+PONG\r\n"

    def test_encode_error(self) -> None:
        assert RespEncoder.encode_error("unknown command") == b"-ERR unknown command\r\n"
        assert RespEncoder.encode_error("Operation against key", code="WRONGTYPE") == b"-WRONGTYPE Operation against key\r\n"
        assert RespEncoder.encode(SimpleError("custom error", code="ERR")) == b"-ERR custom error\r\n"

    def test_encode_integer(self) -> None:
        assert RespEncoder.encode_integer(0) == b":0\r\n"
        assert RespEncoder.encode_integer(1000) == b":1000\r\n"
        assert RespEncoder.encode_integer(-42) == b":-42\r\n"
        assert RespEncoder.encode(Integer(77)) == b":77\r\n"
        assert RespEncoder.encode(123) == b":123\r\n"

    def test_encode_boolean(self) -> None:
        assert RespEncoder.encode(True) == b":1\r\n"
        assert RespEncoder.encode(False) == b":0\r\n"

    def test_encode_bulk_string(self) -> None:
        assert RespEncoder.encode_bulk_string("hello") == b"$5\r\nhello\r\n"
        assert RespEncoder.encode_bulk_string("") == b"$0\r\n\r\n"
        assert RespEncoder.encode_bulk_string(None) == b"$-1\r\n"
        assert RespEncoder.encode_bulk_string(b"binary\x00data") == b"$11\r\nbinary\x00data\r\n"
        assert RespEncoder.encode(None) == b"$-1\r\n"
        assert RespEncoder.encode("world") == b"$5\r\nworld\r\n"

    def test_encode_array(self) -> None:
        assert RespEncoder.encode_array(["SET", "key", "val"]) == (
            b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$3\r\nval\r\n"
        )
        assert RespEncoder.encode_array([]) == b"*0\r\n"
        assert RespEncoder.encode_array(None) == b"*-1\r\n"
        assert RespEncoder.encode(["ECHO", 123]) == b"*2\r\n$4\r\nECHO\r\n:123\r\n"


class TestRespParser:
    """Test RESP2 parser."""

    def test_parse_simple_string(self) -> None:
        parser = RespParser()
        parser.feed(b"+OK\r\n")
        val = parser.parse_next()
        assert isinstance(val, SimpleString)
        assert val.value == "OK"
        assert parser.is_empty()

    def test_parse_error(self) -> None:
        parser = RespParser()
        parser.feed(b"-ERR unknown command 'foobar'\r\n")
        val = parser.parse_next()
        assert isinstance(val, SimpleError)
        assert val.code == "ERR"
        assert val.message == "unknown command 'foobar'"

        parser.feed(b"-WRONGTYPE Operation against key\r\n")
        val2 = parser.parse_next()
        assert isinstance(val2, SimpleError)
        assert val2.code == "WRONGTYPE"
        assert val2.message == "Operation against key"

    def test_parse_integer(self) -> None:
        parser = RespParser()
        parser.feed(b":1000\r\n:-25\r\n:0\r\n")
        assert parser.parse_next() == Integer(1000)
        assert parser.parse_next() == Integer(-25)
        assert parser.parse_next() == Integer(0)
        assert parser.is_empty()

    def test_parse_bulk_string(self) -> None:
        parser = RespParser()
        parser.feed(b"$6\r\nfoobar\r\n$0\r\n\r\n$-1\r\n")
        assert parser.parse_next() == BulkString(b"foobar")
        assert parser.parse_next() == BulkString(b"")
        assert parser.parse_next() == BulkString(None)
        assert parser.is_empty()

    def test_parse_array(self) -> None:
        parser = RespParser()
        parser.feed(b"*2\r\n$3\r\nfoo\r\n$3\r\nbar\r\n*0\r\n*-1\r\n")
        arr = parser.parse_next()
        assert isinstance(arr, Array)
        assert arr.elements == [BulkString(b"foo"), BulkString(b"bar")]
        assert parser.parse_next() == Array([])
        assert parser.parse_next() == Array(None)
        assert parser.is_empty()

    def test_streaming_chunked_input(self) -> None:
        """Simulate single-byte chunk arrival from network socket."""
        parser = RespParser()
        raw = b"*2\r\n$4\r\nECHO\r\n$5\r\nhello\r\n"

        for b in raw[:-1]:
            parser.feed(bytes([b]))
            assert parser.parse_next() is None

        parser.feed(bytes([raw[-1]]))
        result = parser.parse_next()
        assert isinstance(result, Array)
        assert result.elements == [BulkString(b"ECHO"), BulkString(b"hello")]
        assert parser.is_empty()

    def test_pipelining(self) -> None:
        """Multiple commands in a single TCP read buffer."""
        parser = RespParser()
        parser.feed(b"+PING\r\n+PONG\r\n:42\r\n")
        assert parser.parse_next() == SimpleString("PING")
        assert parser.parse_next() == SimpleString("PONG")
        assert parser.parse_next() == Integer(42)
        assert parser.is_empty()

    def test_inline_command(self) -> None:
        parser = RespParser()
        parser.feed(b"PING\r\n")
        cmd = parser.get_command()
        assert cmd == [b"PING"]

        parser.feed(b"SET key val\r\n")
        cmd2 = parser.get_command()
        assert cmd2 == [b"SET", b"key", b"val"]

    def test_get_command_from_array(self) -> None:
        parser = RespParser()
        parser.feed(b"*3\r\n$3\r\nSET\r\n$4\r\nname\r\n$5\r\nAlice\r\n")
        cmd = parser.get_command()
        assert cmd == [b"SET", b"name", b"Alice"]

    def test_malformed_integer(self) -> None:
        parser = RespParser()
        parser.feed(b":notanumber\r\n")
        with pytest.raises(ProtocolError):
            parser.parse_next()

    def test_negative_length_error(self) -> None:
        parser = RespParser()
        parser.feed(b"$-2\r\n")
        with pytest.raises(ProtocolError):
            parser.parse_next()

    def test_bulk_string_missing_crlf(self) -> None:
        parser = RespParser()
        parser.feed(b"$3\r\nfooXX")
        with pytest.raises(ProtocolError):
            parser.parse_next()
