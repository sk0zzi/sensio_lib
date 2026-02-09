"""Async socket manager for communicating with the Sensio controller."""

import asyncio
import logging

from sensio_lib.const import COMMAND_POSTFIX, COMMAND_PREFIX
from sensio_lib.exceptions import SensioCommandError, SensioConnectionError

logger = logging.getLogger(__name__)


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
        if self._writer and not self._writer.is_closing():
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError:
                pass
        self._reader = None
        self._writer = None