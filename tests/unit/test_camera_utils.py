import struct

import pytest

from images import FrameSource, png_dimensions


def make_png(width: int, height: int) -> bytes:
  ihdr = struct.pack(">II", width, height) + b"\x08\x02\x00\x00\x00"
  return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr


def test_png_dimensions():
  assert png_dimensions(make_png(1920, 1080)) == (1920, 1080)


def test_png_dimensions_rejects_garbage():
  with pytest.raises(ValueError):
    png_dimensions(b"not a png at all, just bytes")


def test_frame_source_round_robin(tmp_path):
  for name in ("b.png", "a.png"):
    (tmp_path / name).write_bytes(make_png(1, 1))
  source = FrameSource(str(tmp_path))
  first = source.next_frame()
  second = source.next_frame()
  third = source.next_frame()
  # файлы отсортированы: a.png, b.png, затем по кругу снова a.png
  assert first[0] == "a.png"
  assert second[0] == "b.png"
  assert third[0] == "a.png"


def test_frame_source_empty_dir(tmp_path):
  with pytest.raises(FileNotFoundError):
    FrameSource(str(tmp_path))
