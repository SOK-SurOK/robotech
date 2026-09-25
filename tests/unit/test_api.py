import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture()
def client(tmp_path):
  return TestClient(create_app(str(tmp_path / "test.db")))


def test_create_image(client):
  response = client.post("/images/", json={"image_url": "http://minio/images/1.png", "width": 640, "height": 480})
  assert response.status_code == 201
  body = response.json()
  assert body["id"] == 1
  assert body["image_url"] == "http://minio/images/1.png"
  assert body["width"] == 640
  assert body["height"] == 480


def test_get_image_by_id(client):
  created = client.post("/images/", json={"image_url": "http://minio/images/2.png", "width": 100, "height": 200}).json()
  response = client.get(f"/images/{created['id']}")
  assert response.status_code == 200
  assert response.json() == created


def test_get_image_not_found(client):
  response = client.get("/images/999")
  assert response.status_code == 404


def test_list_images(client):
  client.post("/images/", json={"image_url": "http://minio/images/a.png", "width": 10, "height": 10})
  client.post("/images/", json={"image_url": "http://minio/images/b.png", "width": 20, "height": 20})
  response = client.get("/images/")
  assert response.status_code == 200
  body = response.json()
  assert len(body) == 2
  assert [row["id"] for row in body] == [1, 2]


def test_create_image_validation(client):
  response = client.post("/images/", json={"image_url": "", "width": 0, "height": -1})
  assert response.status_code == 422
