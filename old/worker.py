from threading import Thread

from tcp.server import TcpServer
from ws.client import WebSocketClient


class Worker:
  def __init__(self, tcp_host: str, tcp_port: int, ws_host: str, ws_port: int) -> None:
    self._tcp_server = TcpServer(tcp_host, tcp_port)
    self._ws_client = WebSocketClient(ws_host, ws_port)

  def run(self):
    tcp_thread = Thread(target=self._tcp_server.run)
    ws_thread = Thread(target=self._ws_client.run)

    tcp_thread.start()
    ws_thread.start()

    tcp_thread.join()
    ws_thread.join()
