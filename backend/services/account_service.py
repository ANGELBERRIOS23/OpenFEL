import base64
import io
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.crypto import encrypt_credential, decrypt_credential
from backend.models.account import Account

logger = logging.getLogger(__name__)

MAX_LOGO_PX = 400


def _compress_logo(b64_data: str) -> str:
    try:
        from PIL import Image
        raw = base64.b64decode(b64_data)
        img = Image.open(io.BytesIO(raw))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")
        img.thumbnail((MAX_LOGO_PX, MAX_LOGO_PX), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        compressed = base64.b64encode(buf.getvalue()).decode()
        original_kb = len(b64_data) * 3 // 4 // 1024
        compressed_kb = len(compressed) * 3 // 4 // 1024
        logger.info(f"Logo compressed: {original_kb}KB -> {compressed_kb}KB ({img.size[0]}x{img.size[1]})")
        return compressed
    except Exception as e:
        logger.warning(f"Logo compression failed, storing original: {e}")
        return b64_data


async def create_account(
    db: AsyncSession,
    nit: str,
    login_password: str,
    cert_password: str,
    preferred_api: str = "mixed",
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
    affiliation: Optional[str] = None,
    name: Optional[str] = None,
    status: Optional[str] = None,
    branding: Optional[dict] = None,
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
    if affiliation is not None:
        account.affiliation = affiliation
    if name is not None:
        account.name = name
    if status is not None:
        account.status = status
    if branding is not None:
        for field in ("color_primario", "color_secundario", "telefono", "email", "web", "logo_b64"):
            if field in branding:
                value = branding[field] or ""
                if field == "logo_b64" and value:
                    value = _compress_logo(value)
                setattr(account, field, value)

    account.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(account)

    from backend.services.session_manager import evict
    evict(nit)

    return account


async def delete_account(db: AsyncSession, nit: str) -> bool:
    account = await get_account(db, nit)
    if not account:
        return False
    await db.execute(sql_delete(Account).where(Account.nit == nit))
    await db.commit()

    from backend.services.session_manager import evict
    evict(nit)

    return True


async def deactivate_account(db: AsyncSession, nit: str) -> bool:
    account = await get_account(db, nit)
    if not account:
        return False
    account.status = "inactive"
    account.updated_at = datetime.utcnow()
    await db.commit()

    from backend.services.session_manager import evict
    evict(nit)

    return True
