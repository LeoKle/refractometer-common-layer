import uuid
from typing import Any

import httpx2
from pydantic import ValidationError

from refractometer_common.queue.api.request import SimulationQueueRequest
from refractometer_common.queue.api.responses import (
    SimulationQueuePostResponse,
    SimulationQueueResponse,
)
from refractometer_common.queue.queue_client_interface import (
    QueueClientConnectionException,
    QueueClientElementNotFoundException,
    QueueClientException,
    QueueClientInterface,
    QueueClientInvalidResponseException,
    QueueClientTimeoutException,
)
from refractometer_common.queue.queue_element import (
    SimulationQueueElement,
    SimulationQueueElementCreate,
)


class QueueClient(QueueClientInterface):
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def claim_element(self) -> SimulationQueueElement:
        response = self._request(
            "GET",
            "/api/queue/claim",
            not_found_message="No queued simulations available",
        )
        return self._to_domain(self._json(response), response.status_code)

    def get_queued_simulations(self) -> list[SimulationQueueElement]:
        response = self._request("GET", "/api/queued")
        payload = self._json(response)

        if not isinstance(payload, list):
            msg = f"Expected a list of queue elements, got {type(payload).__name__}"
            raise QueueClientInvalidResponseException(msg, response.status_code)

        return [self._to_domain(element, response.status_code) for element in payload]

    def get_queued_simulation(self, queued_element_id: str | uuid.UUID) -> SimulationQueueElement:
        response = self._request(
            "GET",
            f"/api/queue/{queued_element_id}",
            not_found_message=f"Queue element '{queued_element_id}' not found",
        )
        return self._to_domain(self._json(response), response.status_code)

    def post_queued_simulation(self, request: SimulationQueueElementCreate) -> str:
        payload = SimulationQueueRequest(
            parameters=request.parameters,
            issuer=request.issuer,
            callback_url=request.callback_url,
            name=request.name,
        ).model_dump(mode="json")

        response = self._request("POST", "/api/queue", json=payload)
        return self._to_post_result(self._json(response), response.status_code).id

    def update_queued_simulation(
        self,
        queued_element_id: str | uuid.UUID,
        parameters: dict,
        issuer: str | None = None,
        callback_url: str | None = None,
        name: str | None = None,
    ) -> SimulationQueueElement:
        payload = SimulationQueueRequest(
            parameters=parameters,
            issuer=issuer,
            callback_url=callback_url,
            name=name,
        ).model_dump(mode="json")

        response = self._request(
            "PATCH",
            f"/api/queue/{queued_element_id}",
            json=payload,
            not_found_message=f"Queue element '{queued_element_id}' not found",
        )
        return self._to_domain(self._json(response), response.status_code)

    def delete_queued_element(self, queue_id: str | uuid.UUID) -> bool:
        self._request(
            "DELETE",
            f"/api/queue/{queue_id}",
            not_found_message=f"Queue element '{queue_id}' not found",
        )
        return True

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
            raise QueueClientTimeoutException(msg) from ex
        except httpx2.HTTPStatusError as ex:
            raise self._map_status_error(ex, not_found_message) from ex
        except (httpx2.RequestError, httpx2.InvalidURL) as ex:
            msg = f"{method} {url} failed: {ex!r}"
            raise QueueClientConnectionException(msg) from ex

        return response

    @staticmethod
    def _map_status_error(
        ex: httpx2.HTTPStatusError, not_found_message: str | None
    ) -> QueueClientException:
        response = ex.response
        status = response.status_code
        detail = QueueClient._extract_detail(response)

        if status == httpx2.codes.NOT_FOUND:
            return QueueClientElementNotFoundException(
                not_found_message or f"Queue element not found: {detail}", status
            )

        request = ex.request
        return QueueClientException(
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
            raise QueueClientInvalidResponseException(msg, response.status_code) from ex

    @staticmethod
    def _to_domain(element: Any, status_code: int) -> SimulationQueueElement:
        try:
            dto = SimulationQueueResponse.model_validate(element)
            return SimulationQueueElement.model_validate(dto.model_dump())
        except ValidationError as ex:
            msg = f"Validation error: {ex}"
            raise QueueClientInvalidResponseException(msg, status_code) from ex

    @staticmethod
    def _to_post_result(element: Any, status_code: int) -> SimulationQueuePostResponse:
        try:
            return SimulationQueuePostResponse.model_validate(element)
        except ValidationError as ex:
            msg = f"Validation error: {ex}"
            raise QueueClientInvalidResponseException(msg, status_code) from ex
