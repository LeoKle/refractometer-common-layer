import uuid

from pydantic import BaseModel


class Spectrum(BaseModel):
    name: str
    id: uuid.UUID
    wavelengths: list[float]
    intensities: list[float]
