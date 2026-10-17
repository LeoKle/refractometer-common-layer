from pydantic import BaseModel, Field


class DetectorImageResponse(BaseModel):
    values: list[list[float]] = Field(
        ..., description="A 2D matrix representing the detector image"
    )
    shape: tuple[int, int]


class DetectorPostResponse(BaseModel):
    id: str
