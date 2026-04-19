"""Dimmer device for Sensio brightness control."""

from __future__ import annotations

from sensio_lib.device import Device
from sensio_lib.message import RsnMessage, TYPE_DIMMER
from sensio_lib.socket_manager import SocketManager

DEFAULT_BRIGHTNESS = 100


class Dimmer(Device):
    """Represents a Sensio dimmer with brightness control.

    Brightness is tracked on a 0–100 scale. State is updated optimistically
    on command, then confirmed or corrected by RSN type 21 messages.
    """

    def __init__(
        self,
        unique_id: str,
        name: str,
        zone_id: str,
        dim_set_address: int,
        socket_manager: SocketManager,
        dim_value_address: int | None = None,
        device_address: int | None = None,
    ) -> None:
        super().__init__(unique_id, name, zone_id, socket_manager)
        self._dim_set_address = dim_set_address
        self._dim_value_address = dim_value_address
        self._device_address = device_address
        self._brightness: int = 0
        self._last_nonzero_brightness: int = DEFAULT_BRIGHTNESS

    @property
    def dim_set_address(self) -> int:
        """Return the command address for setting brightness."""
        return self._dim_set_address

    @property
    def dim_value_address(self) -> int | None:
        """Return the feedback address for brightness value, if known."""
        return self._dim_value_address

    @property
    def device_address(self) -> int | None:
        """Return the device state feedback address (RSN type 21), if known."""
        return self._device_address

    @property
    def brightness(self) -> int:
        """Return the current brightness (0–100)."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Return True if the dimmer is on (brightness > 0)."""
        return self._brightness > 0

    async def set_brightness(self, value: int) -> None:
        """Set the dimmer brightness (0–100)."""
        value = max(0, min(100, value))
        await self._socket_manager.send_command(
            f"new_state {self._dim_set_address} {value}"
        )
        self._brightness = value
        if value > 0:
            self._last_nonzero_brightness = value
        self._fire_callbacks()

    async def turn_on(self) -> None:
        """Turn the dimmer on at the last known brightness."""
        await self.set_brightness(self._last_nonzero_brightness)

    async def turn_off(self) -> None:
        """Turn the dimmer off."""
        await self.set_brightness(0)

    def handle_state_update(self, rsn: RsnMessage) -> None:
        """Update brightness from an RSN message.

        For dimmer devices (type 21):
        - field_a = current level (0–100)
        - field_b = target level (0–100)

        We use field_b (target) as the authoritative brightness since it
        represents the final desired state, even while the dimmer is ramping.
        """
        if rsn.type_code == TYPE_DIMMER:
            new_brightness = int(rsn.field_b)
            new_brightness = max(0, min(100, new_brightness))
            if new_brightness != self._brightness:
                self._brightness = new_brightness
                if new_brightness > 0:
                    self._last_nonzero_brightness = new_brightness
                self._fire_callbacks()

    def __repr__(self) -> str:
        return f"Dimmer(name={self._name!r}, brightness={self._brightness})"
