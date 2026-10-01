import httpx
from pydantic import ValidationError

from .api.request import SimulationQueueRequest
from .api.responses import SimulationQueueResponse
from .queue_element import SimulationQueueElement, SimulationQueueElementCreate


class QueueClientException(Exception):
    """Base exception for QueueClient errors."""

    pass


class QueueClientElementNotFoundException(QueueClientException):
    """Exception raised when a queued element is not found."""

    pass


class QueueClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def claim_element(self) -> SimulationQueueElement:
        response = httpx.get(self.base_url + "/api/queue/claim")

        if response.status_code != 200:
            if response.status_code == 404:
                msg = "No queued simulations available"
                raise QueueClientElementNotFoundException(msg)
            msg_0 = f"Failed to claim element: {response.text}"
            raise QueueClientException(msg_0)

        data = SimulationQueueResponse(**response.json())

        try:
            return SimulationQueueElement(**data.model_dump())
        except ValidationError as ex:
            msg = f"Validation error: {ex}"
            raise QueueClientException(msg) from ex

    def get_queued_simulations(self) -> list[SimulationQueueElement]:
        response = httpx.get(self.base_url + "/api/queued")

        if response.status_code != 200:
            msg = f"Failed to get queued simulations: {response.text}"
            raise QueueClientException(msg)

        data = [SimulationQueueResponse(**item) for item in response.json()]

        try:
            return [SimulationQueueElement(**item.model_dump()) for item in data]
        except ValidationError as ex:
            msg = f"Validation error: {ex}"
            raise QueueClientException(msg) from ex

    def get_queued_simulation(self, queued_element_id: str) -> SimulationQueueElement:
        response = httpx.get(self.base_url + f"/api/queue/{queued_element_id}")

        if response.status_code != 200:
            if response.status_code == 404:
                msg = f"Queue element '{queued_element_id}' not found"
                raise QueueClientElementNotFoundException(msg)
            msg_0 = f"Failed to get queued simulation: {response.text}"
            raise QueueClientException(msg_0)

        data = SimulationQueueResponse(**response.json())

        try:
            return SimulationQueueElement(**data.model_dump())
        except ValidationError as ex:
            msg = f"Validation error: {ex}"
            raise QueueClientException(msg) from ex

    def post_queued_simulation(self, request: SimulationQueueElementCreate) -> str:
        payload = SimulationQueueRequest(
            parameters=request.parameters,
            issuer=request.issuer,
            callback_url=request.callback_url,
            name=request.name,
        ).model_dump()

        response = httpx.post(self.base_url + "/api/queue", json=payload)

        if response.status_code != 201:
            msg = f"Failed to post queued simulation: {response.text}"
            raise QueueClientException(msg)

        return response.json().get("id")

    def update_queued_simulation(
        self,
        queued_element_id: str,
        parameters: dict,
        issuer: str | None = None,
        callback_url: str | None = None,
        name: str | None = None,
    ) -> SimulationQueueElement:
        payload = SimulationQueueRequest(
            parameters=parameters, issuer=issuer, callback_url=callback_url, name=name
        ).model_dump()

        response = httpx.patch(self.base_url + f"/api/queue/{queued_element_id}", json=payload)

        if response.status_code != 200:
            if response.status_code == 404:
                msg = f"Queue element '{queued_element_id}' not found"
                raise QueueClientElementNotFoundException(msg)
            msg = f"Failed to update queued simulation: {response.text}"
            raise QueueClientException(msg)

        data = SimulationQueueResponse(**response.json())

        try:
            return SimulationQueueElement(**data.model_dump())
        except ValidationError as ex:
            msg_0 = f"Validation error: {ex}"
            raise QueueClientException(msg_0) from ex

    def delete_queued_element(self, queue_id: str) -> bool:
        response = httpx.delete(self.base_url + f"/api/queue/{queue_id}")

        if response.status_code != 204:
            if response.status_code == 404:
                msg = f"Queue element '{queue_id}' not found"
                raise QueueClientElementNotFoundException(msg)
            msg = f"Failed to delete queued element: {response.text}"
            raise QueueClientException(msg)

        return True
