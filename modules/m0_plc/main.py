"""Эмулятор PLC: TCP-сервер, рассылающий команду [s][save_image][e].

По сценарию PLC сообщает tcp-клиенту (сервису camera), что объект
на линии подъехал к камере и пора делать снимок.
"""

import logging
import os
import socket
import sys

TRIGGER_MESSAGE = "[s][save_image][e]"


class PlcServer:
  def __init__(self, host: str, port: int, interval_sec: float) -> None:
    self._host = host
    self._port = port
    self._interval_sec = interval_sec

  def _handle_connection(self, conn: socket.socket, addr) -> None:
    logging.info(f"Connected by {addr}")
    try:
      while True:
        conn.sendall(TRIGGER_MESSAGE.encode("utf-8"))
        logging.info(f"Sent to {addr}: {TRIGGER_MESSAGE}")
        if self._wait_or_disconnect(conn):
          break
    except (ConnectionResetError, BrokenPipeError, OSError):
      logging.info(f"Client {addr} closed connection.")
    finally:
      conn.close()

  def _wait_or_disconnect(self, conn: socket.socket) -> bool:
    """Ждёт интервал до следующего триггера; True, если клиент отключился."""
    conn.settimeout(self._interval_sec)
    try:
      data = conn.recv(1024)
      if not data:
        logging.info("Client disconnected...")
        return True
      logging.info(f"Got message from client: {data.decode('utf-8')}")
    except socket.timeout:
      pass
    return False

  def run(self) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
      sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      sock.bind((self._host, self._port))
      sock.listen()
      logging.info(f"PLC server is listening on {self._host}:{self._port}")
      while True:
        conn, addr = sock.accept()
        self._handle_connection(conn, addr)


def main() -> None:
  logging.basicConfig(level=os.getenv("LOGGING_LEVEL", "INFO"))
  host = os.getenv("TCP_HOST", "0.0.0.0")
  port = int(os.getenv("TCP_PORT", "4096"))
  interval_sec = float(os.getenv("PLC_INTERVAL_SEC", "10"))
  try:
    PlcServer(host, port, interval_sec).run()
  except Exception as e:
    logging.error(f"Error occurred: {e}")
    sys.exit(1)


if __name__ == "__main__":
  main()
