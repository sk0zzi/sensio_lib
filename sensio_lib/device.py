"""Base device class for Sensio devices."""

from __future__ import annotations

from collections.abc import Callable

from sensio_lib.socket_manager import SocketManager


class Device:
    """Base class for all Sensio controllable devices."""

    def __init__(
        self,
        unique_id: str,
        name: str,
        zone_id: str,
        socket_manager: SocketManager,
    ) -> None:
        self._unique_id = unique_id
        self._name = name
        self._zone_id = zone_id
        self._socket_manager = socket_manager
        self._callbacks: list[Callable[[], None]] = []

    @property
    def unique_id(self) -> str:
        """Return the unique identifier for this device."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the display name of this device."""
        return self._name

    @property
    def zone_id(self) -> str:
        """Return the zone ID this device belongs to."""
        return self._zone_id

    def set_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be invoked when device state changes."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove a previously registered callback."""
        self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    def _fire_callbacks(self) -> None:
        """Notify all registered callbacks of a state change."""
        for callback in self._callbacks:
            callback()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self._name!r}, id={self._unique_id!r})"
