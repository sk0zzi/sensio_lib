"""Thermostat device for Sensio heated floor / temperature control.

Thermostats require a two-step command sequence to set target temperature:
  1. set_value <therm_sc_address> <mode_index> <temp> — write target setpoint
  2. new_state <set_heat_address> 0                   — trigger the apply

State is tracked via:
  - RSN/SSN type 7 messages on the Thermostat address (TH_<Name>), where:
      field_a = heating status (1 = heating, 0 = idle)
      field_b = target temperature (°C)
      field_c = current temperature (°C)
  - RSN/SSN type 23 messages on the ThermCur address (M_<Name>_Cur), where:
      field_b = active mode index (0 = Comfort, 1 = Saving, 2 = Frost Protect)
  - RSN/SSN type 8 messages on the HeatRelay address (R_<Name>), where:
      field_a = relay state (1 = heating, 0 = idle)
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from sensio_lib.const import (
    RSN_TYPE_MEMORY,
    RSN_TYPE_RELAY,
    RSN_TYPE_THERMOSTAT,
)
from sensio_lib.device import Device
from sensio_lib.socket_manager import SocketManager

if TYPE_CHECKING:
    from sensio_lib.message import RsnMessage


class ThermostatState(Enum):
    """Possible heating states for a thermostat."""

    HEATING = "heating"
    IDLE = "idle"
    UNKNOWN = "unknown"


class Thermostat(Device):
    """Represents a Sensio heated floor thermostat."""

    TEMP_STEP: float = 0.5

    def __init__(
        self,
        unique_id: str,
        name: str,
        zone_id: str,
        thermostat_address: int,
        therm_sc_address: int,
        set_heat_address: int,
        socket_manager: SocketManager,
        therm_cur_address: int | None = None,
        relay_address: int | None = None,
        min_temp: float = 5.0,
        max_temp: float = 35.0,
        zone_name: str | None = None,
    ) -> None:
        super().__init__(unique_id, name, zone_id, socket_manager, zone_name=zone_name)
        self._thermostat_address = thermostat_address
        self._therm_sc_address = therm_sc_address
        self._set_heat_address = set_heat_address
        self._therm_cur_address = therm_cur_address
        self._relay_address = relay_address
        self._min_temp = min_temp
        self._max_temp = max_temp

        self._state = ThermostatState.UNKNOWN
        self._current_temperature: float | None = None
        self._target_temperature: float | None = None
        self._active_mode_index: int = 0

    @property
    def state(self) -> ThermostatState:
        """Return the current heating state of the thermostat."""
        return self._state

    @property
    def is_heating(self) -> bool | None:
        """Return True if actively heating, False if idle, or None if unknown."""
        if self._state == ThermostatState.UNKNOWN:
            return None
        return self._state == ThermostatState.HEATING

    @property
    def current_temperature(self) -> float | None:
        """Return the current measured temperature (°C), or None if unknown."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the target setpoint temperature (°C), or None if unknown."""
        return self._target_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum allowed setpoint temperature (°C)."""
        return self._min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum allowed setpoint temperature (°C)."""
        return self._max_temp

    @property
    def temp_step(self) -> float:
        """Return the temperature step increment (°C)."""
        return self.TEMP_STEP

    async def set_temperature(self, temperature: float) -> None:
        """Set the target temperature in 0.5°C increments.

        Clamps temperature to [min_temp, max_temp], rounds to the nearest
        0.5°C, and sends the two-step protocol sequence to the active mode
        slot in ThermSc followed by the SetHeat trigger.
        """
        clamped = max(self._min_temp, min(self._max_temp, float(temperature)))
        rounded = round(clamped * 2) / 2
        await self._socket_manager.send_command(
            f"set_value {self._therm_sc_address} {self._active_mode_index} {rounded:g}"
        )
        await self._socket_manager.send_command(
            f"new_state {self._set_heat_address} 0"
        )

    async def query_state(self) -> None:
        """Query the hub for the current thermostat mode and temperature state."""
        if self._therm_cur_address is not None:
            await self._socket_manager.send_command(
                f"d_obj {self._therm_cur_address}"
            )
        await self._socket_manager.send_command(
            f"d_obj {self._thermostat_address}"
        )

    def update_from_rsn(self, message: RsnMessage) -> bool:
        """Update thermostat state from an RSN or SSN message.

        Returns True if the state, current_temperature, or target_temperature
        changed.
        """
        if message.type_code == RSN_TYPE_THERMOSTAT:
            new_state = (
                ThermostatState.HEATING
                if message.field_a > 0
                else ThermostatState.IDLE
            )
            new_target = message.field_b
            new_current = message.field_c

            if (
                new_state == self._state
                and new_target == self._target_temperature
                and new_current == self._current_temperature
            ):
                return False

            self._state = new_state
            self._target_temperature = new_target
            self._current_temperature = new_current
            return True

        if message.type_code == RSN_TYPE_RELAY:
            new_state = (
                ThermostatState.HEATING
                if message.field_a > 0
                else ThermostatState.IDLE
            )
            if new_state == self._state:
                return False
            self._state = new_state
            return True

        if (
            message.type_code == RSN_TYPE_MEMORY
            and message.address == self._therm_cur_address
        ):
            mode_idx = int(round(message.field_b))
            if 0 <= mode_idx <= 2:
                self._active_mode_index = mode_idx
            return False

        return False

    def __repr__(self) -> str:
        cur_str = (
            f"{self._current_temperature:.1f}°C"
            if self._current_temperature is not None
            else "unknown"
        )
        tgt_str = (
            f"{self._target_temperature:.1f}°C"
            if self._target_temperature is not None
            else "unknown"
        )
        return (
            f"Thermostat(name={self._name!r}, state={self._state.value},"
            f" current={cur_str}, target={tgt_str})"
        )
