"""Light device for Sensio on/off control."""

from enum import Enum

from sensio_lib.device import Device
from sensio_lib.socket_manager import SocketManager


class LightState(Enum):
    """Possible states for a light."""

    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"


class Light(Device):
    """Represents a Sensio light with on/off control.

    State is tracked optimistically (assumed to succeed after command).
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
        """Return the current optimistic state of the light."""
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

    def __repr__(self) -> str:
        return f"Light(name={self._name!r}, state={self._state.value})"