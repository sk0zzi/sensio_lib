"""Tests for the Dimmer device class."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sensio_lib.dimmer import Dimmer, DimmerState
from sensio_lib.message import RsnMessage


def _make_socket_manager():
    """Return a mock SocketManager with an async send_command."""
    sm = MagicMock()
    sm.send_command = AsyncMock()
    return sm


def _make_dimmer(**kwargs) -> Dimmer:
    defaults = {
        "unique_id": "99",
        "name": "Test Dimmer",
        "zone_id": "z-test",
        "set_address": 1000,
        "value_address": 2000,
        "socket_manager": _make_socket_manager(),
    }
    defaults.update(kwargs)
    return Dimmer(**defaults)


def _rsn(address: int, type_code: int, field_a: float, field_b: float) -> RsnMessage:
    return RsnMessage(
        address=address,
        name="test",
        type_code=type_code,
        flag=1,
        field_a=field_a,
        field_b=field_b,
    )


class TestDimmerInitialState:
    def test_initial_state_is_unknown(self):
        d = _make_dimmer()
        assert d.state == DimmerState.UNKNOWN

    def test_initial_brightness_is_none(self):
        d = _make_dimmer()
        assert d.brightness is None

    def test_is_on_false_when_unknown(self):
        d = _make_dimmer()
        assert d.is_on is False

    def test_repr_contains_name_and_state(self):
        d = _make_dimmer()
        r = repr(d)
        assert "Test Dimmer" in r
        assert "unknown" in r


class TestSetBrightness:
    @pytest.mark.asyncio
    async def test_sends_set_value_then_new_state(self):
        sm = _make_socket_manager()
        d = _make_dimmer(set_address=1000, value_address=2000, socket_manager=sm)

        await d.set_brightness(75)

        calls = sm.send_command.call_args_list
        assert len(calls) == 2
        assert calls[0].args[0] == "set_value 2000 75"
        assert calls[1].args[0] == "new_state 1000 0"

    @pytest.mark.asyncio
    async def test_clamps_level_above_100(self):
        sm = _make_socket_manager()
        d = _make_dimmer(value_address=2000, socket_manager=sm)

        await d.set_brightness(150)

        assert sm.send_command.call_args_list[0].args[0] == "set_value 2000 100"

    @pytest.mark.asyncio
    async def test_clamps_level_below_0(self):
        sm = _make_socket_manager()
        d = _make_dimmer(value_address=2000, socket_manager=sm)

        await d.set_brightness(-10)

        assert sm.send_command.call_args_list[0].args[0] == "set_value 2000 0"

    @pytest.mark.asyncio
    async def test_set_brightness_zero(self):
        sm = _make_socket_manager()
        d = _make_dimmer(set_address=1000, value_address=2000, socket_manager=sm)

        await d.set_brightness(0)

        calls = sm.send_command.call_args_list
        assert calls[0].args[0] == "set_value 2000 0"
        assert calls[1].args[0] == "new_state 1000 0"


class TestTurnOnOff:
    @pytest.mark.asyncio
    async def test_turn_on_uses_last_known_brightness(self):
        sm = _make_socket_manager()
        d = _make_dimmer(value_address=2000, socket_manager=sm)
        d._brightness = 47

        await d.turn_on()

        assert sm.send_command.call_args_list[0].args[0] == "set_value 2000 47"

    @pytest.mark.asyncio
    async def test_turn_on_defaults_to_100_when_brightness_unknown(self):
        sm = _make_socket_manager()
        d = _make_dimmer(value_address=2000, socket_manager=sm)
        assert d._brightness is None

        await d.turn_on()

        assert sm.send_command.call_args_list[0].args[0] == "set_value 2000 100"

    @pytest.mark.asyncio
    async def test_turn_on_defaults_to_100_when_brightness_is_zero(self):
        """If last known brightness was 0, turn_on should go to 100, not stay off."""
        sm = _make_socket_manager()
        d = _make_dimmer(value_address=2000, socket_manager=sm)
        d._brightness = 0

        await d.turn_on()

        assert sm.send_command.call_args_list[0].args[0] == "set_value 2000 100"

    @pytest.mark.asyncio
    async def test_turn_off_sends_zero(self):
        sm = _make_socket_manager()
        d = _make_dimmer(value_address=2000, socket_manager=sm)

        await d.turn_off()

        assert sm.send_command.call_args_list[0].args[0] == "set_value 2000 0"


class TestUpdateFromRsn:
    def test_type23_updates_brightness_and_state(self):
        d = _make_dimmer()
        changed = d.update_from_rsn(_rsn(2000, type_code=23, field_a=0, field_b=75.0))

        assert changed is True
        assert d.brightness == 75
        assert d.state == DimmerState.ON
        assert d.is_on is True

    def test_type23_zero_sets_state_off(self):
        d = _make_dimmer()
        d._brightness = 50
        d._state = DimmerState.ON

        changed = d.update_from_rsn(_rsn(2000, type_code=23, field_a=0, field_b=0.0))

        assert changed is True
        assert d.brightness == 0
        assert d.state == DimmerState.OFF
        assert d.is_on is False

    def test_type23_no_change_returns_false(self):
        d = _make_dimmer()
        d._brightness = 80
        d._state = DimmerState.ON

        changed = d.update_from_rsn(_rsn(2000, type_code=23, field_a=0, field_b=80.0))

        assert changed is False
        assert d.brightness == 80

    def test_type21_is_ignored(self):
        """RSN type 21 (D_ device) should be ignored; we track via type 23."""
        d = _make_dimmer()
        changed = d.update_from_rsn(_rsn(2000, type_code=21, field_a=75, field_b=75))

        assert changed is False
        assert d.state == DimmerState.UNKNOWN

    def test_type8_relay_message_is_ignored(self):
        d = _make_dimmer()
        changed = d.update_from_rsn(_rsn(2000, type_code=8, field_a=1, field_b=1))

        assert changed is False

    def test_brightness_rounds_float(self):
        """field_b is a float like 47.000 — should be stored as int 47."""
        d = _make_dimmer()
        d.update_from_rsn(_rsn(2000, type_code=23, field_a=0, field_b=47.0))

        assert d.brightness == 47
        assert isinstance(d.brightness, int)

    def test_state_transitions_unknown_to_on(self):
        d = _make_dimmer()
        assert d.state == DimmerState.UNKNOWN

        d.update_from_rsn(_rsn(2000, type_code=23, field_a=0, field_b=100.0))

        assert d.state == DimmerState.ON

    def test_repr_shows_brightness_after_update(self):
        d = _make_dimmer()
        d.update_from_rsn(_rsn(2000, type_code=23, field_a=0, field_b=55.0))

        r = repr(d)
        assert "55%" in r
        assert "on" in r
