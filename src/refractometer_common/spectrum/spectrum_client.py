from typing import Any

import httpx2
from pydantic import ValidationError

from refractometer_common.spectrum.api.spectrum_dto import SpectrumCreateDTO, SpectrumDTO
from refractometer_common.spectrum.interfaces.spectrum_client_interface import (
    CreateSpectrumRequest,
    SpectrumClientConnectionException,
    SpectrumClientException,
    SpectrumClientInterface,
    SpectrumClientInvalidResponseException,
    SpectrumClientTimeoutException,
    SpectrumNotFoundException,
)
from refractometer_common.spectrum.spectrum import Spectrum


class SpectrumClient(SpectrumClientInterface):
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_all_spectrums(self) -> list[Spectrum]:
        response = self._request("GET", "/api/spectrums")
        payload = self._json(response)

        if not isinstance(payload, list):
            msg = f"Expected a list of results, got {type(payload).__name__}"
            raise SpectrumClientInvalidResponseException(msg, response.status_code)

        return [self._to_domain(element, response.status_code) for element in payload]

    def get_spectrum(self, spectrum_id: str) -> Spectrum:
        response = self._request(
            "GET",
            f"/api/spectrum/{spectrum_id}",
            not_found_message=f"Spectrum '{spectrum_id}' not found",
        )
        return self._to_domain(self._json(response), response.status_code)

    def create_spectrum(self, request: CreateSpectrumRequest):
        payload = SpectrumCreateDTO(
            name=request.name, wavelengths=request.wavelengths, intensities=request.intensities
        ).model_dump(mode="json")

        self._request("POST", "/api/spectrum", json=payload)

    def update_spectrum(self, spectrum: Spectrum):
        payload = SpectrumDTO(**spectrum.model_dump(mode="json")).model_dump(mode="json")

        self._request(
            "PATCH",
            "/api/spectrum",
            json=payload,
            not_found_message=f"Spectrum '{spectrum.id}' not found",
        )

    def delete_spectrum(self, spectrum_id: str):
        self._request("DELETE", f"/api/spectrum/{spectrum_id}")

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
            raise SpectrumClientTimeoutException(msg) from ex
        except httpx2.HTTPStatusError as ex:
            raise self._map_status_error(ex, not_found_message) from ex
        except (httpx2.RequestError, httpx2.InvalidURL) as ex:
            msg = f"{method} {url} failed: {ex!r}"
            raise SpectrumClientConnectionException(msg) from ex

        return response

    @staticmethod
    def _map_status_error(
        ex: httpx2.HTTPStatusError, not_found_message: str | None
    ) -> SpectrumClientException:
        response = ex.response
        status = response.status_code
        detail = SpectrumClient._extract_detail(response)

        if status == httpx2.codes.NOT_FOUND:
            return SpectrumNotFoundException(
                not_found_message or f"Spectrum not found: {detail}", status
            )

        request = ex.request
        return SpectrumClientException(
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
            raise SpectrumClientInvalidResponseException(msg, response.status_code) from ex

    @staticmethod
    def _to_domain(element: Any, status_code: int) -> Spectrum:
        try:
            dto = SpectrumDTO.model_validate(element)
            return Spectrum.model_validate(dto.model_dump())
        except ValidationError as ex:
            msg = f"Validation error: {ex}"
            raise SpectrumClientInvalidResponseException(msg, status_code) from ex
