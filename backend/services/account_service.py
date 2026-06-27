from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.crypto import encrypt_credential, decrypt_credential
from backend.models.account import Account


async def create_account(
    db: AsyncSession,
    nit: str,
    login_password: str,
    cert_password: str,
    preferred_api: str = "mobile",
    name: str = "",
    affiliation: str = "GEN",
) -> Account:
    account = Account(
        nit=nit,
        name=name,
        affiliation=affiliation,
        login_password=encrypt_credential(login_password),
        cert_password=encrypt_credential(cert_password),
        preferred_api=preferred_api,
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def list_accounts(db: AsyncSession) -> list[Account]:
    result = await db.execute(
        select(Account).order_by(Account.created_at.desc())
    )
    return list(result.scalars().all())


async def get_account(db: AsyncSession, nit: str) -> Account | None:
    result = await db.execute(
        select(Account).where(Account.nit == nit)
    )
    return result.scalar_one_or_none()


async def get_credentials(db: AsyncSession, nit: str) -> tuple[str, str] | None:
    account = await get_account(db, nit)
    if not account or account.status != "active":
        return None
    return (
        decrypt_credential(account.login_password),
        decrypt_credential(account.cert_password),
    )


async def update_account(
    db: AsyncSession,
    nit: str,
    login_password: Optional[str] = None,
    cert_password: Optional[str] = None,
    preferred_api: Optional[str] = None,
    status: Optional[str] = None,
) -> Account | None:
    account = await get_account(db, nit)
    if not account:
        return None

    if login_password is not None:
        account.login_password = encrypt_credential(login_password)
    if cert_password is not None:
        account.cert_password = encrypt_credential(cert_password)
    if preferred_api is not None:
        account.preferred_api = preferred_api
    if status is not None:
        account.status = status

    account.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(account)
    return account


async def deactivate_account(db: AsyncSession, nit: str) -> bool:
    account = await get_account(db, nit)
    if not account:
        return False
    account.status = "inactive"
    account.updated_at = datetime.utcnow()
    await db.commit()
    return True
