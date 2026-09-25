"""Интеграционный тест базового сценария: триггер PLC -> minio -> api -> ws -> rabbitmq.

Поднимает реальные minio и rabbitmq через testcontainers, api — через uvicorn
с временной БД, PLC заменён фейковым asyncio-сервером. Сервис camera работает
in-process, как есть.
"""

import asyncio
import json
import socket
from pathlib import Path

import aio_pika
import httpx
import pytest
import uvicorn
import websockets
from minio import Minio
from testcontainers.minio import MinioContainer
from testcontainers.rabbitmq import RabbitMqContainer

from main import create_app
from service import CameraService
from settings import Settings as CameraSettings

REPO_ROOT = Path(__file__).resolve().parents[2]

MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin123"
MINIO_BUCKET = "images"
RMQ_USER = "guest"
RMQ_PASS = "guest"
EXCHANGE = "inference.in"
ROUTING_KEY = "inference.in"
TRIGGER = b"[s][save_image][e]"


def free_port() -> int:
  with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    return s.getsockname()[1]


@pytest.fixture(scope="module")
def minio_container():
  # bitnamilegacy/minio: канонический minio/minio может быть недоступен для pull в некоторых регионах
  container = (
      MinioContainer(image="bitnamilegacy/minio:latest", access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY)
      .with_env("MINIO_ROOT_USER", MINIO_ACCESS_KEY)
      .with_env("MINIO_ROOT_PASSWORD", MINIO_SECRET_KEY)
      # /data в bitnami-сборке недоступен на запись (non-root), используем её штатную директорию
      .with_command("server /bitnami/minio/data --address :9000")
  )
  with container:
    yield container


@pytest.fixture(scope="module")
def rabbitmq_container():
  with RabbitMqContainer(image="rabbitmq:3-alpine", username=RMQ_USER, password=RMQ_PASS) as container:
    yield container


async def fake_plc(port: int, triggers: int = 5, interval: float = 0.5) -> asyncio.Server:
  async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
      for _ in range(triggers):
        writer.write(TRIGGER)
        await writer.drain()
        await asyncio.sleep(interval)
      await reader.read()  # держим соединение, пока клиент не отключится
    except (ConnectionError, asyncio.CancelledError):
      pass

  return await asyncio.start_server(handle, "127.0.0.1", port)


async def wait_http_ready(url: str, timeout: float = 15) -> None:
  async with httpx.AsyncClient() as client:
    for _ in range(int(timeout / 0.5)):
      try:
        if (await client.get(url, timeout=1)).status_code == 200:
          return
      except httpx.TransportError:
        pass
      await asyncio.sleep(0.5)
  raise TimeoutError(f"Service at {url} is not ready")


async def connect_ws(port: int, timeout: float = 15):
  for _ in range(int(timeout / 0.5)):
    try:
      return await websockets.connect(f"ws://127.0.0.1:{port}")
    except OSError:
      await asyncio.sleep(0.5)
  raise TimeoutError(f"WebSocket server on port {port} is not ready")


@pytest.mark.asyncio
async def test_plc_trigger_pipeline(minio_container, rabbitmq_container, tmp_path):
  minio_endpoint = f"{minio_container.get_container_host_ip()}:{minio_container.get_exposed_port(9000)}"
  rmq_params = rabbitmq_container.get_connection_params()
  rmq_url = f"amqp://{RMQ_USER}:{RMQ_PASS}@{rmq_params.host}:{rmq_params.port}/"

  # --- api (uvicorn + временная sqlite) ---
  api_port = free_port()
  api_server = uvicorn.Server(uvicorn.Config(
      create_app(str(tmp_path / "it.db")), host="127.0.0.1", port=api_port, log_level="warning"
  ))
  api_task = asyncio.create_task(api_server.serve())
  await wait_http_ready(f"http://127.0.0.1:{api_port}/health")

  # --- fake PLC + camera ---
  plc_port = free_port()
  plc_server = await fake_plc(plc_port)

  ws_port = free_port()
  camera_settings = CameraSettings(
      tcp_host="127.0.0.1", tcp_port=plc_port,
      ws_host="127.0.0.1", ws_port=ws_port,
      images_dir=str(REPO_ROOT / "backend_test"),
      api_base_url=f"http://127.0.0.1:{api_port}",
      minio_endpoint=minio_endpoint,
      minio_public_url=f"http://{minio_endpoint}",
      minio_access_key=MINIO_ACCESS_KEY,
      minio_secret_key=MINIO_SECRET_KEY,
      minio_bucket=MINIO_BUCKET,
      rabbitmq_url=rmq_url,
      rabbitmq_exchange=EXCHANGE,
      rabbitmq_routing_key=ROUTING_KEY,
      reconnect_delay_sec=0.5,
  )
  camera = CameraService(camera_settings)
  camera_task = asyncio.create_task(camera.run())

  ws = await connect_ws(ws_port)
  try:
    # --- событие по websocket ---
    raw = await asyncio.wait_for(ws.recv(), timeout=60)
    event = json.loads(raw)
    assert event["image_url"].startswith(f"http://{minio_endpoint}/{MINIO_BUCKET}/")
    assert event["image_url"].endswith(".png")
    assert event["width"] > 0 and event["height"] > 0
    assert "id" in event and "ts" in event

    # --- запись появилась в БД через api ---
    async with httpx.AsyncClient() as client:
      response = await client.get(f"http://127.0.0.1:{api_port}/images/{event['id']}")
      assert response.status_code == 200
      record = response.json()
      assert record["image_url"] == event["image_url"]
      assert record["width"] == event["width"] and record["height"] == event["height"]

    # --- объект реально лежит в minio ---
    minio_client = Minio(minio_endpoint, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)
    object_name = event["image_url"].rsplit("/", 1)[-1]
    stat = minio_client.stat_object(MINIO_BUCKET, object_name)
    assert stat.size > 0

    # --- сообщение дошло до очереди inference.in ---
    connection = await aio_pika.connect_robust(rmq_url)
    try:
      channel = await connection.channel()
      queue = await channel.declare_queue(ROUTING_KEY, durable=True)
      incoming = await queue.get(timeout=10, no_ack=True)
      assert incoming is not None, "Queue inference.in is empty"
      message = json.loads(incoming.body)
      assert message["image_url"].endswith(".png")
      async with httpx.AsyncClient() as client:
        assert (await client.get(f"http://127.0.0.1:{api_port}/images/{message['id']}")).status_code == 200
    finally:
      await connection.close()
  finally:
    await ws.close()
    await camera.close()
    camera_task.cancel()
    api_server.should_exit = True
    await asyncio.gather(camera_task, api_task, return_exceptions=True)
    plc_server.close()
    await plc_server.wait_closed()
