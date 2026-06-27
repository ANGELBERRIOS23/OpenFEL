import json
from datetime import datetime
from enum import IntEnum

from fastapi import Header, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.auth.crypto import hash_api_key, get_master_key
from backend.models.api_key import ApiKey


class Role(IntEnum):
    VIEWER = 1
    OPERATOR = 2
    ADMIN = 3


async def get_current_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    # Master key bypass
    master = get_master_key()
    if master and x_api_key == master:
        master = ApiKey(
            id=0, name="Master Key", key_hash="", key_prefix="master",
            role="ADMIN", is_active=True, allowed_accounts="",
            usage_count=0,
        )
        return master

    key_hash = hash_api_key(x_api_key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash)
    )
    api_key = result.scalar_one_or_none()

    if not api_key or not api_key.is_active:
        raise HTTPException(401, "Invalid or inactive API key")

    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        raise HTTPException(401, "API key expired")

    api_key.usage_count += 1
    api_key.last_used_at = datetime.utcnow()
    await db.commit()
    return api_key


def require_role(min_role: Role):
    async def _check(key: ApiKey = Depends(get_current_key)):
        if Role[key.role] < min_role:
            raise HTTPException(403, f"Requires {min_role.name} role, you have {key.role}")
        return key
    return Depends(_check)


def check_account_access(key: ApiKey, nit: str):
    if not key.allowed_accounts:
        return
    allowed = json.loads(key.allowed_accounts)
    if allowed and nit not in allowed:
        raise HTTPException(403, f"API key not authorized for account {nit}")
