"""Async socket manager for communicating with the Sensio controller."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from sensio_lib.const import COMMAND_POSTFIX, COMMAND_PREFIX
from sensio_lib.exceptions import SensioCommandError, SensioConnectionError
from sensio_lib.message import extract_messages

logger = logging.getLogger(__name__)


class SocketManager:
    """Manages the TCP socket connection to the Sensio controller.

    Uses an asyncio lock to ensure commands are sent sequentially,
    matching the controller's sequential processing model.  A background
    read loop continuously reads incoming messages and dispatches them
    via a callback.
    """

    def __init__(self, server_address: str, port: int = 10023) -> None:
        self._server_address = server_address
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._read_task: asyncio.Task | None = None
        self._buffer: bytes = b""
        self._message_callback: Callable[[str], None] | None = None
        self._disconnect_callback: Callable[[], None] | None = None

    @property
    def connected(self) -> bool:
        """Return True if the socket connection is established."""
        return self._writer is not None and not self._writer.is_closing()

    def set_message_callback(self, callback: Callable[[str], None] | None) -> None:
        """Set the callback invoked for each received message."""
        self._message_callback = callback

    def set_disconnect_callback(self, callback: Callable[[], None] | None) -> None:
        """Set the callback invoked when the connection is lost."""
        self._disconnect_callback = callback

    async def connect(self) -> None:
        """Establish connection to the Sensio controller and start reading."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._server_address, self._port),
                timeout=15,
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise SensioConnectionError(
                f"Failed to connect to {self._server_address}:{self._port}: {err}"
            ) from err

        self._buffer = b""
        self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        """Continuously read from the socket and dispatch messages."""
        try:
            while self._reader and not self._reader.at_eof():
                data = await self._reader.read(4096)
                if not data:
                    break

                messages, self._buffer = extract_messages(data, self._buffer)
                for msg in messages:
                    if self._message_callback:
                        try:
                            self._message_callback(msg)
                        except Exception:
                            logger.exception("Error in message callback")
        except asyncio.CancelledError:
            return
        except (ConnectionResetError, OSError) as err:
            logger.warning("Connection lost: %s", err)
        except Exception:
            logger.exception("Unexpected error in read loop")

        logger.info("Read loop ended, connection to hub lost")
        if self._disconnect_callback:
            try:
                self._disconnect_callback()
            except Exception:
                logger.exception("Error in disconnect callback")

    async def send_command(self, command: str) -> None:
        """Send a command to the Sensio controller.

        Commands are serialized via a lock to ensure sequential execution.
        """
        if not self.connected:
            raise SensioConnectionError("Not connected to controller")

        async with self._lock:
            try:
                full_command = f"{COMMAND_PREFIX}{command}{COMMAND_POSTFIX}"
                self._writer.write(full_command.encode("utf-8"))
                await self._writer.drain()
            except OSError as err:
                raise SensioCommandError(
                    f"Failed to send command: {err}"
                ) from err

    async def close(self) -> None:
        """Close the socket connection and stop the read loop."""
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

        if self._writer and not self._writer.is_closing():
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError:
                pass
        self._reader = None
        self._writer = None
        self._buffer = b""