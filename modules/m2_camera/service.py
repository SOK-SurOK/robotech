"""Сервис camera: tcp-клиент к PLC, websocket-сервер для клиентов, minio, rabbitmq, api.

По триггеру [s][save_image][e] от PLC:
  1. Берёт кадр из папки (имитация снимка).
  2. Сохраняет изображение в minio.
  3. Создаёт запись в БД через api.
  4. Шлёт json-сообщение ws-клиентам и в очередь inference.in.
"""

import asyncio
import io
import json
import logging
import uuid
from datetime import datetime, timezone

import aio_pika
import httpx
import websockets
from minio import Minio
from websockets.asyncio.server import Server, ServerConnection, serve

from images import FrameSource, png_dimensions
from settings import Settings

TRIGGER = b"[s][save_image][e]"


class CameraService:
  def __init__(self, settings: Settings) -> None:
    self._settings = settings
    self._frames = FrameSource(settings.images_dir)
    self._minio = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
    self._ws_clients: set[ServerConnection] = set()
    self._ws_server: Server | None = None
    self._rmq_connection: aio_pika.abc.AbstractRobustConnection | None = None
    self._rmq_exchange: aio_pika.abc.AbstractExchange | None = None
    self._tcp_writer: asyncio.StreamWriter | None = None
    self._stopped = asyncio.Event()

  async def run(self) -> None:
    await self._prepare_minio()
    await self._connect_rabbitmq()
    self._ws_server = await serve(
        self._ws_handler, self._settings.ws_host, self._settings.ws_port
    )
    logging.info(f"WebSocket server is listening on {self._settings.ws_host}:{self._settings.ws_port}")
    try:
      await self._tcp_loop()
    finally:
      await self.close()

  async def close(self) -> None:
    if self._stopped.is_set():
      return
    self._stopped.set()
    if self._tcp_writer is not None:
      self._tcp_writer.close()
    if self._ws_server is not None:
      self._ws_server.close()
      await self._ws_server.wait_closed()
    if self._rmq_connection is not None:
      await self._rmq_connection.close()

  # --- infrastructure ---

  async def _prepare_minio(self) -> None:
    def _ensure_bucket() -> None:
      if not self._minio.bucket_exists(self._settings.minio_bucket):
        self._minio.make_bucket(self._settings.minio_bucket)

    while not self._stopped.is_set():
      try:
        await asyncio.to_thread(_ensure_bucket)
        logging.info(f"MinIO bucket '{self._settings.minio_bucket}' is ready")
        return
      except Exception as e:
        logging.warning(f"MinIO is not ready ({e}), retry in {self._settings.reconnect_delay_sec}s")
        await asyncio.sleep(self._settings.reconnect_delay_sec)

  async def _connect_rabbitmq(self) -> None:
    while not self._stopped.is_set():
      try:
        self._rmq_connection = await aio_pika.connect_robust(self._settings.rabbitmq_url)
        channel = await self._rmq_connection.channel(publisher_confirms=True)
        exchange = await channel.declare_exchange(
            self._settings.rabbitmq_exchange, aio_pika.ExchangeType.DIRECT, durable=True
        )
        queue = await channel.declare_queue(self._settings.rabbitmq_routing_key, durable=True)
        await queue.bind(exchange, routing_key=self._settings.rabbitmq_routing_key)
        self._rmq_exchange = exchange
        logging.info(f"Connected to RabbitMQ, exchange '{self._settings.rabbitmq_exchange}' is ready")
        return
      except Exception as e:
        logging.warning(f"RabbitMQ is not ready ({e}), retry in {self._settings.reconnect_delay_sec}s")
        await asyncio.sleep(self._settings.reconnect_delay_sec)

  async def _ws_handler(self, websocket: ServerConnection) -> None:
    self._ws_clients.add(websocket)
    logging.info(f"WS client connected: {websocket.remote_address}")
    try:
      await websocket.wait_closed()
    finally:
      self._ws_clients.discard(websocket)
      logging.info(f"WS client disconnected: {websocket.remote_address}")

  # --- tcp client to PLC ---

  async def _tcp_loop(self) -> None:
    address = f"{self._settings.tcp_host}:{self._settings.tcp_port}"
    while not self._stopped.is_set():
      try:
        reader, writer = await asyncio.open_connection(self._settings.tcp_host, self._settings.tcp_port)
        self._tcp_writer = writer
        logging.info(f"Connected to PLC: {address}")
        buffer = b""
        while not self._stopped.is_set():
          chunk = await reader.read(1024)
          if not chunk:
            logging.info(f"PLC {address} closed connection")
            break
          buffer += chunk
          while TRIGGER in buffer:
            _, buffer = buffer.split(TRIGGER, 1)
            logging.info(f"Got trigger from PLC: {TRIGGER.decode()}")
            await self._handle_trigger()
        writer.close()
      except (ConnectionRefusedError, OSError) as e:
        logging.warning(f"PLC {address} is unavailable ({e})")
      if not self._stopped.is_set():
        logging.info(f"Reconnecting to PLC in {self._settings.reconnect_delay_sec}s...")
        await asyncio.sleep(self._settings.reconnect_delay_sec)

  # --- trigger pipeline ---

  async def _handle_trigger(self) -> None:
    frame_name, data = await asyncio.to_thread(self._frames.next_frame)
    width, height = png_dimensions(data)
    object_name = f"{uuid.uuid4()}.png"
    await asyncio.to_thread(self._upload_frame, object_name, data)
    image_url = f"{self._settings.minio_public_url}/{self._settings.minio_bucket}/{object_name}"
    logging.info(f"Frame '{frame_name}' saved to minio: {image_url}")

    record = await self._create_record(image_url, width, height)
    message = {
        "id": record["id"],
        "image_url": image_url,
        "width": width,
        "height": height,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    payload = json.dumps(message)
    websockets.broadcast(self._ws_clients, payload)
    await self._publish(payload)
    logging.info(f"Frame processed: {payload}")

  def _upload_frame(self, object_name: str, data: bytes) -> None:
    self._minio.put_object(
        self._settings.minio_bucket,
        object_name,
        io.BytesIO(data),
        length=len(data),
        content_type="image/png",
    )

  async def _create_record(self, image_url: str, width: int, height: int) -> dict:
    async with httpx.AsyncClient(base_url=self._settings.api_base_url, timeout=10) as client:
      response = await client.post(
          "/images/", json={"image_url": image_url, "width": width, "height": height}
      )
      response.raise_for_status()
      return response.json()

  async def _publish(self, payload: str) -> None:
    await self._rmq_exchange.publish(
        aio_pika.Message(payload.encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key=self._settings.rabbitmq_routing_key,
    )
