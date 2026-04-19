"""Tests for the Dimmer device class."""

from unittest.mock import AsyncMock

import pytest

from sensio_lib.dimmer import Dimmer
from sensio_lib.message import RsnMessage, TYPE_DIMMER, TYPE_RELAY


@pytest.fixture
def mock_socket():
    """Create a mock socket manager."""
    mock = AsyncMock()
    mock.send_command = AsyncMock()
    return mock


class TestDimmer:
    """Tests for the Dimmer class."""

    def test_initial_state(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        assert d.brightness == 0
        assert d.is_on is False

    @pytest.mark.asyncio
    async def test_set_brightness(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        await d.set_brightness(75)

        mock_socket.send_command.assert_called_once_with("new_state 100 75")
        assert d.brightness == 75
        assert d.is_on is True

    @pytest.mark.asyncio
    async def test_set_brightness_clamped(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        await d.set_brightness(150)
        assert d.brightness == 100

        await d.set_brightness(-10)
        assert d.brightness == 0

    @pytest.mark.asyncio
    async def test_turn_on_uses_last_brightness(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        await d.set_brightness(60)
        await d.turn_off()
        assert d.brightness == 0

        await d.turn_on()
        assert d.brightness == 60

    @pytest.mark.asyncio
    async def test_turn_on_default_brightness(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        await d.turn_on()
        assert d.brightness == 100  # Default

    @pytest.mark.asyncio
    async def test_turn_off(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        await d.set_brightness(50)
        await d.turn_off()

        assert d.brightness == 0
        assert d.is_on is False

    def test_handle_state_update_dimmer(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        rsn = RsnMessage(
            address=200, name="D_Test", type_code=TYPE_DIMMER,
            flag=1, field_a=50, field_b=75,
        )
        d.handle_state_update(rsn)
        # Uses field_b (target) as brightness
        assert d.brightness == 75
        assert d.is_on is True

    def test_handle_state_update_off(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        # First set to on
        d.handle_state_update(RsnMessage(
            address=200, name="D_Test", type_code=TYPE_DIMMER,
            flag=1, field_a=100, field_b=100,
        ))
        assert d.is_on is True

        # Then off
        d.handle_state_update(RsnMessage(
            address=200, name="D_Test", type_code=TYPE_DIMMER,
            flag=1, field_a=0, field_b=0,
        ))
        assert d.brightness == 0
        assert d.is_on is False

    def test_handle_state_update_ignores_wrong_type(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        rsn = RsnMessage(
            address=200, name="R_Test", type_code=TYPE_RELAY,
            flag=1, field_a=1, field_b=1,
        )
        d.handle_state_update(rsn)
        assert d.brightness == 0  # Unchanged

    def test_callback_fired_on_state_update(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        called = []
        d.set_callback(lambda: called.append(True))

        d.handle_state_update(RsnMessage(
            address=200, name="D_Test", type_code=TYPE_DIMMER,
            flag=1, field_a=50, field_b=50,
        ))
        assert len(called) == 1

    def test_callback_not_fired_when_unchanged(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        # Set initial state
        d.handle_state_update(RsnMessage(
            address=200, name="D_Test", type_code=TYPE_DIMMER,
            flag=1, field_a=50, field_b=50,
        ))

        called = []
        d.set_callback(lambda: called.append(True))

        # Same value again
        d.handle_state_update(RsnMessage(
            address=200, name="D_Test", type_code=TYPE_DIMMER,
            flag=1, field_a=50, field_b=50,
        ))
        assert len(called) == 0

    def test_last_nonzero_preserved_from_rsn(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        d.handle_state_update(RsnMessage(
            address=200, name="D_Test", type_code=TYPE_DIMMER,
            flag=1, field_a=80, field_b=80,
        ))
        d.handle_state_update(RsnMessage(
            address=200, name="D_Test", type_code=TYPE_DIMMER,
            flag=1, field_a=0, field_b=0,
        ))
        assert d._last_nonzero_brightness == 80

    def test_properties(self, mock_socket):
        d = Dimmer(
            "42", "Kitchen", "zone-abc",
            dim_set_address=100, socket_manager=mock_socket,
            dim_value_address=200, device_address=300,
        )
        assert d.unique_id == "42"
        assert d.name == "Kitchen"
        assert d.zone_id == "zone-abc"
        assert d.dim_set_address == 100
        assert d.dim_value_address == 200
        assert d.device_address == 300

    def test_repr(self, mock_socket):
        d = Dimmer("1", "Test", "z1", dim_set_address=100, socket_manager=mock_socket)
        assert "Test" in repr(d)
        assert "0" in repr(d)
