import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateSimulationResultRequest(BaseModel):
    parameters: dict
    image_id: str
    issued_at: datetime
    completed_at: datetime


class PatchSimulationResultRequest(BaseModel):
    id: uuid.UUID
    parameters: dict
    image_id: str
    issued_at: datetime
    completed_at: datetime
