from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_role, Role
from backend.database import get_db
from backend.models.api_key import ApiKey
from backend.schemas.api_key import (
    ApiKeyCreate, ApiKeyUpdate, ApiKeyResponse, ApiKeyCreated,
)
from backend.services import api_key_service

router = APIRouter(prefix="/api/keys", tags=["API Keys"])


@router.get("", response_model=list[ApiKeyResponse])
async def list_keys(
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    return await api_key_service.list_api_keys(db)


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_key(
    body: ApiKeyCreate,
    key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    try:
        api_key, full_key = await api_key_service.create_api_key(
            db,
            name=body.name,
            role=body.role,
            allowed_accounts=body.allowed_accounts,
            expires_at=body.expires_at,
            created_by=key.key_prefix,
        )
    except KeyError:
        raise HTTPException(400, f"Invalid role: {body.role}")

    data = ApiKeyResponse.model_validate(api_key).model_dump()
    data["full_key"] = full_key
    return ApiKeyCreated(**data)


@router.patch("/{key_id}", response_model=ApiKeyResponse)
async def update_key(
    key_id: int,
    body: ApiKeyUpdate,
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    try:
        updated = await api_key_service.update_api_key(
            db,
            key_id=key_id,
            name=body.name,
            role=body.role,
            is_active=body.is_active,
            allowed_accounts=body.allowed_accounts,
        )
    except KeyError:
        raise HTTPException(400, f"Invalid role: {body.role}")

    if not updated:
        raise HTTPException(404, "API key not found")
    return updated


@router.delete("/{key_id}", status_code=204)
async def revoke_key(
    key_id: int,
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    if not await api_key_service.revoke_api_key(db, key_id):
        raise HTTPException(404, "API key not found")
