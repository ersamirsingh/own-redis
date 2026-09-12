"""Asynchronous TCP Server implementing RESP2 on port 6379."""

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Tuple
from pyredis.commands.registry import CommandContext, CommandRegistry, registry as default_registry
from pyredis.core.exceptions import CommandError, ProtocolError, PyRedisException
from pyredis.events import Event, EventBus, EventType, event_bus as default_event_bus
from pyredis.metrics import MetricsCollector, metrics_collector as default_metrics
from pyredis.protocol.encoder import RespEncoder
from pyredis.protocol.parser import RespParser
from pyredis.protocol.types import SimpleString
from pyredis.server.client import ClientConnection
from pyredis.storage.store import DataStore
from pyredis.tracing import Tracer, tracer as default_tracer

logger = logging.getLogger("pyredis.server")


class TcpServer:
    """High-concurrency asyncio TCP server handling RESP2 protocol connections."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 6379,
        store: Optional[DataStore] = None,
        command_registry: Optional[CommandRegistry] = None,
        aof: Optional[Any] = None,
        snapshot: Optional[Any] = None,
        metrics: Optional[MetricsCollector] = None,
        tracer: Optional[Tracer] = None,
        bus: Optional[EventBus] = None,
    ) -> None:
        self.host: str = host
        self.port: int = port
        self.store: DataStore = store if store is not None else DataStore()
        self.registry: CommandRegistry = (
            command_registry if command_registry is not None else default_registry
        )
        self.aof = aof
        self.snapshot = snapshot
        self.metrics: MetricsCollector = metrics if metrics is not None else default_metrics
        self.tracer: Tracer = tracer if tracer is not None else default_tracer
        self.bus: EventBus = bus if bus is not None else default_event_bus
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

                    # Initialize distributed trace
                    trace = self.tracer.start_trace(
                        raw_cmd,
                        raw_args,
                        client_id=client.id,
                        client_ip=client.peer,
                    )
                    cmd_start_time = time.monotonic()

                    # Prepare execution context
                    context = CommandContext(
                        store=self.store,
                        role=client.role,
                        client_id=client.id,
                        authenticated=client.authenticated,
                        aof=self.aof,
                        snapshot=self.snapshot,
                        metrics=self.metrics,
                        tracer=self.tracer,
                    )

                    # Execute command with stage spans
                    status = "OK"
                    err_msg = None
                    try:
                        with self.tracer.span(trace, "storage"):
                            result = self.registry.execute(raw_cmd, raw_args, context)
                        response_bytes = RespEncoder.encode(result)

                        # If mutating, append to AOF and publish domain event
                        cmd_def = self.registry.get_definition(raw_cmd)
                        first_key = raw_args[0].decode("utf-8", errors="ignore") if raw_args else None

                        if cmd_def and cmd_def.is_mutation:
                            if self.aof:
                                with self.tracer.span(trace, "aof"):
                                    self.aof.append(raw_cmd, raw_args)

                            # Emit domain event
                            ev_type = EventType.KEY_DELETED if raw_cmd == "DEL" else EventType.KEY_UPDATED
                            self.bus.publish(Event(
                                type=ev_type,
                                key=first_key,
                                actor=f"client:{client.id}",
                                metadata={"command": raw_cmd},
                            ))

                    except PyRedisException as err:
                        status = "ERROR"
                        err_msg = str(err)
                        response_bytes = RespEncoder.encode(err)
                    except Exception as err:
                        status = "ERROR"
                        err_msg = str(err)
                        logger.exception(f"Unexpected error executing {raw_cmd}")
                        response_bytes = RespEncoder.encode_error(f"ERR {err}")

                    # Network response write span
                    with self.tracer.span(trace, "network_write"):
                        writer.write(response_bytes)
                        await writer.drain()

                    # Finalize telemetry
                    duration_ms = (time.monotonic() - cmd_start_time) * 1000.0
                    trace.finish(status=status, error_message=err_msg)
                    self.tracer.record_trace(trace)

                    first_key = raw_args[0].decode("utf-8", errors="ignore") if raw_args else None
                    self.metrics.record_command(
                        raw_cmd,
                        duration_ms,
                        key=first_key,
                        args=trace.sanitized_args,
                        client_peer=client.peer,
                    )

                    if duration_ms >= self.metrics.slow_threshold_ms:
                        self.bus.publish(Event(
                            type=EventType.SLOW_COMMAND,
                            key=first_key,
                            metadata={"command": raw_cmd, "duration_ms": duration_ms},
                        ))

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
