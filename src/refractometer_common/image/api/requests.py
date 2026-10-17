from pydantic import BaseModel, Field


class DetectorImageCreateRequest(BaseModel):
    values: list[list[float]] = Field(
        ..., description="A 2D matrix representing the detector image"
    )
    shape: tuple[int, int]
