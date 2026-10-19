"""Dimmer device for Sensio brightness control.

Dimmers require a two-step command sequence to set brightness:
  1. set_value <dim_value_address> <0-100>   — write the target brightness
  2. new_state <dim_set_address> 0           — trigger the apply

State is tracked via RSN type 23 messages on the dim_value address
(M_D_<Device>_Val), where field_b carries the current brightness (0–100).
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from sensio_lib.const import RSN_TYPE_MEMORY
from sensio_lib.device import Device
from sensio_lib.socket_manager import SocketManager

if TYPE_CHECKING:
    from sensio_lib.message import RsnMessage


class DimmerState(Enum):
    """Possible states for a dimmer."""

    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"


class Dimmer(Device):
    """Represents a Sensio dimmer with brightness control.

    Sends a two-step command sequence to set brightness:
      1. ``set_value <value_address> <level>`` — writes target brightness
      2. ``new_state <set_address> 0``         — triggers the physical apply

    State is updated from RSN type 23 messages received on the
    ``dim_value`` address (M_D_<Device>_Val). field_b carries the
    current brightness (0.0–100.0).
    """

    def __init__(
        self,
        unique_id: str,
        name: str,
        zone_id: str,
        set_address: int,
        value_address: int,
        socket_manager: SocketManager,
    ) -> None:
        super().__init__(unique_id, name, zone_id, socket_manager)
        self._set_address = set_address
        self._value_address = value_address
        self._brightness: int | None = None
        self._state = DimmerState.UNKNOWN

    @property
    def state(self) -> DimmerState:
        """Return the current state of the dimmer."""
        return self._state

    @property
    def brightness(self) -> int | None:
        """Return the current brightness level (0–100), or None if unknown."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Return True if the dimmer is on (brightness > 0)."""
        return self._state == DimmerState.ON

    async def set_brightness(self, level: int) -> None:
        """Set the dimmer brightness.

        Clamps level to 0–100 and sends the two-step protocol sequence.
        State will be updated when the hub sends the RSN response.

        Args:
            level: Target brightness percentage (0–100).
        """
        level = max(0, min(100, level))
        await self._socket_manager.send_command(
            f"set_value {self._value_address} {level}"
        )
        await self._socket_manager.send_command(
            f"new_state {self._set_address} 0"
        )

    async def turn_on(self) -> None:
        """Turn the dimmer on.

        Restores to the last known brightness, or 100% if the current
        brightness is unknown or zero.
        """
        level = self._brightness if self._brightness else 100
        await self.set_brightness(level)

    async def turn_off(self) -> None:
        """Turn the dimmer off (set brightness to 0)."""
        await self.set_brightness(0)

    def update_from_rsn(self, message: RsnMessage) -> bool:
        """Update dimmer state from an RSN message.

        Processes type 23 (memory/value) messages on the dim_value
        address. field_b carries the current brightness (0.0–100.0).

        Returns True if the state or brightness actually changed.
        """
        if message.type_code != RSN_TYPE_MEMORY:
            return False

        new_brightness = round(message.field_b)
        new_state = DimmerState.ON if new_brightness > 0 else DimmerState.OFF

        if new_brightness == self._brightness and new_state == self._state:
            return False

        self._brightness = new_brightness
        self._state = new_state
        return True

    def __repr__(self) -> str:
        brightness_str = (
            f"{self._brightness}%" if self._brightness is not None else "unknown"
        )
        return (
            f"Dimmer(name={self._name!r}, state={self._state.value},"
            f" brightness={brightness_str})"
        )
