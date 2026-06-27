from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_role, Role
from backend.database import get_db
from backend.models.api_key import ApiKey
from backend.services import audit_service

router = APIRouter(prefix="/api/logs", tags=["Audit Logs"])


@router.get("")
async def get_logs(
    action: Optional[str] = Query(None),
    account_nit: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    logs = await audit_service.query_logs(
        db, action=action, account_nit=account_nit, limit=limit, offset=offset,
    )
    return [
        {
            "id": log.id,
            "timestamp": log.timestamp.isoformat() if log.timestamp else "",
            "api_key_prefix": log.api_key_prefix,
            "account_nit": log.account_nit,
            "action": log.action,
            "request_summary": log.request_summary,
            "response_status": log.response_status,
            "duration_ms": log.duration_ms,
            "source": log.source,
            "error_detail": log.error_detail,
        }
        for log in logs
    ]
