from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_accounts_branding)


def _migrate_accounts_branding(conn):
    from sqlalchemy import text, inspect
    insp = inspect(conn)
    if "accounts" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("accounts")}
    new_cols = {
        "color_primario": "VARCHAR(7) DEFAULT ''",
        "color_secundario": "VARCHAR(7) DEFAULT ''",
        "telefono": "VARCHAR(30) DEFAULT ''",
        "email": "VARCHAR(100) DEFAULT ''",
        "web": "VARCHAR(100) DEFAULT ''",
        "logo_b64": "TEXT DEFAULT ''",
    }
    for col, typedef in new_cols.items():
        if col not in existing:
            conn.execute(text(f"ALTER TABLE accounts ADD COLUMN {col} {typedef}"))
