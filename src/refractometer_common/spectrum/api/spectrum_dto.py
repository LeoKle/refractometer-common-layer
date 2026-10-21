import uuid

from pydantic import BaseModel


class SpectrumDTO(BaseModel):
    name: str
    id: uuid.UUID
    wavelengths: list[float]
    intensities: list[float]


class SpectrumCreateDTO(BaseModel):
    name: str
    wavelengths: list[float]
    intensities: list[float]
