from pydantic import BaseModel


class ServerStatus(BaseModel):
    server: str
    domain: str
    ip: str | None = None
    dns: bool = False
    tls: bool = False
    http: bool = False
    latency_ms: int | None = None
    status: str = "unknown"


class HealthResponse(BaseModel):
    overall: str
    servers: list[ServerStatus]
    timestamp: str
