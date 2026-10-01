import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SimulationQueueElement:
    id: uuid.UUID
    name: str
    parameters: dict
    issued_at: datetime
    image_id: str | None = None
    completed_at: datetime | None = None
    index: int | None = None
    being_processed: bool | None = False
    issuer: str | None = None
    callback_url: str | None = None


@dataclass
class SimulationQueueElementCreate:
    parameters: dict
    issuer: str | None = None
    callback_url: str | None = None
    name: str | None = None
