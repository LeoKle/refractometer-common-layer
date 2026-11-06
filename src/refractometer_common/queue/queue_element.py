import uuid
from datetime import datetime

from pydantic import BaseModel


class SimulationQueueElement(BaseModel):
    id: uuid.UUID
    parameters: dict
    issued_at: datetime
    name: str | None = None
    index: int | None = None
    being_processed: bool | None = False
    issuer: str | None = None
    callback_url: str | None = None


class SimulationQueueElementCreate(BaseModel):
    parameters: dict
    issuer: str | None = None
    callback_url: str | None = None
    name: str | None = None
