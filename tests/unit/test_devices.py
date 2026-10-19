"""Tests for the Light and Scene device classes."""

from unittest.mock import AsyncMock

import pytest

from sensio_lib.light import Light, LightState
from sensio_lib.message import RsnMessage
from sensio_lib.scene import Scene


@pytest.fixture
def mock_socket():
    """Create a mock socket manager."""
    mock = AsyncMock()
    mock.send_command = AsyncMock()
    return mock


def _make_rsn(*, type_code: int = 8, field_a: float = 0, field_b: float = 0) -> RsnMessage:
    """Helper to create an RsnMessage with sensible defaults."""
    return RsnMessage(
        address=41302,
        name="R_Test",
        type_code=type_code,
        flag=1,
        field_a=field_a,
        field_b=field_b,
    )


class TestLight:
    """Tests for the Light class."""

    @pytest.mark.asyncio
    async def test_turn_on(self, mock_socket):
        light = Light("1", "Test Light", "zone1", on_address=100, off_address=200, socket_manager=mock_socket)

        await light.turn_on()

        mock_socket.send_command.assert_called_once_with("new_state 100 0")

    @pytest.mark.asyncio
    async def test_turn_on_does_not_change_state(self, mock_socket):
        """turn_on() should NOT optimistically set state — RSN drives state."""
        light = Light("1", "Test Light", "zone1", on_address=100, off_address=200, socket_manager=mock_socket)

        await light.turn_on()

        assert light.state == LightState.UNKNOWN

    @pytest.mark.asyncio
    async def test_turn_off(self, mock_socket):
        light = Light("1", "Test Light", "zone1", on_address=100, off_address=200, socket_manager=mock_socket)

        await light.turn_off()

        mock_socket.send_command.assert_called_once_with("new_state 200 0")


    @pytest.mark.asyncio
    async def test_turn_off_does_not_change_state(self, mock_socket):
        """turn_off() should NOT optimistically set state — RSN drives state."""
        light = Light("1", "Test Light", "zone1", on_address=100, off_address=200, socket_manager=mock_socket)

        await light.turn_off()

        assert light.state == LightState.UNKNOWN

    def test_initial_state_unknown(self, mock_socket):
        light = Light("1", "Test Light", "zone1", on_address=100, off_address=200, socket_manager=mock_socket)
        assert light.state == LightState.UNKNOWN
        assert light.is_on is None

    def test_properties(self, mock_socket):
        light = Light("42", "Kitchen", "zone-abc", on_address=100, off_address=200, socket_manager=mock_socket)
        assert light.unique_id == "42"
        assert light.name == "Kitchen"
        assert light.zone_id == "zone-abc"

    def test_repr(self, mock_socket):
        light = Light("1", "Test", "z", on_address=0, off_address=0, socket_manager=mock_socket)
        assert "Test" in repr(light)


class TestLightUpdateFromRsn:
    """Tests for Light.update_from_rsn()."""

    def test_relay_on(self, mock_socket):
        """RSN type 8 with field_a=1 should set state to ON."""
        light = Light("1", "Test", "z", on_address=0, off_address=0, socket_manager=mock_socket)

        changed = light.update_from_rsn(_make_rsn(type_code=8, field_a=1))

        assert light.state == LightState.ON
        assert light.is_on is True
        assert changed is True

    def test_relay_off(self, mock_socket):
        """RSN type 8 with field_a=0 should set state to OFF."""
        light = Light("1", "Test", "z", on_address=0, off_address=0, socket_manager=mock_socket)

        changed = light.update_from_rsn(_make_rsn(type_code=8, field_a=0))

        assert light.state == LightState.OFF
        assert light.is_on is False
        assert changed is True

    def test_same_state_returns_false(self, mock_socket):
        """Updating to the same state should return False."""
        light = Light("1", "Test", "z", on_address=0, off_address=0, socket_manager=mock_socket)

        light.update_from_rsn(_make_rsn(type_code=8, field_a=1))
        changed = light.update_from_rsn(_make_rsn(type_code=8, field_a=1))

        assert changed is False
        assert light.state == LightState.ON

    def test_state_toggle(self, mock_socket):
        """Toggling state via RSN should work correctly."""
        light = Light("1", "Test", "z", on_address=0, off_address=0, socket_manager=mock_socket)

        light.update_from_rsn(_make_rsn(type_code=8, field_a=1))
        assert light.state == LightState.ON

        changed = light.update_from_rsn(_make_rsn(type_code=8, field_a=0))
        assert changed is True
        assert light.state == LightState.OFF


    def test_memory_type_ignored(self, mock_socket):
        """RSN type 23 (memory) should be ignored."""
        light = Light("1", "Test", "z", on_address=0, off_address=0, socket_manager=mock_socket)

        changed = light.update_from_rsn(_make_rsn(type_code=23, field_a=0, field_b=1.0))

        assert changed is False
        assert light.state == LightState.UNKNOWN

    def test_button_type_ignored(self, mock_socket):
        """RSN type 6 (button) should be ignored."""
        light = Light("1", "Test", "z", on_address=0, off_address=0, socket_manager=mock_socket)

        changed = light.update_from_rsn(_make_rsn(type_code=6))

        assert changed is False


class TestScene:
    """Tests for the Scene class."""

    @pytest.mark.asyncio
    async def test_activate(self, mock_socket):
        scene = Scene("s1", "Living Room Scene 1", "zone1", address=500, socket_manager=mock_socket)

        await scene.activate()

        mock_socket.send_command.assert_called_once_with("new_state 500 0")

    def test_properties(self, mock_socket):
        scene = Scene("s1", "Living Room Scene 1", "zone1", address=500, socket_manager=mock_socket)
        assert scene.unique_id == "s1"
        assert scene.name == "Living Room Scene 1"
        assert scene.zone_id == "zone1"

    def test_repr(self, mock_socket):
        scene = Scene("s1", "Test Scene", "z", address=0, socket_manager=mock_socket)
        assert "Test Scene" in repr(scene)
