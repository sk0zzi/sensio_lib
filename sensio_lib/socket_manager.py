"""Async socket manager for communicating with the Sensio controller."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from sensio_lib.const import COMMAND_POSTFIX, COMMAND_PREFIX
from sensio_lib.exceptions import SensioCommandError, SensioConnectionError

logger = logging.getLogger(__name__)

_RECONNECT_MIN_SECONDS = 5
_RECONNECT_MAX_SECONDS = 300


class SocketManager:
    """Manages the TCP socket connection to the Sensio controller.

    Uses an asyncio lock to ensure commands are sent sequentially,
    matching the controller's sequential processing model.
    """

    def __init__(self, server_address: str, port: int = 10023) -> None:
        self._server_address = server_address
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._listener_task: asyncio.Task | None = None
        self._start_byte = COMMAND_PREFIX.encode()
        self._end_byte = COMMAND_POSTFIX.encode()

    @property
    def connected(self) -> bool:
        """Return True if the socket connection is established."""
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        """Establish connection to the Sensio controller."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._server_address, self._port),
                timeout=15,
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise SensioConnectionError(
                f"Failed to connect to {self._server_address}:{self._port}: {err}"
            ) from err

    async def start_listener(
        self,
        callback: Callable[[str], None],
        *,
        auto_reconnect: bool = True,
    ) -> None:
        """Start a background task that reads frames and invokes the callback.

        The listener continuously reads \\x01...\\x02 frames from the hub
        and calls ``callback(raw_content)`` for each one. When
        ``auto_reconnect`` is True, a dropped connection is automatically
        re-established with exponential backoff.

        Args:
            callback: Called with the raw string content of each frame.
            auto_reconnect: Whether to automatically reconnect on EOF or error.
        """
        if self._listener_task is not None:
            logger.warning("Listener already running, stopping existing one")
            await self.stop_listener()

        self._listener_task = asyncio.ensure_future(
            self._listener_loop(callback, auto_reconnect=auto_reconnect)
        )

    async def stop_listener(self) -> None:
        """Stop the background listener task."""
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

    async def _close_socket(self) -> None:
        """Close the underlying stream writer if open."""
        if self._writer and not self._writer.is_closing():
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError:
                pass
        self._reader = None
        self._writer = None

    async def _listener_loop(
        self,
        callback: Callable[[str], None],
        *,
        auto_reconnect: bool = True,
    ) -> None:
        """Internal loop that reads frames and dispatches to the callback."""
        if not self._reader:
            logger.error("Cannot start listener: not connected")
            return

        buf = b""
        backoff = _RECONNECT_MIN_SECONDS

        try:
            while True:
                try:
                    if self._reader is None:
                        await self.connect()
                        buf = b""
                        backoff = _RECONNECT_MIN_SECONDS
                        logger.info(
                            "Reconnected to Sensio controller at %s:%d",
                            self._server_address,
                            self._port,
                        )

                    data = await self._reader.read(4096)
                    if not data:
                        if not auto_reconnect:
                            logger.info("Hub connection closed (EOF)")
                            break
                        raise ConnectionResetError("Hub closed the connection (EOF)")

                    buf += data
                    while self._start_byte in buf and self._end_byte in buf:
                        start = buf.index(self._start_byte)
                        # Discard any bytes before the start marker.
                        buf = buf[start:]
                        end = buf.index(self._end_byte)
                        content = buf[1:end].decode(
                            "utf-8", errors="replace"
                        )
                        buf = buf[end + 1:]
                        try:
                            callback(content)
                        except Exception:
                            logger.exception("Error in listener callback")
                except (OSError, SensioConnectionError) as err:
                    if not auto_reconnect:
                        logger.error("Listener connection error: %s", err)
                        break
                    logger.warning(
                        "Lost connection to hub (%s); retrying in %ds",
                        err,
                        backoff,
                    )
                    await self._close_socket()
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, _RECONNECT_MAX_SECONDS)
        except asyncio.CancelledError:
            logger.debug("Listener task cancelled")
            raise

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
        """Close the socket connection."""
        await self.stop_listener()
        await self._close_socket()