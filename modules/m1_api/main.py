"""CRUD API поверх sqlite: создание, чтение по id и список записей об изображениях."""

import logging
import os

import uvicorn
from fastapi import FastAPI, HTTPException, status

from db import connect, create_image, get_image, init_db, list_images
from schemas import ImageCreate, ImageOut

logger = logging.getLogger(__name__)


def create_app(db_path: str) -> FastAPI:
  init_db(db_path)
  app = FastAPI(version="0.1.0", title="synetra api")

  @app.post("/images/", response_model=ImageOut, status_code=status.HTTP_201_CREATED)
  def post_image(item: ImageCreate) -> ImageOut:
    with connect(db_path) as conn:
      row = create_image(conn, item.image_url, item.width, item.height)
    logger.info(f"Created image record: id={row['id']}")
    return ImageOut(**dict(row))

  @app.get("/images/{image_id}", response_model=ImageOut)
  def get_image_by_id(image_id: int) -> ImageOut:
    with connect(db_path) as conn:
      row = get_image(conn, image_id)
    if row is None:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return ImageOut(**dict(row))

  @app.get("/images/", response_model=list[ImageOut])
  def get_images() -> list[ImageOut]:
    with connect(db_path) as conn:
      rows = list_images(conn)
    return [ImageOut(**dict(row)) for row in rows]

  @app.get("/health")
  def health() -> dict:
    return {"status": "ok"}

  return app


app = create_app(os.getenv("DB_PATH", "./excercise.db"))

if __name__ == "__main__":
  uvicorn.run(
      app,
      host=os.getenv("API_HOST", "0.0.0.0"),
      port=int(os.getenv("API_PORT", "8000")),
  )
