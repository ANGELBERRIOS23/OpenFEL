import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit_log import AuditLog


async def log_action(
    db: AsyncSession,
    action: str,
    api_key_prefix: str = "",
    account_nit: str = "",
    request_summary: dict | None = None,
    response_status: int = 200,
    duration_ms: int = 0,
    source: str = "",
    error_detail: str = "",
):
    entry = AuditLog(
        timestamp=datetime.utcnow(),
        api_key_prefix=api_key_prefix,
        account_nit=account_nit,
        action=action,
        request_summary=json.dumps(request_summary or {}),
        response_status=response_status,
        duration_ms=duration_ms,
        source=source,
        error_detail=error_detail,
    )
    db.add(entry)
    await db.commit()


async def query_logs(
    db: AsyncSession,
    action: Optional[str] = None,
    account_nit: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(desc(AuditLog.timestamp))

    if action:
        stmt = stmt.where(AuditLog.action == action)
    if account_nit:
        stmt = stmt.where(AuditLog.account_nit == account_nit)

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
