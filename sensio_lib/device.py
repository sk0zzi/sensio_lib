"""Base device class for Sensio devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sensio_lib.socket_manager import SocketManager

if TYPE_CHECKING:
    from sensio_lib.message import RsnMessage


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

    def update_from_rsn(self, message: RsnMessage) -> bool:
        """Update device state from an RSN message.

        Returns True if the state actually changed.
        Subclasses override this to handle their specific RSN type codes.
        """
        return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self._name!r}, id={self._unique_id!r})"
