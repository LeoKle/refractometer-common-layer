from types import TracebackType
from typing import Any, Self

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

# Keep every pooled connection alive: callers (e.g. the API gateway threadpool) issue many
# concurrent requests, and httpx2's default of 20 keep-alive connections causes connection churn.
DEFAULT_LIMITS = httpx2.Limits(max_connections=100, max_keepalive_connections=100)


class SpectrumClient(SpectrumClientInterface):
    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        *,
        http_client: httpx2.Client | None = None,
        limits: httpx2.Limits | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._owns_client = http_client is None
        self._client = (
            http_client
            if http_client is not None
            else httpx2.Client(timeout=timeout, limits=limits or DEFAULT_LIMITS)
        )

    def close(self) -> None:
        """Close the underlying connection pool if this instance created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

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

    def create_spectrum(self, request: CreateSpectrumRequest) -> Spectrum:
        payload = SpectrumCreateDTO(
            name=request.name, wavelengths=request.wavelengths, intensities=request.intensities
        ).model_dump(mode="json")

        response = self._request("POST", "/api/spectrum", json=payload)
        return self._to_domain(self._json(response), response.status_code)

    def update_spectrum(self, spectrum: Spectrum) -> Spectrum:
        payload = SpectrumDTO(**spectrum.model_dump(mode="json")).model_dump(mode="json")

        response = self._request(
            "PATCH",
            "/api/spectrum",
            json=payload,
            not_found_message=f"Spectrum '{spectrum.id}' not found",
        )
        return self._to_domain(self._json(response), response.status_code)

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
            response = self._client.request(method, url, json=json, timeout=self.timeout)
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
