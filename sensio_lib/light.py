from sensio_lib.light_state import LightState
from sensio_lib.socket_manager import SocketManager
import uuid
import logging

logger = logging.getLogger(__name__)

class Light:
    def __init__(self, name, on_address, off_address, server_address=None):
        self.state = LightState.UNKNOWN
        self.id = uuid.uuid4()
        self.name = name
        self.on_address = on_address
        self.off_address = off_address
        self.server_address = server_address
        self.socket_manager = SocketManager(self.server_address)

    def turn_on(self):
        logger.debug(f"Turning on light with ID: {self.name}")
        self.socket_manager.send_command(f'new_state {self.on_address} 0')
        self.state = LightState.ON

    def turn_off(self):
        logger.debug(f"Turning off light with ID: {self.name}")
        self.socket_manager.send_command(f'new_state {self.off_address} 0')
        self.state = LightState.OFF

    def update(self):
        logger.debug('Not implemented')

    def __repr__(self):
        return f'LightEntity: {self.name} - {self.state}'