from typing import Any

import httpx2
from pydantic import ValidationError

from refractometer_common.sample.api.sample_dto import SampleCreateDTO, SampleDTO
from refractometer_common.sample.interfaces.sample_client_interface import (
    CreateSampleRequest,
    SampleClientConnectionException,
    SampleClientException,
    SampleClientInterface,
    SampleClientInvalidResponseException,
    SampleClientTimeoutException,
    SampleNotFoundException,
)
from refractometer_common.sample.sample import Sample


class SampleClient(SampleClientInterface):
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_all_samples(self) -> list[Sample]:
        response = self._request("GET", "/api/samples")
        payload = self._json(response)

        if not isinstance(payload, list):
            msg = f"Expected a list of results, got {type(payload).__name__}"
            raise SampleClientInvalidResponseException(msg, response.status_code)

        return [self._to_domain(element, response.status_code) for element in payload]

    def get_sample(self, sample_id: str):
        response = self._request(
            "GET",
            f"/api/sample/{sample_id}",
            not_found_message=f"Sample '{sample_id}' not found",
        )
        return self._to_domain(self._json(response), response.status_code)

    def create_sample(self, request: CreateSampleRequest):
        payload = SampleCreateDTO(
            name=request.name, sellmeier_coefficients={"B": request.B, "C": request.C}
        ).model_dump(mode="json")

        self._request("POST", "/api/sample", json=payload)

    def update_sample(self, sample: Sample):
        payload = SampleDTO(**sample.model_dump(mode="json")).model_dump(mode="json")

        self._request(
            "PATCH",
            "/api/sample",
            json=payload,
            not_found_message=f"Sample '{sample.id}' not found",
        )

    def delete_sample(self, sample_id: str):
        self._request("DELETE", f"/api/sample/{sample_id}")

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
            raise SampleClientTimeoutException(msg) from ex
        except httpx2.HTTPStatusError as ex:
            raise self._map_status_error(ex, not_found_message) from ex
        except (httpx2.RequestError, httpx2.InvalidURL) as ex:
            msg = f"{method} {url} failed: {ex!r}"
            raise SampleClientConnectionException(msg) from ex

        return response

    @staticmethod
    def _map_status_error(
        ex: httpx2.HTTPStatusError, not_found_message: str | None
    ) -> SampleClientException:
        response = ex.response
        status = response.status_code
        detail = SampleClient._extract_detail(response)

        if status == httpx2.codes.NOT_FOUND:
            return SampleNotFoundException(
                not_found_message or f"Sample not found: {detail}", status
            )

        request = ex.request
        return SampleClientException(
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
            raise SampleClientInvalidResponseException(msg, response.status_code) from ex

    @staticmethod
    def _to_domain(element: Any, status_code: int) -> Sample:
        try:
            dto = SampleDTO.model_validate(element)
            return Sample.model_validate(dto.model_dump())
        except ValidationError as ex:
            msg = f"Validation error: {ex}"
            raise SampleClientInvalidResponseException(msg, status_code) from ex
