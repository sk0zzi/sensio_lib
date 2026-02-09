"""Scene device for Sensio scene activation."""

from sensio_lib.device import Device
from sensio_lib.socket_manager import SocketManager


class Scene(Device):
    """Represents a Sensio scene that can be activated.

    Scenes are trigger-only — they have no on/off state.
    """

    def __init__(
        self,
        unique_id: str,
        name: str,
        zone_id: str,
        address: int,
        socket_manager: SocketManager,
    ) -> None:
        super().__init__(unique_id, name, zone_id, socket_manager)
        self._address = address

    async def activate(self) -> None:
        """Activate this scene."""
        await self._socket_manager.send_command(f"new_state {self._address} 0")

    def __repr__(self) -> str:
        return f"Scene(name={self._name!r})"
