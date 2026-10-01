from datetime import datetime

from pydantic import BaseModel


class SimulationQueueResponse(BaseModel):
    parameters: dict

    index: int | None = None
    being_processed: bool | None = None

    issuer: str | None = None
    callback_url: str | None = None
    id: str | None = None
    name: str | None = None
    image_id: str | None = None
    issued_at: datetime
    completed_at: datetime | None = None
