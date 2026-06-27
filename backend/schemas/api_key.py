from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ApiKeyCreate(BaseModel):
    name: str
    role: str = "VIEWER"
    allowed_accounts: list[str] = []
    expires_at: Optional[datetime] = None


class ApiKeyUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    allowed_accounts: Optional[list[str]] = None


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    role: str
    is_active: bool
    allowed_accounts: str
    expires_at: Optional[datetime]
    usage_count: int
    last_used_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyResponse):
    full_key: str
