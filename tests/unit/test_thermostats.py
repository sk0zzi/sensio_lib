"""Tests for the Thermostat device class."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sensio_lib.message import RsnMessage
from sensio_lib.thermostat import Thermostat, ThermostatState


def _make_socket_manager():
    """Return a mock SocketManager with an async send_command."""
    sm = MagicMock()
    sm.send_command = AsyncMock()
    return sm


def _make_thermostat(**kwargs) -> Thermostat:
    defaults = {
        "unique_id": "11673",
        "name": "Bad Kjeller Thermostat",
        "zone_id": "z-bad",
        "thermostat_address": 11673,
        "therm_sc_address": 12860,
        "set_heat_address": 13701,
        "therm_cur_address": 12812,
        "relay_address": 15680,
        "min_temp": 5.0,
        "max_temp": 35.0,
        "socket_manager": _make_socket_manager(),
        "zone_name": "Bad Kjeller",
    }
    defaults.update(kwargs)
    return Thermostat(**defaults)


def _rsn(
    address: int,
    type_code: int,
    field_a: float,
    field_b: float,
    field_c: float = 0.0,
) -> RsnMessage:
    return RsnMessage(
        address=address,
        name="test",
        type_code=type_code,
        flag=1,
        field_a=field_a,
        field_b=field_b,
        field_c=field_c,
    )


class TestThermostatInitialState:
    def test_initial_state_is_unknown(self):
        t = _make_thermostat()
        assert t.state == ThermostatState.UNKNOWN
        assert t.is_heating is None

    def test_initial_temperatures_are_none(self):
        t = _make_thermostat()
        assert t.current_temperature is None
        assert t.target_temperature is None

    def test_bounds_and_step(self):
        t = _make_thermostat(min_temp=5.0, max_temp=35.0)
        assert t.min_temp == 5.0
        assert t.max_temp == 35.0
        assert t.temp_step == 0.5
        assert t.zone_name == "Bad Kjeller"

    def test_repr_when_unknown(self):
        t = _make_thermostat()
        r = repr(t)
        assert "Bad Kjeller Thermostat" in r
        assert "unknown" in r


class TestSetTemperature:
    @pytest.mark.asyncio
    async def test_sends_set_value_then_new_state_for_default_mode(self):
        sm = _make_socket_manager()
        t = _make_thermostat(
            therm_sc_address=12860, set_heat_address=13701, socket_manager=sm
        )

        await t.set_temperature(22.0)

        calls = sm.send_command.call_args_list
        assert len(calls) == 2
        assert calls[0].args[0] == "set_value 12860 0 22"
        assert calls[1].args[0] == "new_state 13701 0"

    @pytest.mark.asyncio
    async def test_supports_half_degree_steps(self):
        sm = _make_socket_manager()
        t = _make_thermostat(
            therm_sc_address=12860, set_heat_address=13701, socket_manager=sm
        )

        await t.set_temperature(22.5)

        calls = sm.send_command.call_args_list
        assert calls[0].args[0] == "set_value 12860 0 22.5"
        assert calls[1].args[0] == "new_state 13701 0"

    @pytest.mark.asyncio
    async def test_rounds_to_nearest_half_degree(self):
        sm = _make_socket_manager()
        t = _make_thermostat(therm_sc_address=12860, socket_manager=sm)

        await t.set_temperature(21.3)

        assert sm.send_command.call_args_list[0].args[0] == "set_value 12860 0 21.5"

    @pytest.mark.asyncio
    async def test_uses_active_mode_index_from_therm_cur(self):
        sm = _make_socket_manager()
        t = _make_thermostat(
            therm_sc_address=12860,
            therm_cur_address=12812,
            set_heat_address=13701,
            socket_manager=sm,
        )
        # Simulate ThermCur reporting mode 1 (Saving)
        t.update_from_rsn(_rsn(12812, type_code=23, field_a=0, field_b=1.0))

        await t.set_temperature(20.0)

        calls = sm.send_command.call_args_list
        assert calls[0].args[0] == "set_value 12860 1 20"
        assert calls[1].args[0] == "new_state 13701 0"

    @pytest.mark.asyncio
    async def test_clamps_below_min_temp(self):
        sm = _make_socket_manager()
        t = _make_thermostat(therm_sc_address=12860, min_temp=5.0, socket_manager=sm)

        await t.set_temperature(2.0)

        assert sm.send_command.call_args_list[0].args[0] == "set_value 12860 0 5"

    @pytest.mark.asyncio
    async def test_clamps_above_max_temp(self):
        sm = _make_socket_manager()
        t = _make_thermostat(therm_sc_address=12860, max_temp=35.0, socket_manager=sm)

        await t.set_temperature(42.0)

        assert sm.send_command.call_args_list[0].args[0] == "set_value 12860 0 35"


class TestQueryState:
    @pytest.mark.asyncio
    async def test_queries_therm_cur_and_thermostat_addresses(self):
        sm = _make_socket_manager()
        t = _make_thermostat(
            thermostat_address=11673,
            therm_cur_address=12812,
            socket_manager=sm,
        )

        await t.query_state()

        calls = sm.send_command.call_args_list
        assert len(calls) == 2
        assert calls[0].args[0] == "d_obj 12812"
        assert calls[1].args[0] == "d_obj 11673"

    @pytest.mark.asyncio
    async def test_queries_only_thermostat_when_therm_cur_is_none(self):
        sm = _make_socket_manager()
        t = _make_thermostat(
            thermostat_address=11673,
            therm_cur_address=None,
            socket_manager=sm,
        )

        await t.query_state()

        sm.send_command.assert_called_once_with("d_obj 11673")


class TestUpdateFromRsn:
    def test_type7_updates_temps_and_heating_state(self):
        t = _make_thermostat()
        changed = t.update_from_rsn(
            _rsn(11673, type_code=7, field_a=1.0, field_b=21.0, field_c=19.6)
        )

        assert changed is True
        assert t.state == ThermostatState.HEATING
        assert t.is_heating is True
        assert t.target_temperature == 21.0
        assert t.current_temperature == 19.6

    def test_type7_idle_state(self):
        t = _make_thermostat()
        changed = t.update_from_rsn(
            _rsn(11673, type_code=7, field_a=0.0, field_b=22.0, field_c=24.5)
        )

        assert changed is True
        assert t.state == ThermostatState.IDLE
        assert t.is_heating is False
        assert t.target_temperature == 22.0
        assert t.current_temperature == 24.5

    def test_type7_no_change_returns_false(self):
        t = _make_thermostat()
        t.update_from_rsn(
            _rsn(11673, type_code=7, field_a=0.0, field_b=22.0, field_c=24.5)
        )

        changed = t.update_from_rsn(
            _rsn(11673, type_code=7, field_a=0.0, field_b=22.0, field_c=24.5)
        )
        assert changed is False

    def test_type8_relay_updates_heating_state(self):
        t = _make_thermostat()
        t.update_from_rsn(
            _rsn(11673, type_code=7, field_a=0.0, field_b=22.0, field_c=24.5)
        )
        assert t.is_heating is False

        changed = t.update_from_rsn(_rsn(15680, type_code=8, field_a=1.0, field_b=0.0))
        assert changed is True
        assert t.is_heating is True
        assert t.state == ThermostatState.HEATING

    def test_type8_relay_unchanged_returns_false(self):
        t = _make_thermostat()
        t.update_from_rsn(_rsn(15680, type_code=8, field_a=1.0, field_b=0.0))
        changed = t.update_from_rsn(_rsn(15680, type_code=8, field_a=1.0, field_b=0.0))
        assert changed is False

    def test_repr_shows_temperatures_after_update(self):
        t = _make_thermostat()
        t.update_from_rsn(
            _rsn(11673, type_code=7, field_a=1.0, field_b=21.5, field_c=19.2)
        )
        r = repr(t)
        assert "19.2°C" in r
        assert "21.5°C" in r
        assert "heating" in r
