"""Работа с sqlite: чистый SQL, без ORM (требование задания)."""

import sqlite3
from contextlib import contextmanager
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY,
    image_url TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL
)
"""


def init_db(db_path: str) -> None:
  with sqlite3.connect(db_path) as conn:
    conn.execute(SCHEMA)


@contextmanager
def connect(db_path: str) -> Iterator[sqlite3.Connection]:
  conn = sqlite3.connect(db_path)
  conn.row_factory = sqlite3.Row
  try:
    yield conn
    conn.commit()
  finally:
    conn.close()


def create_image(conn: sqlite3.Connection, image_url: str, width: int, height: int) -> sqlite3.Row:
  cursor = conn.execute(
      "INSERT INTO images (image_url, width, height) VALUES (?, ?, ?)",
      (image_url, width, height),
  )
  return conn.execute("SELECT * FROM images WHERE id = ?", (cursor.lastrowid,)).fetchone()


def get_image(conn: sqlite3.Connection, image_id: int) -> sqlite3.Row | None:
  return conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()


def list_images(conn: sqlite3.Connection) -> list[sqlite3.Row]:
  return conn.execute("SELECT * FROM images ORDER BY id").fetchall()
