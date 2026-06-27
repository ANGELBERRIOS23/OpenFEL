from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    api_key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    account_nit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    request_summary: Mapped[Optional[str]] = mapped_column(nullable=True)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(nullable=True)
