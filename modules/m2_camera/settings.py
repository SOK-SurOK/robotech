"""Настройки модуля camera: читаются из переменных окружения."""

import os
from dataclasses import dataclass


@dataclass
class Settings:
  tcp_host: str
  tcp_port: int
  ws_host: str
  ws_port: int
  images_dir: str
  api_base_url: str
  minio_endpoint: str
  minio_public_url: str
  minio_access_key: str
  minio_secret_key: str
  minio_bucket: str
  rabbitmq_url: str
  rabbitmq_exchange: str
  rabbitmq_routing_key: str
  reconnect_delay_sec: float

  @classmethod
  def from_env(cls) -> "Settings":
    rmq_user = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
    rmq_pass = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
    rmq_host = os.getenv("RABBITMQ_HOST", "localhost")
    rmq_port = os.getenv("RABBITMQ_PORT", "5672")
    return cls(
        tcp_host=os.getenv("TCP_HOST", "localhost"),
        tcp_port=int(os.getenv("TCP_PORT", "4096")),
        ws_host=os.getenv("WS_HOST", "0.0.0.0"),
        ws_port=int(os.getenv("WS_PORT", "1234")),
        images_dir=os.getenv("IMAGES_DIR", "./backend_test"),
        api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        minio_public_url=os.getenv("MINIO_PUBLIC_URL", "http://localhost:9000"),
        minio_access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
        minio_secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
        minio_bucket=os.getenv("MINIO_BUCKET", "images"),
        rabbitmq_url=f"amqp://{rmq_user}:{rmq_pass}@{rmq_host}:{rmq_port}/",
        rabbitmq_exchange=os.getenv("RABBITMQ_EXCHANGE", "inference.in"),
        rabbitmq_routing_key=os.getenv("RABBITMQ_ROUTING_KEY", "inference.in"),
        reconnect_delay_sec=float(os.getenv("RECONNECT_DELAY_SEC", "5")),
    )
