from pydantic import BaseModel


class SimulationQueueRequest(BaseModel):
    parameters: dict

    issuer: str | None = None
    callback_url: str | None = None
    name: str | None = None
