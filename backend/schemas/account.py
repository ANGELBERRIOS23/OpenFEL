from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AccountBranding(BaseModel):
    color_primario: str = ""
    color_secundario: str = ""
    telefono: str = ""
    email: str = ""
    web: str = ""
    logo_b64: Optional[str] = None


class AccountCreate(BaseModel):
    nit: str
    login_password: str
    cert_password: str
    preferred_api: str = "mixed"
    affiliation: str = "GEN"
    name: str = ""


class AccountUpdate(BaseModel):
    login_password: Optional[str] = None
    cert_password: Optional[str] = None
    preferred_api: Optional[str] = None
    affiliation: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    branding: Optional[AccountBranding] = None


class AccountResponse(BaseModel):
    nit: str
    name: str
    affiliation: str
    preferred_api: str
    status: str
    branding: Optional[AccountBranding] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_account(cls, account) -> "AccountResponse":
        branding = None
        if any([account.color_primario, account.color_secundario, account.telefono,
                account.email, account.web, account.logo_b64]):
            branding = AccountBranding(
                color_primario=account.color_primario or "",
                color_secundario=account.color_secundario or "",
                telefono=account.telefono or "",
                email=account.email or "",
                web=account.web or "",
                logo_b64=account.logo_b64 or None,
            )
        return cls(
            nit=account.nit,
            name=account.name,
            affiliation=account.affiliation,
            preferred_api=account.preferred_api,
            status=account.status,
            branding=branding,
            created_at=account.created_at,
        )
