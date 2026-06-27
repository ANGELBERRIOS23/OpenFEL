from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_role, Role
from backend.database import get_db
from backend.models.api_key import ApiKey
from backend.schemas.account import AccountCreate, AccountUpdate, AccountResponse
from backend.services import account_service

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    return await account_service.list_accounts(db)


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(
    body: AccountCreate,
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    existing = await account_service.get_account(db, body.nit)
    if existing:
        raise HTTPException(409, f"Account {body.nit} already exists")

    account = await account_service.create_account(
        db,
        nit=body.nit,
        login_password=body.login_password,
        cert_password=body.cert_password,
        preferred_api=body.preferred_api,
        affiliation=body.affiliation,
        name=body.name,
    )
    return account


@router.get("/{nit}", response_model=AccountResponse)
async def get_account(
    nit: str,
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    account = await account_service.get_account(db, nit)
    if not account:
        raise HTTPException(404, "Account not found")
    return account


@router.patch("/{nit}", response_model=AccountResponse)
async def update_account(
    nit: str,
    body: AccountUpdate,
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    updated = await account_service.update_account(
        db,
        nit=nit,
        login_password=body.login_password,
        cert_password=body.cert_password,
        preferred_api=body.preferred_api,
        affiliation=body.affiliation,
        name=body.name,
        status=body.status,
    )
    if not updated:
        raise HTTPException(404, "Account not found")
    return updated


@router.delete("/{nit}", status_code=204)
async def delete_account(
    nit: str,
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    if not await account_service.delete_account(db, nit):
        raise HTTPException(404, "Account not found")
