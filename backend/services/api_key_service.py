import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.crypto import generate_api_key
from backend.auth.dependencies import Role
from backend.models.api_key import ApiKey


async def create_api_key(
    db: AsyncSession,
    name: str,
    role: str = "VIEWER",
    allowed_accounts: list[str] | None = None,
    expires_at: Optional[datetime] = None,
    created_by: str = "",
) -> tuple[ApiKey, str]:
    Role[role]

    full_key, key_hash, key_prefix = generate_api_key()

    api_key = ApiKey(
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        role=role,
        is_active=True,
        allowed_accounts=json.dumps(allowed_accounts or []),
        expires_at=expires_at,
        usage_count=0,
        created_at=datetime.utcnow(),
        created_by=created_by,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key, full_key


async def list_api_keys(db: AsyncSession) -> list[ApiKey]:
    result = await db.execute(
        select(ApiKey).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def get_api_key_by_id(db: AsyncSession, key_id: int) -> ApiKey | None:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id)
    )
    return result.scalar_one_or_none()


async def update_api_key(
    db: AsyncSession,
    key_id: int,
    name: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    allowed_accounts: Optional[list[str]] = None,
) -> ApiKey | None:
    api_key = await get_api_key_by_id(db, key_id)
    if not api_key:
        return None

    if name is not None:
        api_key.name = name
    if role is not None:
        Role[role]
        api_key.role = role
    if is_active is not None:
        api_key.is_active = is_active
    if allowed_accounts is not None:
        api_key.allowed_accounts = json.dumps(allowed_accounts)

    await db.commit()
    await db.refresh(api_key)
    return api_key


async def revoke_api_key(db: AsyncSession, key_id: int) -> bool:
    api_key = await get_api_key_by_id(db, key_id)
    if not api_key:
        return False
    api_key.is_active = False
    await db.commit()
    return True
