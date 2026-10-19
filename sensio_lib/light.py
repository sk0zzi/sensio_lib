"""Light device for Sensio on/off control."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from sensio_lib.const import RSN_TYPE_RELAY
from sensio_lib.device import Device
from sensio_lib.socket_manager import SocketManager

if TYPE_CHECKING:
    from sensio_lib.message import RsnMessage


class LightState(Enum):
    """Possible states for a light."""

    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"


class Light(Device):
    """Represents a Sensio light with on/off control.

    State is updated from RSN messages received by the hub listener.
    """

    def __init__(
        self,
        unique_id: str,
        name: str,
        zone_id: str,
        on_address: int,
        off_address: int,
        socket_manager: SocketManager,
    ) -> None:
        super().__init__(unique_id, name, zone_id, socket_manager)
        self._on_address = on_address
        self._off_address = off_address
        self._state = LightState.UNKNOWN

    @property
    def state(self) -> LightState:
        """Return the current state of the light."""
        return self._state

    @property
    def is_on(self) -> bool | None:
        """Return True if the light is on, False if off, or None if unknown."""
        if self._state == LightState.UNKNOWN:
            return None
        return self._state == LightState.ON

    async def turn_on(self) -> None:
        """Turn the light on.

        State will be updated when the hub sends the RSN response.
        """
        await self._socket_manager.send_command(f"new_state {self._on_address} 0")

    async def turn_off(self) -> None:
        """Turn the light off.

        State will be updated when the hub sends the RSN response.
        """
        await self._socket_manager.send_command(f"new_state {self._off_address} 0")

    def update_from_rsn(self, message: RsnMessage) -> bool:
        """Update light state from an RSN message.

        Processes type 8 (relay) messages.
        field_a > 0 means ON, 0 means OFF.

        Returns True if the state actually changed.
        """
        if message.type_code != RSN_TYPE_RELAY:
            return False

        new_state = LightState.ON if message.field_a > 0 else LightState.OFF
        if new_state == self._state:
            return False

        self._state = new_state
        return True

    def __repr__(self) -> str:
        return f"Light(name={self._name!r}, state={self._state.value})"