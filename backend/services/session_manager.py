import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import DATA_DIR
from backend.services.account_service import get_credentials, get_account

logger = logging.getLogger(__name__)

_clients: dict[str, "SessionEntry"] = {}
_locks: dict[str, asyncio.Lock] = {}
_SESSION_FILE = DATA_DIR / "sessions.json"


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


def _save_sessions():
    data = {}
    for nit, entry in _clients.items():
        try:
            exported = entry.client.export_session()
            if exported:
                data[nit] = {
                    "session": exported,
                    "login_time": entry.login_time,
                    "preferred_api": entry.preferred_api,
                }
        except Exception:
            pass
    try:
        _SESSION_FILE.write_text(json.dumps(data))
    except Exception as e:
        logger.warning(f"Failed to save sessions: {e}")


def _load_saved_session(nit: str) -> dict | None:
    try:
        if not _SESSION_FILE.exists():
            return None
        data = json.loads(_SESSION_FILE.read_text())
        entry = data.get(nit)
        if not entry:
            return None
        return entry
    except Exception:
        return None


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

        saved = _load_saved_session(nit)
        if saved:
            client = await asyncio.to_thread(
                _try_restore, nit, login_password, cert_password, preferred_api, saved
            )
            if client:
                _clients[nit] = SessionEntry(client, saved["login_time"], preferred_api)
                logger.info(f"[session] Restored session for {nit}")
                return client

        client = await asyncio.to_thread(
            _create_and_login, nit, login_password, cert_password, preferred_api
        )

        _clients[nit] = SessionEntry(client, time.time(), preferred_api)
        _save_sessions()
        logger.info(f"[session] Login OK for {nit} via {preferred_api}")
        return client


def _try_restore(
    nit: str, login_password: str, cert_password: str,
    preferred_api: str, saved: dict,
):
    from backend.sat.sat_fallback import SatFallbackClient

    client = SatFallbackClient(
        nit=nit,
        password_login=login_password,
        password_certificacion=cert_password,
        prefer=preferred_api,
    )
    session_data = saved.get("session")
    if client.import_session(session_data):
        return client
    return None


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
    _save_sessions()


def evict_all():
    _clients.clear()
    _save_sessions()
