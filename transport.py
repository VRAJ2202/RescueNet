# transport.py
import socket
import json

class UDPTransport:
    def __init__(self, host="127.0.0.1", port=5000):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.setblocking(False)

    def send(self, data, target_port):
        self.sock.sendto(json.dumps(data).encode(), (self.host, target_port))

    def receive(self):
        try:
            data, addr = self.sock.recvfrom(65535)
            return json.loads(data.decode()), addr
        except BlockingIOError:
            return None, None