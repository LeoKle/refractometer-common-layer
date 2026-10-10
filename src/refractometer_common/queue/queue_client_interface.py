from abc import ABC, abstractmethod

from .queue_element import SimulationQueueElement, SimulationQueueElementCreate


class QueueClientException(Exception):
    """Base exception for QueueClient errors."""

    pass


class QueueClientElementNotFoundException(QueueClientException):
    """Exception raised when a queued element is not found."""

    pass


class QueueClientInterface(ABC):
    @abstractmethod
    def claim_element(self) -> SimulationQueueElement: ...

    @abstractmethod
    def get_queued_simulations(self) -> list[SimulationQueueElement]: ...

    @abstractmethod
    def get_queued_simulation(self, queued_element_id: str) -> SimulationQueueElement: ...

    @abstractmethod
    def post_queued_simulation(self, request: SimulationQueueElementCreate) -> str: ...

    @abstractmethod
    def update_queued_simulation(
        self,
        queued_element_id: str,
        parameters: dict,
        issuer: str | None = None,
        callback_url: str | None = None,
        name: str | None = None,
    ) -> SimulationQueueElement: ...

    @abstractmethod
    def delete_queued_element(self, queue_id: str) -> bool: ...
