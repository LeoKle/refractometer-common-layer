from pydantic import BaseModel


class SellmeierCoefficientsDTO(BaseModel):
    B: list[float]
    C: list[float]


class SampleDTO(BaseModel):
    name: str
    id: str
    sellmeier_coefficients: SellmeierCoefficientsDTO


class SampleCreateDTO(BaseModel):
    name: str
    sellmeier_coefficients: SellmeierCoefficientsDTO
