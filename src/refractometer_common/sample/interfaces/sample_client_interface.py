from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from refractometer_common.sample.sample import Sample


class SampleClientException(Exception):
    """Base exception for SampleClient errors"""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class SampleClientConnectionException(SampleClientException):
    """The service could not be reached (DNS, refused connection, network error)."""


class SampleClientTimeoutException(SampleClientConnectionException):
    """The service did not answer in time."""


class SampleNotFoundException(SampleClientException):
    """The requested sample does not exist."""


class SampleClientInvalidResponseException(SampleClientException):
    """The service answered, but the body was not valid JSON / not the expected schema."""


class CreateSampleRequest(BaseModel):
    name: str
    B: list[float] = Field(..., max_length=3, min_length=3)
    C: list[float] = Field(..., max_length=3, min_length=3)


class SampleClientInterface(ABC):
    @abstractmethod
    def get_all_samples(self) -> list[Sample]: ...

    @abstractmethod
    def get_sample(self, sample_id: str) -> Sample: ...

    @abstractmethod
    def create_sample(self, request: CreateSampleRequest): ...

    @abstractmethod
    def update_sample(self, sample: Sample): ...

    @abstractmethod
    def delete_sample(self, sample_id: str): ...
