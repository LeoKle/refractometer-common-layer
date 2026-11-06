import uuid
from abc import ABC, abstractmethod

from refractometer_common.queue.queue_element import (
    SimulationQueueElement,
    SimulationQueueElementCreate,
)


class QueueClientException(Exception):
    """Base exception for QueueClient errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class QueueClientConnectionException(QueueClientException):
    """The service could not be reached (DNS, refused connection, network error)."""


class QueueClientTimeoutException(QueueClientConnectionException):
    """The service did not answer in time."""


class QueueClientElementNotFoundException(QueueClientException):
    """The requested queue element does not exist, or the queue is empty when claiming."""


class QueueClientInvalidResponseException(QueueClientException):
    """The service answered, but the body was not valid JSON / not the expected schema."""


class QueueClientInterface(ABC):
    @abstractmethod
    def claim_element(self) -> SimulationQueueElement:
        """Claim the next queued simulation and mark it as being processed.

        Raises QueueClientElementNotFoundException if no simulation is queued.
        """

    @abstractmethod
    def get_queued_simulations(self) -> list[SimulationQueueElement]: ...

    @abstractmethod
    def get_queued_simulation(
        self, queued_element_id: str | uuid.UUID
    ) -> SimulationQueueElement: ...

    @abstractmethod
    def post_queued_simulation(self, request: SimulationQueueElementCreate) -> str: ...

    @abstractmethod
    def update_queued_simulation(
        self,
        queued_element_id: str | uuid.UUID,
        parameters: dict,
        issuer: str | None = None,
        callback_url: str | None = None,
        name: str | None = None,
    ) -> SimulationQueueElement: ...

    @abstractmethod
    def delete_queued_element(self, queue_id: str | uuid.UUID) -> bool: ...
