from pydantic import BaseModel


class Image(BaseModel):
    values: list[list[float]]
    shape: tuple[int, int]
