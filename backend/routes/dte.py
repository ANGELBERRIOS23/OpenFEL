from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_role, check_account_access, Role
from backend.database import get_db
from backend.models.api_key import ApiKey
from backend.schemas.dte import (
    NitLookup, NitResponse, DteEmit, DteAnnul,
    DteEmitResponse, DteAnnulResponse, DteListResponse, DteDetailResponse,
)
from backend.services import dte_service

router = APIRouter(prefix="/api", tags=["DTE"])


@router.post("/nit/lookup", response_model=NitResponse)
async def lookup_nit(
    body: NitLookup,
    key: ApiKey = require_role(Role.VIEWER),
    db: AsyncSession = Depends(get_db),
):
    check_account_access(key, body.account_nit)
    try:
        result = await dte_service.consultar_nit(db, body.account_nit, body.nit)
        return NitResponse(nit=body.nit, nombre=result["nombre"], estado="ACTIVO")
    except Exception as e:
        raise HTTPException(502, f"SAT error: {e}")


@router.post("/dte/emit", response_model=DteEmitResponse)
async def emit_dte(
    body: DteEmit,
    key: ApiKey = require_role(Role.OPERATOR),
    db: AsyncSession = Depends(get_db),
):
    check_account_access(key, body.account_nit)
    try:
        result = await dte_service.emitir_dte(
            db,
            account_nit=body.account_nit,
            tipo=body.tipo,
            receptor_nit=body.receptor_nit,
            receptor_nombre=body.receptor_nombre,
            items=body.items,
            complemento=body.complemento,
            export=body.export,
        )
        return DteEmitResponse(
            uuid=result.get("uuid", ""),
            serie=result.get("serie", ""),
            numero=result.get("numero", ""),
            fecha_certificacion=result.get("fecha_certificacion", ""),
            source=result.get("source", "unknown"),
        )
    except Exception as e:
        raise HTTPException(502, f"SAT error: {e}")


@router.post("/dte/annul", response_model=DteAnnulResponse)
async def annul_dte(
    body: DteAnnul,
    key: ApiKey = require_role(Role.OPERATOR),
    db: AsyncSession = Depends(get_db),
):
    check_account_access(key, body.account_nit)
    try:
        result = await dte_service.anular_dte(db, body.account_nit, body.uuid, body.motivo)
        return DteAnnulResponse(
            uuid=body.uuid,
            estado=result.get("resultado", ""),
            source=result.get("source", "unknown"),
        )
    except Exception as e:
        raise HTTPException(502, f"SAT error: {e}")


@router.get("/dte/emitted", response_model=DteListResponse)
async def list_emitted(
    account_nit: str,
    key: ApiKey = require_role(Role.VIEWER),
    db: AsyncSession = Depends(get_db),
):
    check_account_access(key, account_nit)
    try:
        return await dte_service.listar_emitidos(db, account_nit)
    except Exception as e:
        raise HTTPException(502, f"SAT error: {e}")


@router.get("/dte/received", response_model=DteListResponse)
async def list_received(
    account_nit: str,
    key: ApiKey = require_role(Role.VIEWER),
    db: AsyncSession = Depends(get_db),
):
    check_account_access(key, account_nit)
    try:
        return await dte_service.listar_recibidos(db, account_nit)
    except Exception as e:
        raise HTTPException(502, f"SAT error: {e}")


@router.get("/dte/{uuid}/detail", response_model=DteDetailResponse)
async def detail_dte(
    uuid: str,
    account_nit: str,
    key: ApiKey = require_role(Role.VIEWER),
    db: AsyncSession = Depends(get_db),
):
    check_account_access(key, account_nit)
    try:
        return await dte_service.detalle_dte(db, account_nit, uuid)
    except Exception as e:
        raise HTTPException(502, f"SAT error: {e}")


@router.get("/dte/{uuid}/pdf")
async def download_pdf(
    uuid: str,
    account_nit: str,
    key: ApiKey = require_role(Role.VIEWER),
    db: AsyncSession = Depends(get_db),
):
    check_account_access(key, account_nit)
    try:
        pdf_bytes = await dte_service.descargar_pdf(db, account_nit, uuid)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={uuid}.pdf"},
        )
    except Exception as e:
        raise HTTPException(502, f"SAT error: {e}")
