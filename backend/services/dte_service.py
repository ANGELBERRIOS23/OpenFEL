import asyncio
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services import session_manager

logger = logging.getLogger(__name__)


def _extract_items(result) -> list:
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for key in ("items", "data", "dtes", "listado"):
            if key in result and isinstance(result[key], list):
                return result[key]
        return [result]
    return []


async def consultar_nit(db: AsyncSession, account_nit: str, nit_consulta: str) -> dict:
    client = await session_manager.get_client(db, account_nit)
    start = time.time()
    nombre = await asyncio.to_thread(client.consultar_nit, nit_consulta)
    duration = int((time.time() - start) * 1000)
    return {"nit": nit_consulta, "nombre": nombre, "duration_ms": duration}


async def emitir_dte(
    db: AsyncSession,
    account_nit: str,
    tipo: str,
    receptor_nit: str,
    receptor_nombre: str,
    items: list[dict],
    complemento: dict | None = None,
    export: bool = False,
) -> dict:
    client = await session_manager.get_client(db, account_nit)
    start = time.time()
    result = await asyncio.to_thread(
        client.emitir,
        tipo_dte=tipo,
        nit_receptor=receptor_nit,
        nombre_receptor=receptor_nombre,
        items=items,
        complemento=complemento,
        export_flag=export,
    )
    duration = int((time.time() - start) * 1000)
    if isinstance(result, dict):
        result["duration_ms"] = duration
        result["source"] = "fallback"
    return result


async def anular_dte(db: AsyncSession, account_nit: str, uuid: str, motivo: str = "Anulación") -> dict:
    client = await session_manager.get_client(db, account_nit)
    start = time.time()
    result = await asyncio.to_thread(client.anular, uuid, motivo=motivo)
    duration = int((time.time() - start) * 1000)
    if isinstance(result, dict):
        result["duration_ms"] = duration
    return result


async def listar_emitidos(db: AsyncSession, account_nit: str) -> dict:
    client = await session_manager.get_client(db, account_nit)
    start = time.time()
    raw = await asyncio.to_thread(client.listar_emitidos)
    duration = int((time.time() - start) * 1000)
    items = _extract_items(raw)
    return {"total": len(items), "items": items, "source": "mobile", "duration_ms": duration}


async def listar_recibidos(db: AsyncSession, account_nit: str) -> dict:
    client = await session_manager.get_client(db, account_nit)
    start = time.time()
    raw = await asyncio.to_thread(client.listar_recibidos)
    duration = int((time.time() - start) * 1000)
    items = _extract_items(raw)
    return {"total": len(items), "items": items, "source": "mobile", "duration_ms": duration}


async def detalle_dte(db: AsyncSession, account_nit: str, uuid: str) -> dict:
    client = await session_manager.get_client(db, account_nit)
    start = time.time()
    data = await asyncio.to_thread(client.detalle_dte, uuid, account_nit)
    duration = int((time.time() - start) * 1000)
    return {"uuid": uuid, "data": data, "source": "mobile", "duration_ms": duration}


async def descargar_pdf(db: AsyncSession, account_nit: str, uuid: str) -> bytes:
    client = await session_manager.get_client(db, account_nit)
    return await asyncio.to_thread(client.descargar_pdf, uuid, account_nit)


async def descargar_xml(db: AsyncSession, account_nit: str, uuid: str) -> bytes:
    client = await session_manager.get_client(db, account_nit)
    if hasattr(client, 'descargar_xml'):
        return await asyncio.to_thread(client.descargar_xml, uuid, account_nit)
    raise ValueError("XML download requires web API (not available on mobile-only accounts)")
