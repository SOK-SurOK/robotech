"""Имитация кадров камеры: чтение png из папки и разбор размеров без сторонних библиотек."""

import struct
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_dimensions(data: bytes) -> tuple[int, int]:
  """Ширина и высота png: байты 16-24 (поля width/height первого чанка IHDR)."""
  if len(data) < 24 or data[:8] != PNG_SIGNATURE:
    raise ValueError("Not a PNG file")
  width, height = struct.unpack(">II", data[16:24])
  return width, height


class FrameSource:
  """Round-robin по png-файлам папки, имитирует кадры с реальной камеры."""

  def __init__(self, images_dir: str) -> None:
    self._files = sorted(Path(images_dir).glob("*.png"))
    if not self._files:
      raise FileNotFoundError(f"No .png files in {images_dir}")
    self._index = 0

  def next_frame(self) -> tuple[str, bytes]:
    path = self._files[self._index % len(self._files)]
    self._index += 1
    return path.name, path.read_bytes()
