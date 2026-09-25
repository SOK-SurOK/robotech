from pydantic import BaseModel, Field


class ImageCreate(BaseModel):
  image_url: str = Field(min_length=1)
  width: int = Field(gt=0)
  height: int = Field(gt=0)


class ImageOut(BaseModel):
  id: int
  image_url: str
  width: int
  height: int
