"""Hub for local control of the Sensio smart house system."""

from __future__ import annotations

import logging
from collections.abc import Callable

from sensio_lib.dimmer import Dimmer
from sensio_lib.light import Light
from sensio_lib.message import RsnMessage, parse_rsn
from sensio_lib.scene import Scene
from sensio_lib.socket_manager import SocketManager

logger = logging.getLogger(__name__)


class Hub:
    """Local controller for a Sensio smart house system.

    Manages the socket connection to the physical controller and provides
    access to lights, dimmers, and scenes. Device data is supplied via
    connect(), typically from cached data originally fetched through SensioApi.

    A background read loop continuously receives RSN state messages and
    dispatches them to the appropriate device via an address registry.
    """

    def __init__(self, server_address: str) -> None:
        self._socket_manager = SocketManager(server_address)
        self._lights: list[Light] = []
        self._dimmers: list[Dimmer] = []
        self._scenes: list[Scene] = []
        self._address_registry: dict[int, list[Callable[[RsnMessage], None]]] = {}

    async def connect(self, functions_data: dict) -> None:
        """Parse device data and connect to the local controller.

        Args:
            functions_data: Functions JSON dict as returned by
                SensioApi.get_devices(). Can be cached and replayed.
        """
        self._parse_devices(functions_data)
        self._register_device_addresses()
        self._socket_manager.set_message_callback(self._on_message)
        await self._socket_manager.connect()

    def get_lights(self) -> list[Light]:
        """Return all discovered lights."""
        return list(self._lights)

    def get_dimmers(self) -> list[Dimmer]:
        """Return all discovered dimmers."""
        return list(self._dimmers)

    def get_scenes(self) -> list[Scene]:
        """Return all discovered scenes."""
        return list(self._scenes)

    def register_address(
        self, address: int, callback: Callable[[RsnMessage], None]
    ) -> None:
        """Register a callback for RSN messages at a specific address."""
        if address not in self._address_registry:
            self._address_registry[address] = []
        if callback not in self._address_registry[address]:
            self._address_registry[address].append(callback)

    def unregister_address(
        self, address: int, callback: Callable[[RsnMessage], None]
    ) -> None:
        """Remove a callback for a specific address."""
        if address in self._address_registry:
            self._address_registry[address] = [
                cb for cb in self._address_registry[address] if cb is not callback
            ]
            if not self._address_registry[address]:
                del self._address_registry[address]

    def _on_message(self, raw: str) -> None:
        """Handle an incoming message from the socket."""
        rsn = parse_rsn(raw)
        if rsn is None:
            logger.debug("Non-RSN message: %s", raw[:80])
            return

        callbacks = self._address_registry.get(rsn.address)
        if callbacks:
            for callback in callbacks:
                try:
                    callback(rsn)
                except Exception:
                    logger.exception(
                        "Error in address callback for %d", rsn.address
                    )
        else:
            logger.debug("Unhandled RSN address %d: %s", rsn.address, rsn.name)

    def _register_device_addresses(self) -> None:
        """Register all device feedback addresses with the address registry."""
        for light in self._lights:
            if light.relay_address is not None:
                self.register_address(light.relay_address, light.handle_state_update)

        for dimmer in self._dimmers:
            if dimmer.device_address is not None:
                self.register_address(
                    dimmer.device_address, dimmer.handle_state_update
                )

    def _parse_devices(self, functions_data: dict) -> None:
        """Parse the functions JSON into Light, Dimmer, and Scene objects."""
        functions = functions_data.get("functions", [])

        self._lights = self._parse_lights(functions)
        self._dimmers = self._parse_dimmers(functions)
        self._scenes = self._parse_scenes(functions)

    def _parse_lights(self, functions: list[dict]) -> list[Light]:
        """Parse individual lights and room-level light controls."""
        lights: list[Light] = []

        # --- Individual lights (subGroupId > 0) ---
        # Group by subGroupId to pair on/off addresses and relay feedback.
        groups: dict[int, dict] = {}
        for func in functions:
            sub_type = func["subType"]
            sub_group_id = func["subGroupId"]

            if sub_type not in ("light_on", "light_off", "light_relay") or sub_group_id == 0:
                continue

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
            elif sub_type == "light_relay":
                groups[sub_group_id]["relay_address"] = func["address"]

        for sub_group_id, info in groups.items():
            if info["on_address"] is not None and info["off_address"] is not None:
                lights.append(
                    Light(
                        unique_id=str(sub_group_id),
                        name=info["name"],
                        zone_id=info["zone_id"],
                        on_address=info["on_address"],
                        off_address=info["off_address"],
                        socket_manager=self._socket_manager,
                        relay_address=info["relay_address"],
                    )
                )

        # --- Room-level lights (LightOnRoom / LightOffRoom, subGroupId == 0) ---
        # Group by zoneId to pair on/off.
        room_groups: dict[str, dict] = {}
        for func in functions:
            sub_type = func["subType"]
            if sub_type not in ("LightOnRoom", "LightOffRoom"):
                continue

            zone_id = func["zoneId"]
            if zone_id not in room_groups:
                # Derive a friendly name from the internal name field
                # e.g. "B_LightStue_ON" -> "Stue"
                room_name = self._extract_room_name(func["name"])
                room_groups[zone_id] = {
                    "name": f"{room_name} All Lights",
                    "zone_id": zone_id,
                    "on_address": None,
                    "off_address": None,
                }

            if sub_type == "LightOnRoom":
                room_groups[zone_id]["on_address"] = func["address"]
            elif sub_type == "LightOffRoom":
                room_groups[zone_id]["off_address"] = func["address"]

        for zone_id, info in room_groups.items():
            if info["on_address"] is not None and info["off_address"] is not None:
                lights.append(
                    Light(
                        unique_id=f"{zone_id}_room",
                        name=info["name"],
                        zone_id=info["zone_id"],
                        on_address=info["on_address"],
                        off_address=info["off_address"],
                        socket_manager=self._socket_manager,
                    )
                )

        return lights

    def _parse_dimmers(self, functions: list[dict]) -> list[Dimmer]:
        """Parse dimmer devices from functions.

        Dimmers are grouped by subGroupId and have dim_set (command),
        dim_value (brightness feedback), and optionally light_mem entries.
        """
        groups: dict[int, dict] = {}
        for func in functions:
            sub_type = func["subType"]
            sub_group_id = func["subGroupId"]

            if sub_type not in ("dim_set", "dim_value", "light_mem") or sub_group_id == 0:
                continue

            if sub_group_id not in groups:
                groups[sub_group_id] = {
                    "name": func["displayName"],
                    "zone_id": func["zoneId"],
                    "dim_set_address": None,
                    "dim_value_address": None,
                }

            if sub_type == "dim_set":
                groups[sub_group_id]["dim_set_address"] = func["address"]
            elif sub_type == "dim_value":
                groups[sub_group_id]["dim_value_address"] = func["address"]

        dimmers: list[Dimmer] = []
        for sub_group_id, info in groups.items():
            if info["dim_set_address"] is not None:
                dimmers.append(
                    Dimmer(
                        unique_id=str(sub_group_id),
                        name=info["name"],
                        zone_id=info["zone_id"],
                        dim_set_address=info["dim_set_address"],
                        dim_value_address=info["dim_value_address"],
                        socket_manager=self._socket_manager,
                    )
                )

        return dimmers

    def _parse_scenes(self, functions: list[dict]) -> list[Scene]:
        """Parse scene functions into Scene objects."""
        room_scene_sub_types = {
            "LigthSc1Room", "LigthSc2Room", "LigthSc3Room", "LigthSc4Room",
        }
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

            if sub_type in room_scene_sub_types:
                # Room light scene: e.g. "B_LightStue_Sc1" -> "Stue Scene 1"
                room_name = self._extract_room_name(func["name"])
                scene_number = sub_type.replace("LigthSc", "").replace("Room", "")
                display_name = f"{room_name} Scene {scene_number}"
            elif sub_type in house_scene_sub_types:
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
        self._address_registry.clear()

    async def __aenter__(self) -> Hub:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()