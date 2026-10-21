import uuid

from pydantic import BaseModel


class SellmeierCoefficients(BaseModel):
    B: list[float]
    C: list[float]


class Sample(BaseModel):
    id: uuid.UUID
    name: str
    sellmeier_coefficients: SellmeierCoefficients
