"""Tests for the Light and Scene device classes."""

from unittest.mock import AsyncMock

import pytest

from sensio_lib.light import Light, LightState
from sensio_lib.scene import Scene


@pytest.fixture
def mock_socket():
    """Create a mock socket manager."""
    mock = AsyncMock()
    mock.send_command = AsyncMock()
    return mock


class TestLight:
    """Tests for the Light class."""

    @pytest.mark.asyncio
    async def test_turn_on(self, mock_socket):
        light = Light("1", "Test Light", "zone1", on_address=100, off_address=200, socket_manager=mock_socket)

        await light.turn_on()

        mock_socket.send_command.assert_called_once_with("new_state 100 0")
        assert light.state == LightState.ON
        assert light.is_on is True

    @pytest.mark.asyncio
    async def test_turn_off(self, mock_socket):
        light = Light("1", "Test Light", "zone1", on_address=100, off_address=200, socket_manager=mock_socket)

        await light.turn_off()

        mock_socket.send_command.assert_called_once_with("new_state 200 0")
        assert light.state == LightState.OFF
        assert light.is_on is False

    def test_initial_state_unknown(self, mock_socket):
        light = Light("1", "Test Light", "zone1", on_address=100, off_address=200, socket_manager=mock_socket)
        assert light.state == LightState.UNKNOWN
        assert light.is_on is False

    def test_properties(self, mock_socket):
        light = Light("42", "Kitchen", "zone-abc", on_address=100, off_address=200, socket_manager=mock_socket)
        assert light.unique_id == "42"
        assert light.name == "Kitchen"
        assert light.zone_id == "zone-abc"

    def test_repr(self, mock_socket):
        light = Light("1", "Test", "z", on_address=0, off_address=0, socket_manager=mock_socket)
        assert "Test" in repr(light)


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
