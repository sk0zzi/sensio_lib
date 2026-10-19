"""Hub for local control of the Sensio smart house system."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from sensio_lib.exceptions import SensioConnectionError
from sensio_lib.dimmer import Dimmer
from sensio_lib.light import Light
from sensio_lib.message import HubIdentity, parse_hub_identity, parse_rsn_message
from sensio_lib.scene import Scene
from sensio_lib.socket_manager import SocketManager

logger = logging.getLogger(__name__)


class Hub:
    """Local controller for a Sensio smart house system.

    Manages the socket connection to the physical controller and provides
    access to lights and scenes. Device data is supplied via connect(),
    typically from cached data originally fetched through SensioApi.

    On connect, the hub starts a background listener. The first message
    from the hub is expected to be a <connect> XML tag identifying the
    hub. Subsequent messages are RSN state updates dispatched to
    registered devices.
    """

    def __init__(self, server_address: str) -> None:
        self._socket_manager = SocketManager(server_address)
        self._zones: dict[str, str] = {}
        self._lights: list[Light] = []
        self._dimmers: list[Dimmer] = []
        self._scenes: list[Scene] = []
        self._device_registry: dict[int, Light | Dimmer] = {}
        self._hub_identity: HubIdentity | None = None
        self._state_callback: Callable[[Light | Dimmer], None] | None = None
        self._identity_ready: asyncio.Event | None = None

    @property
    def hub_identity(self) -> HubIdentity | None:
        """Return the hub identity read on connect, or None."""
        return self._hub_identity

    def set_state_callback(self, callback: Callable[[Light | Dimmer], None]) -> None:
        """Set the callback invoked when any registered device's state changes.

        Home Assistant uses this to trigger entity state refreshes.
        """
        self._state_callback = callback

    async def validate_connection(self) -> HubIdentity:
        """Connect, wait for the hub identity, then disconnect.

        For use in Home Assistant config flow to verify the IP
        points to a real Sensio hub before saving the entry.

        Returns:
            HubIdentity with serial, firmware, etc.

        Raises:
            SensioConnectionError: If the connection fails or the hub
                does not send a valid Sensio connect tag.
        """
        try:
            self._hub_identity = None
            self._identity_ready = asyncio.Event()
            await self._socket_manager.connect()
            await self._socket_manager.start_listener(self._handle_message)

            # Wait for the listener to process the first message (hub identity).
            try:
                await asyncio.wait_for(self._identity_ready.wait(), timeout=10.0)
            except asyncio.TimeoutError as err:
                raise SensioConnectionError(
                    "Hub did not send identity within timeout"
                ) from err

            if self._hub_identity is None:
                raise SensioConnectionError(
                    "Hub did not send a valid Sensio identity"
                )

            return self._hub_identity
        finally:
            await self._socket_manager.close()

    async def connect(self, functions_data: dict) -> None:
        """Parse device data and connect to the local controller.

        This method:
        1. Parses functions data into Light/Scene objects and builds
           the internal RSN address registry.
        2. Connects the TCP socket to the hub.
        3. Starts the background listener. The first message is expected
           to be the hub identity XML.

        Args:
            functions_data: Functions JSON dict as returned by
                SensioApi.get_devices(). Can be cached and replayed.
        """
        self._parse_devices(functions_data)
        self._hub_identity = None
        self._identity_ready = asyncio.Event()
        await self._socket_manager.connect()
        await self._socket_manager.start_listener(self._handle_message)

        # Wait for the listener to process the hub identity.
        try:
            await asyncio.wait_for(self._identity_ready.wait(), timeout=10.0)
        except asyncio.TimeoutError as err:
            raise SensioConnectionError(
                "Hub did not send identity within timeout"
            ) from err

        if self._hub_identity is None:
            raise SensioConnectionError(
                "Hub did not send a valid Sensio identity"
            )

        logger.info(
            "Connected to Sensio hub: serial=%s, firmware=%s",
            self._hub_identity.serial,
            self._hub_identity.firmware,
        )
        logger.info(
            "Device registry: %d relay lights, %d dimmers with RSN state tracking",
            sum(1 for d in self._device_registry.values() if isinstance(d, Light)),
            sum(1 for d in self._device_registry.values() if isinstance(d, Dimmer)),
        )
        for addr, device in self._device_registry.items():
            logger.info("  %s addr=%d -> %s", type(device).__name__, addr, device.name)

    def get_zones(self) -> dict[str, str]:
        """Return all discovered zones as a mapping of zone_id to zone_name."""
        return dict(self._zones)

    def get_lights(self) -> list[Light]:
        """Return all discovered relay lights."""
        return list(self._lights)

    def get_dimmers(self) -> list[Dimmer]:
        """Return all discovered dimmers."""
        return list(self._dimmers)

    def get_scenes(self) -> list[Scene]:
        """Return all discovered scenes."""
        return list(self._scenes)

    def _handle_message(self, raw: str) -> None:
        """Dispatch an incoming hub message.

        This is the callback passed to the socket listener. The first
        message is expected to be the hub identity XML. All subsequent
        messages are parsed as RSN and dispatched to registered devices.
        """
        # First message: parse as hub identity.
        if self._hub_identity is None:
            try:
                self._hub_identity = parse_hub_identity(raw)
                logger.debug("Parsed hub identity: serial=%s", self._hub_identity.serial)
            except SensioConnectionError:
                logger.error("Hub did not send valid identity on connect")
            if self._identity_ready is not None:
                self._identity_ready.set()
            return

        # Normal RSN dispatch.
        message = parse_rsn_message(raw)
        if message is None:
            logger.debug("Non-RSN message (skipped): %.80s", raw)
            return

        logger.debug(
            "RSN: addr=%d name=%s type=%d field_a=%.1f field_b=%.1f",
            message.address, message.name, message.type_code,
            message.field_a, message.field_b,
        )

        # Look up device by address (relays).
        device = self._device_registry.get(message.address)
        if device is None:
            logger.debug(
                "RSN addr=%d name=%s not in registry (ignored)",
                message.address, message.name,
            )
            return

        changed = device.update_from_rsn(message)
        if changed:
            logger.info(
                "Device updated: %s -> %s",
                device.name, device.state.value,
            )
            if self._state_callback is not None:
                self._state_callback(device)
        else:
            logger.debug("RSN matched %s but state unchanged", device.name)

    def _parse_devices(self, functions_data: dict) -> None:
        """Parse the functions JSON into Light, Dimmer, and Scene objects."""
        functions = functions_data.get("functions", [])

        self._zones = self._parse_zones(functions)
        self._lights = self._parse_lights(functions)
        self._dimmers = self._parse_dimmers(functions)
        self._scenes = self._parse_scenes(functions)

    @staticmethod
    def _parse_zones(functions: list[dict]) -> dict[str, str]:
        """Parse zone names from memLightRoomCurSc entries."""
        zones: dict[str, str] = {}
        for func in functions:
            if func.get("subType") != "memLightRoomCurSc":
                continue
            zone_id = func.get("zoneId")
            display_name = func.get("displayName") or ""
            if zone_id and display_name:
                zones[zone_id] = display_name.removesuffix(" Light Scene").strip()
        return zones

    def _parse_lights(self, functions: list[dict]) -> list[Light]:
        """Parse individual lights, dimmers, and room-level light controls.

        Builds a registry for RSN state dispatch:
        - _device_registry: maps relay addresses to Light objects (relays)
        """
        lights: list[Light] = []
        self._device_registry = {}

        # --- Individual relay lights (subGroupId > 0) ---
        # Group by subGroupId to pair on/off addresses and find relay address.
        groups: dict[int, dict] = {}
        for func in functions:
            sub_type = func["subType"]
            sub_group_id = func["subGroupId"]

            if sub_group_id == 0:
                continue

            if sub_type in ("light_on", "light_off"):
                if sub_group_id not in groups:
                    groups[sub_group_id] = {
                        "name": func["displayName"],
                        "zone_id": func["zoneId"],
                        "on_address": None,
                        "off_address": None,
                        "relay_address": None,
                    }

                if sub_type == "light_on":
                    groups[sub_group_id]["on_address"] = func["address"]
                elif sub_type == "light_off":
                    groups[sub_group_id]["off_address"] = func["address"]

            elif sub_type == "light_relay" and sub_group_id in groups:
                groups[sub_group_id]["relay_address"] = func["address"]

        # Second pass: pick up light_relay entries for groups that were
        # created before the relay entry was encountered.
        for func in functions:
            if func["subType"] == "light_relay" and func["subGroupId"] in groups:
                groups[func["subGroupId"]]["relay_address"] = func["address"]

        for sub_group_id, info in groups.items():
            if info["on_address"] is not None and info["off_address"] is not None:
                zone_id = info["zone_id"]
                light = Light(
                    unique_id=str(sub_group_id),
                    name=info["name"],
                    zone_id=zone_id,
                    on_address=info["on_address"],
                    off_address=info["off_address"],
                    socket_manager=self._socket_manager,
                    zone_name=self._zones.get(zone_id),
                )
                lights.append(light)

                # Register the relay address for RSN state dispatch.
                if info["relay_address"] is not None:
                    self._device_registry[info["relay_address"]] = light



        return lights

    def _parse_dimmers(self, functions: list[dict]) -> list[Dimmer]:
        """Parse dimmer devices from functions data.

        Groups entries by subGroupId and collects dim_set (trigger address)
        and dim_value (value address). The dim_value address is registered
        in the device registry for RSN type 23 state dispatch — the hub
        broadcasts brightness updates on this address.
        """
        groups: dict[int, dict] = {}

        for func in functions:
            sub_type = func["subType"]
            sub_group_id = func["subGroupId"]

            if sub_group_id == 0:
                continue

            if sub_type in ("dim_set", "dim_value"):
                if sub_group_id not in groups:
                    groups[sub_group_id] = {
                        "name": func["displayName"],
                        "zone_id": func["zoneId"],
                        "set_address": None,
                        "value_address": None,
                    }

                if sub_type == "dim_set":
                    groups[sub_group_id]["set_address"] = func["address"]
                elif sub_type == "dim_value":
                    groups[sub_group_id]["value_address"] = func["address"]

        dimmers: list[Dimmer] = []
        for sub_group_id, info in groups.items():
            if info["set_address"] is not None and info["value_address"] is not None:
                zone_id = info["zone_id"]
                dimmer = Dimmer(
                    unique_id=str(sub_group_id),
                    name=info["name"],
                    zone_id=zone_id,
                    set_address=info["set_address"],
                    value_address=info["value_address"],
                    socket_manager=self._socket_manager,
                    zone_name=self._zones.get(zone_id),
                )
                dimmers.append(dimmer)

                # Register the dim_value address for RSN type 23 state dispatch.
                self._device_registry[info["value_address"]] = dimmer

        return dimmers
    def _parse_scenes(self, functions: list[dict]) -> list[Scene]:
        """Parse house-level scene functions into Scene objects."""
        house_scene_sub_types = {
            "house_in": "Home",
            "house_away": "Away",
            "house_night": "Night",
            "house_vacation": "Vacation",
        }
        scenes: list[Scene] = []

        for func in functions:
            sub_type = func["subType"]
            zone_id = func["zoneId"]
            address = func["address"]

            if sub_type in house_scene_sub_types:
                # House-level scene: e.g. house_in -> "House Home"
                display_name = f"House {house_scene_sub_types[sub_type]}"
            else:
                continue

            scenes.append(
                Scene(
                    unique_id=f"{zone_id}_{address}",
                    name=display_name,
                    zone_id=zone_id,
                    address=address,
                    socket_manager=self._socket_manager,
                    zone_name=self._zones.get(zone_id),
                )
            )

        return scenes

    @staticmethod
    def _extract_room_name(internal_name: str) -> str:
        """Extract a room name from the Sensio internal naming convention.

        Examples:
            "B_LightStue_ON"    -> "Stue"
            "B_LightKontor_OFF" -> "Kontor"
            "B_LightStue_Sc1"   -> "Stue"
        """
        parts = internal_name.split("_")
        # Typically: B_Light<Room>_<Suffix> or B_Light<Room>_<Suffix>
        for part in parts:
            if part.startswith("Light") and len(part) > 5:
                return part[5:]  # Strip "Light" prefix
        # Fallback: return the middle part
        if len(parts) >= 3:
            return parts[1]
        return internal_name

    async def close(self) -> None:
        """Close the socket connection and clean up resources."""
        await self._socket_manager.close()

    async def __aenter__(self) -> Hub:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()