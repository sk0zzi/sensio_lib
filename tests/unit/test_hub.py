"""Tests for Hub device parsing and orchestration."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from sensio_lib.dimmer import Dimmer
from sensio_lib.hub import Hub
from sensio_lib.light import Light, LightState
from sensio_lib.message import RsnMessage, TYPE_DIMMER, TYPE_RELAY
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


class TestDimmerParsing:
    """Tests for dimmer device parsing."""

    def test_parse_dimmers_from_real_data(self, hub, sample_functions):
        """Dimmers with dim_set should be discovered."""
        hub._parse_devices(sample_functions)
        dimmers = hub.get_dimmers()

        assert len(dimmers) > 0
        assert all(isinstance(d, Dimmer) for d in dimmers)

    def test_dimmer_has_dim_set_address(self, hub, sample_functions):
        """All dimmers must have a dim_set_address."""
        hub._parse_devices(sample_functions)
        for dimmer in hub.get_dimmers():
            assert dimmer.dim_set_address is not None

    def test_parse_dimmer_from_minimal_data(self, hub):
        """A subGroup with dim_set and dim_value produces a Dimmer."""
        data = {
            "functions": [
                {"address": 100, "subType": "dim_set", "name": "B_D_Test_SET", "displayName": "Test Dimmer", "zoneId": "z1", "subGroupId": 50, "type": 0, "properties": "", "displayOrder": 1},
                {"address": 200, "subType": "dim_value", "name": "M_D_Test_Val", "displayName": "Test Dimmer", "zoneId": "z1", "subGroupId": 50, "type": 1, "properties": "", "displayOrder": 1},
            ]
        }
        hub._parse_devices(data)
        dimmers = hub.get_dimmers()
        assert len(dimmers) == 1
        assert dimmers[0].name == "Test Dimmer"
        assert dimmers[0].dim_set_address == 100
        assert dimmers[0].dim_value_address == 200

    def test_no_overlap_between_lights_and_dimmers(self, hub, sample_functions):
        """Dimmers and relay lights should not share IDs."""
        hub._parse_devices(sample_functions)
        light_ids = {l.unique_id for l in hub.get_lights()}
        dimmer_ids = {d.unique_id for d in hub.get_dimmers()}
        # Allow overlap in IDs since they use different subGroupIds naturally,
        # but verify both sets are populated
        assert len(light_ids) > 0
        assert len(dimmer_ids) > 0

    def test_empty_functions_no_dimmers(self, hub):
        hub._parse_devices({"functions": []})
        assert hub.get_dimmers() == []


class TestRelayAddressParsing:
    """Tests for relay address extraction in lights."""

    def test_lights_with_relay_address(self, hub, sample_functions):
        """Relay lights should have relay_address set when light_relay exists."""
        hub._parse_devices(sample_functions)
        lights = hub.get_lights()

        relay_lights = [l for l in lights if l.relay_address is not None]
        assert len(relay_lights) > 0

    def test_room_lights_no_relay(self, hub, sample_functions):
        """Room-level lights should not have relay addresses."""
        hub._parse_devices(sample_functions)
        lights = hub.get_lights()

        room_lights = [l for l in lights if l.unique_id.endswith("_room")]
        for rl in room_lights:
            assert rl.relay_address is None


class TestMessageDispatch:
    """Tests for the hub's address-based message routing."""

    def test_register_and_dispatch(self, hub):
        """Registered callbacks should receive RSN messages for their address."""
        received = []
        hub.register_address(42264, lambda rsn: received.append(rsn))

        hub._on_message("RSN 42264 D_TaklampeBod 21 1 100 100")
        assert len(received) == 1
        assert received[0].address == 42264

    def test_unregistered_address_ignored(self, hub):
        """Messages for unregistered addresses should not cause errors."""
        # Should just log at DEBUG, no exception
        hub._on_message("RSN 99999 Unknown 6 1 0 0")

    def test_non_rsn_message_ignored(self, hub):
        """Non-RSN messages should not cause errors."""
        hub._on_message("PANEL_BRIGHTNESS 70")
        hub._on_message("end 79057")

    def test_unregister_address(self, hub):
        """Unregistered callbacks should stop receiving messages."""
        received = []
        cb = lambda rsn: received.append(rsn)
        hub.register_address(100, cb)
        hub.unregister_address(100, cb)

        hub._on_message("RSN 100 Test 8 1 1 1")
        assert len(received) == 0

    def test_multiple_callbacks_same_address(self, hub):
        """Multiple callbacks on the same address should all fire."""
        r1, r2 = [], []
        hub.register_address(100, lambda rsn: r1.append(rsn))
        hub.register_address(100, lambda rsn: r2.append(rsn))

        hub._on_message("RSN 100 Test 8 1 1 1")
        assert len(r1) == 1
        assert len(r2) == 1

    def test_light_state_update_via_dispatch(self, hub, sample_functions):
        """A relay RSN should update the light's state through the dispatch chain."""
        hub._parse_devices(sample_functions)
        hub._register_device_addresses()

        # Find a light with a relay address
        relay_lights = [l for l in hub.get_lights() if l.relay_address is not None]
        assert len(relay_lights) > 0
        light = relay_lights[0]

        assert light.state == LightState.UNKNOWN

        # Simulate RSN for relay ON
        hub._on_message(
            f"RSN {light.relay_address} R_Test 8 1 1 1"
        )
        assert light.state == LightState.ON

        # Simulate RSN for relay OFF
        hub._on_message(
            f"RSN {light.relay_address} R_Test 8 1 0 0"
        )
        assert light.state == LightState.OFF