from typing import Any

import httpx2
from pydantic import ValidationError

from refractometer_common.image.api.requests import DetectorImageCreateRequest
from refractometer_common.image.api.responses import DetectorImageResponse, DetectorPostResponse
from refractometer_common.image.image import Image
from refractometer_common.image.image_client_interface import (
    CreateImageRequest,
    ImageClientConnectionException,
    ImageClientException,
    ImageClientInterface,
    ImageClientInvalidResponseException,
    ImageClientTimeoutException,
    ImageNotFoundException,
)


class ImageClient(ImageClientInterface):
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_image(self, image_id: str) -> Image:
        response = self._request(
            "GET",
            f"/api/image/{image_id}",
            not_found_message=f"Image '{image_id}' not found",
        )
        return self._to_domain(self._json(response), response.status_code)

    def post_image(self, request: CreateImageRequest) -> str:
        try:
            payload = DetectorImageCreateRequest.model_validate(request.model_dump())
        except ValidationError as ex:
            msg = f"Invalid image create request: {ex}"
            raise ImageClientException(msg) from ex

        response = self._request("POST", "/api/image", json=payload.model_dump(mode="json"))

        return self._to_post_result(self._json(response), response.status_code).id

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        not_found_message: str | None = None,
    ) -> httpx2.Response:
        url = f"{self.base_url}{path}"

        try:
            with httpx2.Client(timeout=self.timeout) as client:
                response = client.request(method, url, json=json)
            response.raise_for_status()
        except httpx2.TimeoutException as ex:  # must come before RequestError
            msg = f"{method} {url} timed out after {self.timeout}s"
            raise ImageClientTimeoutException(msg) from ex
        except httpx2.HTTPStatusError as ex:
            raise self._map_status_error(ex, not_found_message) from ex
        except (httpx2.RequestError, httpx2.InvalidURL) as ex:
            msg = f"{method} {url} failed: {ex!r}"
            raise ImageClientConnectionException(msg) from ex
        except httpx2.HTTPError as ex:  # safety net for any other httpx error
            msg = f"{method} {url} failed unexpectedly: {ex!r}"
            raise ImageClientException(msg) from ex

        return response

    @staticmethod
    def _map_status_error(
        ex: httpx2.HTTPStatusError,
        not_found_message: str | None,
    ) -> ImageClientException:
        response = ex.response
        status = response.status_code
        detail = ImageClient._extract_detail(response)

        if status == httpx2.codes.NOT_FOUND:
            return ImageNotFoundException(not_found_message or f"Image not found: {detail}", status)

        request = ex.request
        return ImageClientException(
            f"{request.method} {request.url} returned {status}: {detail}", status
        )

    @staticmethod
    def _extract_detail(response: httpx2.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
        return response.text

    @staticmethod
    def _json(response: httpx2.Response) -> Any:
        try:
            return response.json()
        except ValueError as ex:
            msg = f"Response from {response.request.url} is not valid JSON"
            raise ImageClientInvalidResponseException(msg, response.status_code) from ex

    @staticmethod
    def _to_domain(element: Any, status_code: int) -> Image:
        try:
            dto = DetectorImageResponse.model_validate(element)
            return Image.model_validate(dto.model_dump())
        except ValidationError as ex:
            msg = f"Validation error: {ex}"
            raise ImageClientInvalidResponseException(msg, status_code) from ex

    @staticmethod
    def _to_post_result(element: Any, status_code: int) -> DetectorPostResponse:
        try:
            return DetectorPostResponse.model_validate(element)
        except ValidationError as ex:
            msg = f"Validation error: {ex}"
            raise ImageClientInvalidResponseException(msg, status_code) from ex
