"""Light device for Sensio on/off control."""

from __future__ import annotations

from enum import Enum

from sensio_lib.device import Device
from sensio_lib.message import RsnMessage, TYPE_RELAY
from sensio_lib.socket_manager import SocketManager


class LightState(Enum):
    """Possible states for a light."""

    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"


class Light(Device):
    """Represents a Sensio light with on/off control.

    State is tracked optimistically on command, then confirmed or
    corrected by RSN messages from the hub.
    """

    def __init__(
        self,
        unique_id: str,
        name: str,
        zone_id: str,
        on_address: int,
        off_address: int,
        socket_manager: SocketManager,
        relay_address: int | None = None,
    ) -> None:
        super().__init__(unique_id, name, zone_id, socket_manager)
        self._on_address = on_address
        self._off_address = off_address
        self._relay_address = relay_address
        self._state = LightState.UNKNOWN

    @property
    def relay_address(self) -> int | None:
        """Return the relay feedback address, if known."""
        return self._relay_address

    @property
    def state(self) -> LightState:
        """Return the current state of the light."""
        return self._state

    @property
    def is_on(self) -> bool:
        """Return True if the light is considered on."""
        return self._state == LightState.ON

    async def turn_on(self) -> None:
        """Turn the light on."""
        await self._socket_manager.send_command(f"new_state {self._on_address} 0")
        self._state = LightState.ON

    async def turn_off(self) -> None:
        """Turn the light off."""
        await self._socket_manager.send_command(f"new_state {self._off_address} 0")
        self._state = LightState.OFF

    def handle_state_update(self, rsn: RsnMessage) -> None:
        """Update state from an RSN message.

        For relay devices (type 8), field_a indicates on/off (1 or 0).
        """
        if rsn.type_code == TYPE_RELAY:
            new_state = LightState.ON if rsn.field_a >= 1 else LightState.OFF
            if new_state != self._state:
                self._state = new_state
                self._fire_callbacks()

    def __repr__(self) -> str:
        return f"Light(name={self._name!r}, state={self._state.value})"