"""Asynchronous TCP Server implementing RESP2 on port 6379."""

import asyncio
import logging
from typing import Dict, Optional, Tuple
from pyredis.commands.registry import CommandContext, CommandRegistry, registry as default_registry
from pyredis.core.exceptions import CommandError, ProtocolError, PyRedisException
from pyredis.protocol.encoder import RespEncoder
from pyredis.protocol.parser import RespParser
from pyredis.protocol.types import SimpleString
from pyredis.server.client import ClientConnection
from pyredis.storage.store import DataStore

logger = logging.getLogger("pyredis.server")


class TcpServer:
    """High-concurrency asyncio TCP server handling RESP2 protocol connections."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 6379,
        store: Optional[DataStore] = None,
        command_registry: Optional[CommandRegistry] = None,
    ) -> None:
        self.host: str = host
        self.port: int = port
        self.store: DataStore = store if store is not None else DataStore()
        self.registry: CommandRegistry = (
            command_registry if command_registry is not None else default_registry
        )
        self._server: Optional[asyncio.Server] = None
        self._clients: Dict[str, ClientConnection] = {}
        self._running: bool = False
        self._total_connections: int = 0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def active_connections_count(self) -> int:
        return len(self._clients)

    @property
    def total_connections_count(self) -> int:
        return self._total_connections

    async def start(self) -> None:
        """Start accepting TCP connections."""
        self._server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port,
            reuse_address=True,
        )
        self._running = True
        self._total_connections = 0
        logger.info(f"PyRedis TCP Server listening on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Gracefully shut down the server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._clients.clear()
        logger.info("PyRedis TCP Server stopped")

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Per-client connection lifecycle handler."""
        peername = writer.get_extra_info("peername")
        addr: Tuple[str, int] = peername if peername else ("unknown", 0)
        client = ClientConnection(addr)
        self._clients[client.id] = client
        self._total_connections += 1
        logger.debug(f"Client connected: {client.peer} (id: {client.id})")

        parser = RespParser()

        try:
            while self._running:
                data = await reader.read(8192)
                if not data:
                    break  # Client closed socket cleanly (EOF)

                parser.feed(data)

                while True:
                    try:
                        cmd_tokens = parser.get_command()
                    except ProtocolError as e:
                        writer.write(RespEncoder.encode_error(f"Protocol error: {e}"))
                        await writer.drain()
                        break

                    if cmd_tokens is None:
                        # Need more chunks from network socket
                        break

                    if not cmd_tokens:
                        continue

                    raw_cmd = cmd_tokens[0].decode("utf-8", errors="replace").upper()
                    raw_args = cmd_tokens[1:]

                    # Handle QUIT connection termination
                    if raw_cmd == "QUIT":
                        writer.write(RespEncoder.encode(SimpleString("OK")))
                        await writer.drain()
                        return

                    # Handle modern Redis CLI initialization probes (COMMAND, COMMAND DOCS)
                    if raw_cmd == "COMMAND":
                        writer.write(RespEncoder.encode([]))
                        await writer.drain()
                        client.touch()
                        continue

                    # Prepare execution context
                    context = CommandContext(
                        store=self.store,
                        role=client.role,
                        client_id=client.id,
                        authenticated=client.authenticated,
                    )

                    # Execute command
                    try:
                        result = self.registry.execute(raw_cmd, raw_args, context)
                        response_bytes = RespEncoder.encode(result)
                    except PyRedisException as err:
                        response_bytes = RespEncoder.encode(err)
                    except Exception as err:
                        logger.exception(f"Unexpected error executing {raw_cmd}")
                        response_bytes = RespEncoder.encode_error(f"ERR {err}")

                    writer.write(response_bytes)
                    await writer.drain()
                    client.touch()

        except (ConnectionResetError, asyncio.IncompleteReadError):
            logger.debug(f"Client disconnected abruptly: {client.peer}")
        except Exception as e:
            logger.error(f"Connection handler error for {client.peer}: {e}")
        finally:
            self._clients.pop(client.id, None)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.debug(f"Client connection closed: {client.peer}")
