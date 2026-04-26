"""Tests for Hub device parsing and orchestration."""

from unittest.mock import AsyncMock, patch

import pytest

from sensio_lib.hub import Hub
from sensio_lib.light import Light
from sensio_lib.scene import Scene


@pytest.fixture
def sample_functions():
    """Synthetic functions data covering all device types.

    Contains:
    - 2 individual lights (subGroupId 27 in Stue, subGroupId 42 in Kontor)
    - 2 room-level light controls (Stue, Kontor)
    - 8 room scenes (4 per room)
    - 4 house-level scenes
    - 1 non-light function (heating) that should be ignored
    """
    return {"functions": [
        # --- Individual lights (paired on/off by subGroupId) ---
        # Stue – "Vindu sør" (subGroupId=27)
        {"address": 101, "subType": "light_on",  "name": "B_LightStue_ON",  "displayName": "Vindu sør",   "zoneId": "z-stue",   "subGroupId": 27, "type": 0, "properties": "", "displayOrder": 1},
        {"address": 102, "subType": "light_off", "name": "B_LightStue_OFF", "displayName": "Vindu sør",   "zoneId": "z-stue",   "subGroupId": 27, "type": 0, "properties": "", "displayOrder": 2},
        # Kontor – "Skrivebord" (subGroupId=42)
        {"address": 201, "subType": "light_on",  "name": "B_LightKontor_ON",  "displayName": "Skrivebord", "zoneId": "z-kontor", "subGroupId": 42, "type": 0, "properties": "", "displayOrder": 1},
        {"address": 202, "subType": "light_off", "name": "B_LightKontor_OFF", "displayName": "Skrivebord", "zoneId": "z-kontor", "subGroupId": 42, "type": 0, "properties": "", "displayOrder": 2},

        # --- Room-level light controls (subGroupId == 0) ---
        {"address": 301, "subType": "LightOnRoom",  "name": "B_LightStue_ON",    "displayName": "Stue On",    "zoneId": "z-stue",   "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 302, "subType": "LightOffRoom", "name": "B_LightStue_OFF",   "displayName": "Stue Off",   "zoneId": "z-stue",   "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 303, "subType": "LightOnRoom",  "name": "B_LightKontor_ON",  "displayName": "Kontor On",  "zoneId": "z-kontor", "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 304, "subType": "LightOffRoom", "name": "B_LightKontor_OFF", "displayName": "Kontor Off", "zoneId": "z-kontor", "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},

        # --- Room scenes (4 per room) ---
        {"address": 401, "subType": "LigthSc1Room", "name": "B_LightStue_Sc1",   "displayName": "Stue Sc1",   "zoneId": "z-stue",   "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 402, "subType": "LigthSc2Room", "name": "B_LightStue_Sc2",   "displayName": "Stue Sc2",   "zoneId": "z-stue",   "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 403, "subType": "LigthSc3Room", "name": "B_LightStue_Sc3",   "displayName": "Stue Sc3",   "zoneId": "z-stue",   "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 404, "subType": "LigthSc4Room", "name": "B_LightStue_Sc4",   "displayName": "Stue Sc4",   "zoneId": "z-stue",   "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 411, "subType": "LigthSc1Room", "name": "B_LightKontor_Sc1", "displayName": "Kontor Sc1", "zoneId": "z-kontor", "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 412, "subType": "LigthSc2Room", "name": "B_LightKontor_Sc2", "displayName": "Kontor Sc2", "zoneId": "z-kontor", "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 413, "subType": "LigthSc3Room", "name": "B_LightKontor_Sc3", "displayName": "Kontor Sc3", "zoneId": "z-kontor", "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 414, "subType": "LigthSc4Room", "name": "B_LightKontor_Sc4", "displayName": "Kontor Sc4", "zoneId": "z-kontor", "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},

        # --- House-level scenes ---
        {"address": 501, "subType": "house_in",       "name": "B_HouseIn",       "displayName": "House In",       "zoneId": "z-house", "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 502, "subType": "house_away",     "name": "B_HouseAway",     "displayName": "House Away",     "zoneId": "z-house", "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 503, "subType": "house_night",    "name": "B_HouseNight",    "displayName": "House Night",    "zoneId": "z-house", "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},
        {"address": 504, "subType": "house_vacation", "name": "B_HouseVacation", "displayName": "House Vacation", "zoneId": "z-house", "subGroupId": 0, "type": 0, "properties": "", "displayOrder": -1},

        # --- Non-light function (should be ignored) ---
        {"address": 900, "subType": "memHeatAway", "name": "M_HeatAway", "displayName": "Heat Away", "zoneId": "z-stue", "subGroupId": 0, "type": 1, "properties": "", "displayOrder": -1},
    ]}


@pytest.fixture
def hub():
    """Create a Hub instance without connecting."""
    return Hub("192.168.1.1")


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

    def test_parse_house_scenes(self, hub, sample_functions):
        """House-level scenes (house_in, house_away, etc.) should be parsed."""
        hub._parse_devices(sample_functions)
        scenes = hub.get_scenes()

        house_scenes = [s for s in scenes if s.name.startswith("House ")]
        assert len(house_scenes) == 4

        house_scene_names = {s.name for s in house_scenes}
        assert house_scene_names == {
            "House Home", "House Away", "House Night", "House Vacation",
        }

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
    """Tests for connect and close."""

    @pytest.mark.asyncio
    async def test_connect_parses_and_connects(self, hub, sample_functions):
        """connect() should parse devices and open the socket."""
        with patch.object(hub._socket_manager, "connect", new_callable=AsyncMock) as mock_connect:
            await hub.connect(sample_functions)

            mock_connect.assert_called_once()
            assert len(hub.get_lights()) > 0
            assert len(hub.get_scenes()) > 0

    @pytest.mark.asyncio
    async def test_close_cleans_up(self, hub):
        """Close should clean up the socket connection."""
        with patch.object(hub._socket_manager, "close", new_callable=AsyncMock) as mock_sock_close:
            await hub.close()

            mock_sock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Hub should work as an async context manager."""
        async with Hub("192.168.1.1") as hub:
            assert hub is not None
        # close() is called automatically by __aexit__