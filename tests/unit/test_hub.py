"""Tests for Hub device parsing, validation, and state dispatch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sensio_lib.hub import Hub
from sensio_lib.dimmer import Dimmer, DimmerState
from sensio_lib.light import Light, LightState
from sensio_lib.message import HubIdentity, RsnMessage
from sensio_lib.scene import Scene


VALID_CONNECT_XML = (
    '<connect sn="AABBCCDDEEFF" ip="10.0.0.1" mac="aa:bb:cc:dd:ee:ff"'
    ' pname="" pid="TEST-PRODUCT-001" pdate="1000000000" psum="1234"'
    ' rg="" fw="etn-spux Jan 01 2024 12:00:00 1.0.0-1"/>'
)


def _make_start_listener_side_effect(*messages: str):
    """Create a side effect for start_listener that calls the callback with messages.

    The callback is called synchronously with each message before returning.
    """
    async def side_effect(callback):
        for msg in messages:
            callback(msg)
    return side_effect


@pytest.fixture
def sample_functions():
    """Synthetic functions data covering all device types.

    Contains:
    - 2 individual lights (subGroupId 27 in Stue, subGroupId 42 in Kontor)
      with light_relay entries for RSN state dispatch
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
        {"address": 103, "subType": "light_relay", "name": "R_VindusrStue", "displayName": "Vindu sør",   "zoneId": "z-stue",   "subGroupId": 27, "type": 7, "properties": "", "displayOrder": 3},
        # Kontor – "Skrivebord" (subGroupId=42)
        {"address": 201, "subType": "light_on",  "name": "B_LightKontor_ON",  "displayName": "Skrivebord", "zoneId": "z-kontor", "subGroupId": 42, "type": 0, "properties": "", "displayOrder": 1},
        {"address": 202, "subType": "light_off", "name": "B_LightKontor_OFF", "displayName": "Skrivebord", "zoneId": "z-kontor", "subGroupId": 42, "type": 0, "properties": "", "displayOrder": 2},
        {"address": 203, "subType": "light_relay", "name": "R_SkrivebordKontor", "displayName": "Skrivebord", "zoneId": "z-kontor", "subGroupId": 42, "type": 7, "properties": "", "displayOrder": 3},

        # --- Dimmers ---
        # Stue – "Taklampe stue" (subGroupId=55)
        {"address": 301, "subType": "dim_value", "name": "M_D_TaklampeStue_Val", "displayName": "Taklampe stue", "zoneId": "z-stue", "subGroupId": 55, "type": 1, "properties": "", "displayOrder": 1},
        {"address": 302, "subType": "dim_set",   "name": "B_D_TaklampeStue_SET", "displayName": "Taklampe stue", "zoneId": "z-stue", "subGroupId": 55, "type": 0, "properties": "", "displayOrder": 2},
        {"address": 303, "subType": "light_mem", "name": "M_D_TaklampeStue_Sc",  "displayName": "Taklampe stue", "zoneId": "z-stue", "subGroupId": 55, "type": 2, "properties": "", "displayOrder": 3},
        # Kontor – "Downlights kontor" (subGroupId=60)
        {"address": 401, "subType": "dim_value", "name": "M_D_DownlightsKontor_Val", "displayName": "Downlights kontor", "zoneId": "z-kontor", "subGroupId": 60, "type": 1, "properties": "", "displayOrder": 1},
        {"address": 402, "subType": "dim_set",   "name": "B_D_DownlightsKontor_SET", "displayName": "Downlights kontor", "zoneId": "z-kontor", "subGroupId": 60, "type": 0, "properties": "", "displayOrder": 2},

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
            ]
        }
        hub._parse_devices(data)
        assert hub.get_lights() == []
        assert hub.get_scenes() == []


class TestDeviceRegistry:
    """Tests for the internal device registry built during parsing."""

    def test_registry_populated_for_relay_lights(self, hub, sample_functions):
        """light_relay entries should register the relay address in the registry."""
        hub._parse_devices(sample_functions)

        # subGroupId=27 has light_relay at address 103
        assert 103 in hub._device_registry
        assert hub._device_registry[103].unique_id == "27"

        # subGroupId=42 has light_relay at address 203
        assert 203 in hub._device_registry
        assert hub._device_registry[203].unique_id == "42"

    def test_registry_empty_without_relay_entries(self, hub):
        """Lights without light_relay entries should not be in the registry."""
        data = {"functions": [
            {"address": 101, "subType": "light_on",  "name": "B_Test_ON",  "displayName": "Test", "zoneId": "z1", "subGroupId": 50, "type": 0, "properties": "", "displayOrder": 1},
            {"address": 102, "subType": "light_off", "name": "B_Test_OFF", "displayName": "Test", "zoneId": "z1", "subGroupId": 50, "type": 0, "properties": "", "displayOrder": 2},
            # No light_relay entry for subGroupId 50
        ]}
        hub._parse_devices(data)

        # Light should still be created
        assert len(hub.get_lights()) == 1
        # But no registry entry
        assert len(hub._device_registry) == 0

    def test_registry_maps_to_correct_light(self, hub, sample_functions):
        """The registry should map the relay address to the correct Light object."""
        hub._parse_devices(sample_functions)

        light = hub._device_registry[103]
        assert light.name == "Vindu sør"
        assert light.unique_id == "27"


class TestDimmerParsing:
    """Tests for _parse_dimmers() and the dimmer device registry."""

    def test_parse_dimmers_creates_dimmer_objects(self, hub, sample_functions):
        """dim_set + dim_value pairs should produce Dimmer instances."""
        hub._parse_devices(sample_functions)
        dimmers = hub.get_dimmers()

        assert len(dimmers) == 2
        assert all(isinstance(d, Dimmer) for d in dimmers)

    def test_dimmer_names_correct(self, hub, sample_functions):
        hub._parse_devices(sample_functions)
        names = {d.name for d in hub.get_dimmers()}
        assert names == {"Taklampe stue", "Downlights kontor"}

    def test_dimmer_registered_at_value_address(self, hub, sample_functions):
        """dim_value address should be in the device registry for RSN dispatch."""
        hub._parse_devices(sample_functions)

        # subGroupId=55 has dim_value at address 301
        assert 301 in hub._device_registry
        assert hub._device_registry[301].unique_id == "55"
        assert isinstance(hub._device_registry[301], Dimmer)

        # subGroupId=60 has dim_value at address 401
        assert 401 in hub._device_registry
        assert hub._device_registry[401].unique_id == "60"

    def test_dimmer_set_address_stored(self, hub, sample_functions):
        hub._parse_devices(sample_functions)
        dimmer = hub._device_registry[301]  # Taklampe stue
        assert dimmer._set_address == 302

    def test_dimmer_value_address_stored(self, hub, sample_functions):
        hub._parse_devices(sample_functions)
        dimmer = hub._device_registry[301]
        assert dimmer._value_address == 301

    def test_light_mem_entry_does_not_create_extra_dimmer(self, hub, sample_functions):
        """light_mem subtype should be ignored; subGroupId=55 only has one dimmer."""
        hub._parse_devices(sample_functions)
        sg55 = [d for d in hub.get_dimmers() if d.unique_id == "55"]
        assert len(sg55) == 1

    def test_empty_functions_produces_no_dimmers(self, hub):
        hub._parse_devices({"functions": []})
        assert hub.get_dimmers() == []

    def test_dimmers_do_not_appear_in_lights(self, hub, sample_functions):
        """Dimmer subGroupIds should not bleed into the lights list."""
        hub._parse_devices(sample_functions)
        light_ids = {l.unique_id for l in hub.get_lights()}
        dimmer_ids = {d.unique_id for d in hub.get_dimmers()}
        assert light_ids.isdisjoint(dimmer_ids)

class TestMessageDispatch:
    """Tests for _handle_message() - the RSN dispatch logic."""

    def _set_identity(self, hub):
        """Set a dummy identity so _handle_message processes RSN messages."""
        hub._hub_identity = HubIdentity(
            serial="DUMMY000000",
            ip="10.0.0.1",
            mac="00:00:00:00:00:00",
            firmware="test-fw 1.0",
            product_id="TEST-001",
        )

    def test_rsn_updates_registered_device(self, hub, sample_functions):
        """RSN type 8 for a registered address should update the light."""
        hub._parse_devices(sample_functions)
        self._set_identity(hub)

        # Relay address 103 → subGroupId=27 "Vindu sør"
        hub._handle_message("RSN 103 R_VindusrStue 8 1 1 1")

        light = hub._device_registry[103]
        assert light.state == LightState.ON

    def test_rsn_calls_state_callback(self, hub, sample_functions):
        """When a registered device changes state, the callback should fire."""
        hub._parse_devices(sample_functions)
        self._set_identity(hub)
        callback = MagicMock()
        hub.set_state_callback(callback)

        hub._handle_message("RSN 103 R_VindusrStue 8 1 1 1")

        callback.assert_called_once()
        called_device = callback.call_args[0][0]
        assert called_device.unique_id == "27"

    def test_rsn_no_callback_when_state_unchanged(self, hub, sample_functions):
        """If state does not change, the callback should NOT fire."""
        hub._parse_devices(sample_functions)
        self._set_identity(hub)
        callback = MagicMock()
        hub.set_state_callback(callback)

        # First call changes state
        hub._handle_message("RSN 103 R_VindusrStue 8 1 1 1")
        callback.reset_mock()

        # Second call with same state - no change
        hub._handle_message("RSN 103 R_VindusrStue 8 1 1 1")
        callback.assert_not_called()

    def test_rsn_unregistered_address_ignored(self, hub, sample_functions):
        """RSN for an unregistered address should be silently ignored."""
        hub._parse_devices(sample_functions)
        self._set_identity(hub)
        callback = MagicMock()
        hub.set_state_callback(callback)

        # Address 99999 is not in the registry
        hub._handle_message("RSN 99999 R_Unknown 8 1 1 1")

        callback.assert_not_called()

    def test_non_rsn_message_ignored(self, hub, sample_functions):
        """Non-RSN messages should be silently skipped (after identity is set)."""
        hub._parse_devices(sample_functions)
        self._set_identity(hub)
        callback = MagicMock()
        hub.set_state_callback(callback)

        hub._handle_message("PANEL_BRIGHTNESS 70")
        hub._handle_message("end 79057")
        hub._handle_message("x_bm_st ACK_DIRECT seq=5")

        callback.assert_not_called()

    def test_no_callback_when_none_set(self, hub, sample_functions):
        """Without a state callback, state should still update without error."""
        hub._parse_devices(sample_functions)
        self._set_identity(hub)
        # No callback set

        hub._handle_message("RSN 103 R_VindusrStue 8 1 1 1")

        light = hub._device_registry[103]
        assert light.state == LightState.ON

    def test_rsn_type23_updates_dimmer_brightness(self, hub, sample_functions):
        """RSN type 23 on a dim_value address should update the Dimmer."""
        hub._parse_devices(sample_functions)
        self._set_identity(hub)

        # dim_value address 301 → subGroupId=55 "Taklampe stue"
        hub._handle_message("RSN 301 M_D_TaklampeStue_Val 23 1 0 75.000")

        dimmer = hub._device_registry[301]
        assert isinstance(dimmer, Dimmer)
        assert dimmer.brightness == 75
        assert dimmer.state == DimmerState.ON

    def test_rsn_type23_fires_callback_for_dimmer(self, hub, sample_functions):
        """A brightness change on a registered dimmer should fire the state callback."""
        hub._parse_devices(sample_functions)
        self._set_identity(hub)
        callback = MagicMock()
        hub.set_state_callback(callback)

        hub._handle_message("RSN 301 M_D_TaklampeStue_Val 23 1 0 50.000")

        callback.assert_called_once()
        called_device = callback.call_args[0][0]
        assert called_device.unique_id == "55"
        assert isinstance(called_device, Dimmer)

    def test_rsn_type23_no_callback_when_brightness_unchanged(self, hub, sample_functions):
        """No callback when the brightness doesn't change."""
        hub._parse_devices(sample_functions)
        self._set_identity(hub)
        callback = MagicMock()
        hub.set_state_callback(callback)

        hub._handle_message("RSN 301 M_D_TaklampeStue_Val 23 1 0 80.000")
        callback.reset_mock()

        hub._handle_message("RSN 301 M_D_TaklampeStue_Val 23 1 0 80.000")
        callback.assert_not_called()

    def test_first_message_parsed_as_identity(self, hub):
        """The first message should be parsed as hub identity."""
        assert hub._hub_identity is None

        hub._identity_ready = MagicMock()
        hub._handle_message(VALID_CONNECT_XML)

        assert hub._hub_identity is not None
        assert hub._hub_identity.serial == "AABBCCDDEEFF"
        hub._identity_ready.set.assert_called_once()

    def test_invalid_first_message_sets_event(self, hub):
        """If the first message is not valid identity, event should still be set."""
        hub._identity_ready = MagicMock()
        hub._handle_message("garbage data")

        assert hub._hub_identity is None
        hub._identity_ready.set.assert_called_once()


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


class TestHubValidation:
    """Tests for validate_connection()."""

    @pytest.mark.asyncio
    async def test_validate_returns_identity(self, hub):
        """validate_connection() should return HubIdentity on success."""
        with patch.object(hub._socket_manager, "connect", new_callable=AsyncMock), \
             patch.object(hub._socket_manager, "start_listener", side_effect=_make_start_listener_side_effect(VALID_CONNECT_XML)), \
             patch.object(hub._socket_manager, "close", new_callable=AsyncMock):

            identity = await hub.validate_connection()

            assert isinstance(identity, HubIdentity)
            assert identity.serial == "AABBCCDDEEFF"
            assert identity.firmware == "etn-spux Jan 01 2024 12:00:00 1.0.0-1"

    @pytest.mark.asyncio
    async def test_validate_closes_on_success(self, hub):
        """validate_connection() should close the socket after validation."""
        with patch.object(hub._socket_manager, "connect", new_callable=AsyncMock), \
             patch.object(hub._socket_manager, "start_listener", side_effect=_make_start_listener_side_effect(VALID_CONNECT_XML)), \
             patch.object(hub._socket_manager, "close", new_callable=AsyncMock) as mock_close:

            await hub.validate_connection()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_raises_on_garbage(self, hub):
        """validate_connection() should raise on non-XML response."""
        from sensio_lib.exceptions import SensioConnectionError

        with patch.object(hub._socket_manager, "connect", new_callable=AsyncMock), \
             patch.object(hub._socket_manager, "start_listener", side_effect=_make_start_listener_side_effect("garbage data")), \
             patch.object(hub._socket_manager, "close", new_callable=AsyncMock):

            with pytest.raises(SensioConnectionError):
                await hub.validate_connection()

    @pytest.mark.asyncio
    async def test_validate_closes_on_error(self, hub):
        """validate_connection() should close the socket even on error."""
        with patch.object(hub._socket_manager, "connect", new_callable=AsyncMock), \
             patch.object(hub._socket_manager, "start_listener", side_effect=_make_start_listener_side_effect("garbage")), \
             patch.object(hub._socket_manager, "close", new_callable=AsyncMock) as mock_close:

            try:
                await hub.validate_connection()
            except Exception:
                pass
            mock_close.assert_called_once()


class TestHubLifecycle:
    """Tests for connect and close."""

    @pytest.mark.asyncio
    async def test_connect_parses_validates_and_starts_listener(self, hub, sample_functions):
        """connect() should parse devices, validate hub identity, and start listener."""
        with patch.object(hub._socket_manager, "connect", new_callable=AsyncMock) as mock_connect, \
             patch.object(hub._socket_manager, "start_listener", side_effect=_make_start_listener_side_effect(VALID_CONNECT_XML)) as mock_listener:

            await hub.connect(sample_functions)

            mock_connect.assert_called_once()
            mock_listener.assert_called_once()
            assert len(hub.get_lights()) > 0
            assert len(hub.get_scenes()) > 0
            assert hub.hub_identity is not None
            assert hub.hub_identity.serial == "AABBCCDDEEFF"

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