import socket
from sensio_lib.const import COMMAND_PREFIX, COMMAND_POSTFIX

class SocketManager:
    _instance = None

    def __new__(cls, server_address):
        if cls._instance is None:
            cls._instance = super(SocketManager, cls).__new__(cls)
            cls._instance.server_address = server_address
            cls._instance.server_port = 10023
            cls._instance.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cls._instance.socket.settimeout(15)
            cls._instance.socket.connect((server_address, 10023))
        return cls._instance

    def send_command(self, command):
        command = f'{COMMAND_PREFIX}{command}{COMMAND_POSTFIX}'
        self.socket.sendall(command.encode('utf-8'))
        #response = self.socket.recv(1024)
        #return response.decode('utf-8')

    def close(self):
        self.socket.close()
        SocketManager._instance = None