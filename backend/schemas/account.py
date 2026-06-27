from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AccountCreate(BaseModel):
    nit: str
    login_password: str
    cert_password: str
    preferred_api: str = "mobile"


class AccountUpdate(BaseModel):
    login_password: Optional[str] = None
    cert_password: Optional[str] = None
    preferred_api: Optional[str] = None
    status: Optional[str] = None


class AccountResponse(BaseModel):
    nit: str
    name: str
    affiliation: str
    preferred_api: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
