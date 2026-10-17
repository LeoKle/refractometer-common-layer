from abc import ABC, abstractmethod

from pydantic import BaseModel

from refractometer_common.image.image import Image


class CreateImageRequest(BaseModel):
    values: list[list[float]]
    shape: tuple[int, int]


class ImageClientException(Exception):
    """Base exception for ImageClient errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ImageClientConnectionException(ImageClientException):
    """The service could not be reached (DNS, refused connection, network error)."""


class ImageClientTimeoutException(ImageClientConnectionException):
    """The service did not answer in time."""


class ImageNotFoundException(ImageClientException):
    """The requested image does not exist."""


class ImageClientInvalidResponseException(ImageClientException):
    """The service answered, but the body was not valid JSON / not the expected schema."""


class ImageClientInterface(ABC):
    @abstractmethod
    def get_image(self, image_id: str) -> Image: ...

    @abstractmethod
    def post_image(self, request: CreateImageRequest) -> str: ...
