import asyncio
import logging
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.account_service import get_credentials, get_account

logger = logging.getLogger(__name__)

_clients: dict[str, "SessionEntry"] = {}
_locks: dict[str, asyncio.Lock] = {}


class SessionEntry:
    def __init__(self, client, login_time: float, preferred_api: str):
        self.client = client
        self.login_time = login_time
        self.preferred_api = preferred_api

    @property
    def is_expired(self) -> bool:
        if self.preferred_api == "mobile":
            return (time.time() - self.login_time) > 43000
        return (time.time() - self.login_time) > 1400


def _get_lock(nit: str) -> asyncio.Lock:
    if nit not in _locks:
        _locks[nit] = asyncio.Lock()
    return _locks[nit]


async def get_client(db: AsyncSession, nit: str):
    if nit in _clients and not _clients[nit].is_expired:
        return _clients[nit].client

    lock = _get_lock(nit)
    async with lock:
        if nit in _clients and not _clients[nit].is_expired:
            return _clients[nit].client

        creds = await get_credentials(db, nit)
        if not creds:
            raise ValueError(f"Account {nit} not found or inactive")

        login_password, cert_password = creds
        account = await get_account(db, nit)
        preferred_api = account.preferred_api if account else "mobile"

        client = await asyncio.to_thread(
            _create_and_login, nit, login_password, cert_password, preferred_api
        )

        _clients[nit] = SessionEntry(client, time.time(), preferred_api)
        logger.info(f"[session] Login OK for {nit} via {preferred_api}")
        return client


def _create_and_login(nit: str, login_password: str, cert_password: str, preferred_api: str):
    from backend.sat.sat_fallback import SatFallbackClient

    client = SatFallbackClient(
        nit=nit,
        password_login=login_password,
        password_certificacion=cert_password,
        prefer=preferred_api,
    )
    client.login()
    return client


def evict(nit: str):
    _clients.pop(nit, None)


def evict_all():
    _clients.clear()
