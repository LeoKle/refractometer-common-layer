from abc import ABC, abstractmethod

from pydantic import BaseModel

from refractometer_common.spectrum.spectrum import Spectrum


class SpectrumClientException(Exception):
    """Base exception for SpectrumClient errors"""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class SpectrumClientConnectionException(SpectrumClientException):
    """The service could not be reached (DNS, refused connection, network error)."""


class SpectrumClientTimeoutException(SpectrumClientConnectionException):
    """The service did not answer in time."""


class SpectrumNotFoundException(SpectrumClientException):
    """The requested Spectrum does not exist."""


class SpectrumClientInvalidResponseException(SpectrumClientException):
    """The service answered, but the body was not valid JSON / not the expected schema."""


class CreateSpectrumRequest(BaseModel):
    name: str
    wavelengths: list[float]
    intensities: list[float]


class SpectrumClientInterface(ABC):
    @abstractmethod
    def get_all_spectrums(self) -> list[Spectrum]: ...

    @abstractmethod
    def get_spectrum(self, spectrum_id: str) -> Spectrum: ...

    @abstractmethod
    def create_spectrum(self, request: CreateSpectrumRequest): ...

    @abstractmethod
    def update_spectrum(self, spectrum: Spectrum): ...

    @abstractmethod
    def delete_spectrum(self, spectrum_id: str): ...
