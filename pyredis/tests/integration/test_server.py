"""Integration tests for TCP server with real network socket connections."""

import asyncio
import pytest
from pyredis.protocol.encoder import RespEncoder
from pyredis.protocol.parser import RespParser
from pyredis.protocol.types import Array, BulkString, Integer, SimpleString
from pyredis.server.tcp import TcpServer
from pyredis.storage.store import DataStore


@pytest.fixture
async def tcp_server():
    """Start an isolated TCP server on localhost on an ephemeral port."""
    store = DataStore()
    # Port 0 lets OS assign free port
    server = TcpServer(host="127.0.0.1", port=0, store=store)
    await server.start()

    # Get the assigned port from the sockets
    assert server._server is not None
    sockets = server._server.sockets
    assert len(sockets) > 0
    assigned_port = sockets[0].getsockname()[1]

    yield "127.0.0.1", assigned_port, store

    await server.stop()


@pytest.mark.asyncio
async def test_tcp_server_ping_pong(tcp_server) -> None:
    host, port, _ = tcp_server
    reader, writer = await asyncio.open_connection(host, port)

    # Send PING
    writer.write(RespEncoder.encode_array(["PING"]))
    await writer.drain()

    # Read response
    data = await reader.read(1024)
    parser = RespParser()
    parser.feed(data)
    resp = parser.parse_next()

    assert resp == SimpleString("PONG")

    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_tcp_server_set_get_pipeline(tcp_server) -> None:
    host, port, _ = tcp_server
    reader, writer = await asyncio.open_connection(host, port)

    # Send pipelined commands: SET k v, GET k, INCR c, INCR c
    payload = b"".join([
        RespEncoder.encode_array(["SET", "user:99", "Alice"]),
        RespEncoder.encode_array(["GET", "user:99"]),
        RespEncoder.encode_array(["INCR", "visits"]),
        RespEncoder.encode_array(["INCR", "visits"]),
    ])
    writer.write(payload)
    await writer.drain()

    parser = RespParser()
    responses = []

    while len(responses) < 4:
        data = await reader.read(1024)
        if not data:
            break
        parser.feed(data)
        while True:
            item = parser.parse_next()
            if item is None:
                break
            responses.append(item)

    assert responses[0] == SimpleString("OK")
    assert responses[1] == BulkString(b"Alice")
    assert responses[2] == Integer(1)
    assert responses[3] == Integer(2)

    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_tcp_server_quit(tcp_server) -> None:
    host, port, _ = tcp_server
    reader, writer = await asyncio.open_connection(host, port)

    writer.write(RespEncoder.encode_array(["QUIT"]))
    await writer.drain()

    data = await reader.read(1024)
    parser = RespParser()
    parser.feed(data)
    assert parser.parse_next() == SimpleString("OK")

    # Socket should be closed by server on QUIT
    data_after = await reader.read(1024)
    assert data_after == b""

    writer.close()
    await writer.wait_closed()
