import uuid
from abc import ABC, abstractmethod
from datetime import datetime

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


class SimulationResultClientInterface(ABC):
    @abstractmethod
    def get_results(self) -> list[SimulationResult]: ...

    @abstractmethod
    def get_result(self, result_id: str | uuid.UUID) -> SimulationResult: ...

    @abstractmethod
    def create_result(
        self,
        parameters: dict,
        image_id: str,
        issued_at: datetime,
        completed_at: datetime,
    ) -> SimulationResult: ...

    @abstractmethod
    def update_result(self, result: SimulationResult) -> SimulationResult: ...

    @abstractmethod
    def delete_result(self, result_id: str | uuid.UUID) -> None: ...
