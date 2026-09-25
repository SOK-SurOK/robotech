import asyncio
import logging
import os
import sys

from service import CameraService
from settings import Settings


def main() -> None:
  logging.basicConfig(level=os.getenv("LOGGING_LEVEL", "INFO"))
  settings = Settings.from_env()
  logging.info(f"Starting camera service, PLC: {settings.tcp_host}:{settings.tcp_port}")
  try:
    asyncio.run(CameraService(settings).run())
  except KeyboardInterrupt:
    logging.info("Camera service stopped")
  except Exception as e:
    logging.error(f"Error occurred: {e}")
    sys.exit(1)


if __name__ == "__main__":
  main()
