"""Hub for local control of the Sensio smart house system."""

from __future__ import annotations

from sensio_lib.light import Light
from sensio_lib.scene import Scene
from sensio_lib.socket_manager import SocketManager


class Hub:
    """Local controller for a Sensio smart house system.

    Manages the socket connection to the physical controller and provides
    access to lights and scenes. Device data is supplied via connect(),
    typically from cached data originally fetched through SensioApi.
    """

    def __init__(self, server_address: str) -> None:
        self._socket_manager = SocketManager(server_address)
        self._lights: list[Light] = []
        self._scenes: list[Scene] = []

    async def connect(self, functions_data: dict) -> None:
        """Parse device data and connect to the local controller.

        Args:
            functions_data: Functions JSON dict as returned by
                SensioApi.get_devices(). Can be cached and replayed.
        """
        self._parse_devices(functions_data)
        await self._socket_manager.connect()

    def get_lights(self) -> list[Light]:
        """Return all discovered lights."""
        return list(self._lights)

    def get_scenes(self) -> list[Scene]:
        """Return all discovered scenes."""
        return list(self._scenes)

    def _parse_devices(self, functions_data: dict) -> None:
        """Parse the functions JSON into Light and Scene objects."""
        functions = functions_data.get("functions", [])

        self._lights = self._parse_lights(functions)
        self._scenes = self._parse_scenes(functions)

    def _parse_lights(self, functions: list[dict]) -> list[Light]:
        """Parse individual lights and room-level light controls."""
        lights: list[Light] = []

        # --- Individual lights (subGroupId > 0) ---
        # Group by subGroupId to pair on/off addresses.
        groups: dict[int, dict] = {}
        for func in functions:
            sub_type = func["subType"]
            sub_group_id = func["subGroupId"]

            if sub_type not in ("light_on", "light_off") or sub_group_id == 0:
                continue

            if sub_group_id not in groups:
                groups[sub_group_id] = {
                    "name": func["displayName"],
                    "zone_id": func["zoneId"],
                    "on_address": None,
                    "off_address": None,
                }

            if sub_type == "light_on":
                groups[sub_group_id]["on_address"] = func["address"]
            elif sub_type == "light_off":
                groups[sub_group_id]["off_address"] = func["address"]

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

    async def __aenter__(self) -> Hub:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()