"""Tests for Hub device parsing and orchestration."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from sensio_lib.hub import Hub
from sensio_lib.light import Light
from sensio_lib.scene import Scene


@pytest.fixture
def sample_functions():
    """Load the example functions.json test data."""
    path = Path(__file__).resolve().parents[2] / "example_data" / "functions.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def hub():
    """Create a Hub instance without connecting."""
    return Hub("192.168.1.1", "user", "pass")


class TestDeviceParsing:
    """Tests for _parse_devices, _parse_lights, _parse_scenes."""

    def test_parse_individual_lights(self, hub, sample_functions):
        """Lights with subGroupId > 0 should be paired by subGroupId."""
        hub._parse_devices(sample_functions)
        lights = hub.get_lights()

        # Find a known light from the test data: "Vindu sør" (subGroupId=27)
        vindu_sor = [l for l in lights if l.unique_id == "27"]
        assert len(vindu_sor) == 1
        assert vindu_sor[0].name == "Vindu sør"

    def test_parse_room_lights(self, hub, sample_functions):
        """Room-level controls (LightOnRoom/LightOffRoom) should be parsed."""
        hub._parse_devices(sample_functions)
        lights = hub.get_lights()

        # Room lights have unique_id ending in "_room"
        room_lights = [l for l in lights if l.unique_id.endswith("_room")]
        assert len(room_lights) > 0

        # Check that "Stue" room light exists
        stue_room = [l for l in room_lights if "Stue" in l.name]
        assert len(stue_room) == 1
        assert "All Lights" in stue_room[0].name

    def test_parse_scenes(self, hub, sample_functions):
        """Scenes should be parsed from LigthSc*Room subtypes."""
        hub._parse_devices(sample_functions)
        scenes = hub.get_scenes()

        assert len(scenes) > 0
        # All scenes should be Scene instances
        assert all(isinstance(s, Scene) for s in scenes)

        # Check scene naming: should include room name and scene number
        stue_scenes = [s for s in scenes if "Stue" in s.name]
        assert len(stue_scenes) == 4  # 4 scenes per room

        scene_names = {s.name for s in stue_scenes}
        assert "Stue Scene 1" in scene_names
        assert "Stue Scene 4" in scene_names

    def test_no_duplicate_lights(self, hub, sample_functions):
        """Each subGroupId should produce exactly one light."""
        hub._parse_devices(sample_functions)
        lights = hub.get_lights()

        ids = [l.unique_id for l in lights]
        assert len(ids) == len(set(ids)), "Duplicate light IDs found"

    def test_lights_have_addresses(self, hub, sample_functions):
        """All lights should have both on and off addresses set."""
        hub._parse_devices(sample_functions)
        lights = hub.get_lights()

        for light in lights:
            assert light._on_address is not None
            assert light._off_address is not None

    def test_all_devices_are_correct_types(self, hub, sample_functions):
        """Lights should be Light instances, scenes should be Scene instances."""
        hub._parse_devices(sample_functions)

        assert all(isinstance(l, Light) for l in hub.get_lights())
        assert all(isinstance(s, Scene) for s in hub.get_scenes())

    def test_empty_functions(self, hub):
        """Parsing empty data should produce no devices."""
        hub._parse_devices({"functions": []})
        assert hub.get_lights() == []
        assert hub.get_scenes() == []

    def test_parse_ignores_non_light_functions(self, hub):
        """Functions like heating, timers etc should be ignored."""
        data = {
            "functions": [
                {"address": 100, "subType": "memHeatAway", "name": "M_HeatAway", "displayName": "Heat Away", "zoneId": "z1", "subGroupId": 0, "type": 1, "properties": "", "displayOrder": -1},
                {"address": 200, "subType": "dim_set", "name": "B_D_Light", "displayName": "Dimmer", "zoneId": "z1", "subGroupId": 10, "type": 0, "properties": "", "displayOrder": 1},
            ]
        }
        hub._parse_devices(data)
        assert hub.get_lights() == []
        assert hub.get_scenes() == []


class TestExtractRoomName:
    """Tests for the room name extraction helper."""

    def test_standard_on(self):
        assert Hub._extract_room_name("B_LightStue_ON") == "Stue"

    def test_standard_off(self):
        assert Hub._extract_room_name("B_LightKontor_OFF") == "Kontor"

    def test_scene_name(self):
        assert Hub._extract_room_name("B_LightStue_Sc1") == "Stue"

    def test_long_room_name(self):
        assert Hub._extract_room_name("B_LightInngang_ON") == "Inngang"


class TestHubLifecycle:
    """Tests for login, set_project, and close."""

    @pytest.mark.asyncio
    async def test_login_returns_projects(self, hub):
        """Login should authenticate and return projects."""
        with patch.object(hub._api_client, "authenticate", new_callable=AsyncMock) as mock_auth, \
             patch.object(hub._api_client, "get_projects", new_callable=AsyncMock, return_value={"Home": "p1"}) as mock_proj:
            result = await hub.login()

            mock_auth.assert_called_once()
            mock_proj.assert_called_once()
            assert result == {"Home": "p1"}

    @pytest.mark.asyncio
    async def test_close_cleans_up(self, hub):
        """Close should clean up both API client and socket."""
        with patch.object(hub._api_client, "close", new_callable=AsyncMock) as mock_api_close, \
             patch.object(hub._socket_manager, "close", new_callable=AsyncMock) as mock_sock_close:
            await hub.close()

            mock_api_close.assert_called_once()
            mock_sock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Hub should work as an async context manager."""
        async with Hub("192.168.1.1", "user", "pass") as hub:
            assert hub is not None
        # close() is called automatically by __aexit__