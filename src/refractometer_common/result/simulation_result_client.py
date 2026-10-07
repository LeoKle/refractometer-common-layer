import uuid
from datetime import datetime
from typing import Any

import httpx2
from pydantic import ValidationError

from refractometer_common.result.api.requests import (
    CreateSimulationResultRequest,
    PatchSimulationResultRequest,
)
from refractometer_common.result.api.responses import SimulationResultResponse
from refractometer_common.result.simulation_result import SimulationResult


class SimulationResultClientException(Exception):
    """Base exception for SimulationResultClient errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class SimulationResultClientConnectionException(SimulationResultClientException):
    """The service could not be reached (DNS, refused connection, network error)."""


class SimulationResultClientTimeoutException(SimulationResultClientConnectionException):
    """The service did not answer in time."""


class SimulationResultNotFoundException(SimulationResultClientException):
    """The requested simulation result does not exist."""


class SimulationResultClientInvalidResponseException(SimulationResultClientException):
    """The service answered, but the body was not valid JSON / not the expected schema."""


class SimulationResultClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_results(self) -> list[SimulationResult]:
        response = self._request("GET", "/api/results")
        payload = self._json(response)

        if not isinstance(payload, list):
            msg = f"Expected a list of results, got {type(payload).__name__}"
            raise SimulationResultClientInvalidResponseException(msg, response.status_code)

        return [self._to_domain(element, response.status_code) for element in payload]

    def get_result(self, result_id: str | uuid.UUID) -> SimulationResult:
        response = self._request(
            "GET",
            f"/api/result/{result_id}",
            not_found_message=f"Simulation result '{result_id}' not found",
        )
        return self._to_domain(self._json(response), response.status_code)

    def create_result(
        self,
        parameters: dict,
        image_id: str,
        issued_at: datetime,
        completed_at: datetime,
    ) -> SimulationResult:
        payload = CreateSimulationResultRequest(
            parameters=parameters,
            image_id=image_id,
            issued_at=issued_at,
            completed_at=completed_at,
        ).model_dump(mode="json")  # mode="json" -> datetimes/UUIDs become JSON-safe strings

        response = self._request("POST", "/api/result", json=payload)
        return self._to_domain(self._json(response), response.status_code)

    def update_result(self, result: SimulationResult) -> SimulationResult:
        payload = PatchSimulationResultRequest(**result.model_dump()).model_dump(mode="json")

        response = self._request(
            "PATCH",
            "/api/result",
            json=payload,
            not_found_message=f"Simulation result '{result.id}' not found",
        )
        return self._to_domain(self._json(response), response.status_code)

    def delete_result(self, result_id: str | uuid.UUID) -> None:
        self._request("DELETE", f"/api/result/{result_id}")

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
            raise SimulationResultClientTimeoutException(msg) from ex
        except httpx2.HTTPStatusError as ex:
            raise self._map_status_error(ex, not_found_message) from ex
        except (httpx2.RequestError, httpx2.InvalidURL) as ex:
            msg = f"{method} {url} failed: {ex!r}"
            raise SimulationResultClientConnectionException(msg) from ex

        return response

    @staticmethod
    def _map_status_error(
        ex: httpx2.HTTPStatusError, not_found_message: str | None
    ) -> SimulationResultClientException:
        response = ex.response
        status = response.status_code
        detail = SimulationResultClient._extract_detail(response)

        if status == httpx2.codes.NOT_FOUND:
            return SimulationResultNotFoundException(
                not_found_message or f"Simulation result not found: {detail}", status
            )

        request = ex.request
        return SimulationResultClientException(
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
            raise SimulationResultClientInvalidResponseException(msg, response.status_code) from ex

    @staticmethod
    def _to_domain(element: Any, status_code: int) -> SimulationResult:
        try:
            dto = SimulationResultResponse.model_validate(element)
            return SimulationResult.model_validate(dto.model_dump())
        except ValidationError as ex:
            msg = f"Validation error: {ex}"
            raise SimulationResultClientInvalidResponseException(msg, status_code) from ex
