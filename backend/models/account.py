from datetime import datetime

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    nit: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    affiliation: Mapped[str] = mapped_column(String(3), default="GEN")
    login_password: Mapped[str] = mapped_column(nullable=False)
    cert_password: Mapped[str] = mapped_column(nullable=False)
    preferred_api: Mapped[str] = mapped_column(String(10), default="mobile")
    status: Mapped[str] = mapped_column(String(10), default="active")
    color_primario: Mapped[str] = mapped_column(String(7), default="")
    color_secundario: Mapped[str] = mapped_column(String(7), default="")
    telefono: Mapped[str] = mapped_column(String(30), default="")
    email: Mapped[str] = mapped_column(String(100), default="")
    web: Mapped[str] = mapped_column(String(100), default="")
    logo_b64: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
