from fastapi import APIRouter, Depends, HTTPException, Query as Q
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
from backend.services import account_service

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
        if result.get("error"):
            raise HTTPException(502, f"SAT error: {result['error']} | mobile: {result.get('mobile_error','')} | web: {result.get('web_error','')}")
        uuid = result.get("uuid", "")
        if not uuid:
            raise HTTPException(502, f"SAT error: emission returned empty UUID — {result}")
        return DteEmitResponse(
            uuid=uuid,
            serie=result.get("serie", ""),
            numero=result.get("numero", ""),
            fecha_certificacion=result.get("fecha_certificacion", ""),
            source=result.get("source", "unknown"),
        )
    except HTTPException:
        raise
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
    nit_receptor: str = "CF",
    key: ApiKey = require_role(Role.VIEWER),
    db: AsyncSession = Depends(get_db),
):
    check_account_access(key, account_nit)
    try:
        pdf_bytes = await dte_service.descargar_pdf(db, account_nit, uuid, nit_receptor)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={uuid}.pdf"},
        )
    except Exception as e:
        raise HTTPException(502, f"SAT error: {e}")


@router.get("/dte/{uuid}/xml")
async def download_xml(
    uuid: str,
    account_nit: str,
    nit_receptor: str = "CF",
    key: ApiKey = require_role(Role.VIEWER),
    db: AsyncSession = Depends(get_db),
):
    check_account_access(key, account_nit)
    try:
        xml_str = await dte_service.descargar_xml(db, account_nit, uuid, nit_receptor)
        content = xml_str.encode("utf-8") if isinstance(xml_str, str) else xml_str
        return Response(
            content=content,
            media_type="application/xml",
            headers={"Content-Disposition": f"attachment; filename={uuid}.xml"},
        )
    except Exception as e:
        raise HTTPException(502, f"SAT error: {e}")


@router.get("/dte/{uuid}/custom-pdf")
async def download_custom_pdf(
    uuid: str,
    account_nit: str,
    nit_receptor: str = "CF",
    key: ApiKey = require_role(Role.VIEWER),
    db: AsyncSession = Depends(get_db),
):
    check_account_access(key, account_nit)
    try:
        from backend.services.pdf_generator import generate_custom_pdf_from_detail
        import asyncio
        account = await account_service.get_account(db, account_nit)
        branding = None
        logo_b64 = None
        if account:
            branding = {
                "color_primario": account.color_primario or "",
                "color_secundario": account.color_secundario or "",
                "telefono": account.telefono or "",
                "email": account.email or "",
                "web": account.web or "",
            }
            logo_b64 = account.logo_b64 or None

        client = await dte_service.session_manager.get_client(db, account_nit)
        detail = await asyncio.to_thread(client.detalle_dte, uuid, account_nit, nit_receptor)

        pdf_bytes = generate_custom_pdf_from_detail(
            detail, nit_emisor=account_nit, branding=branding, logo_b64=logo_b64,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={uuid}_custom.pdf"},
        )
    except Exception as e:
        raise HTTPException(502, f"PDF generation error: {e}")


@router.get("/dte/{uuid}/pos-receipt")
async def download_pos_receipt(
    uuid: str,
    account_nit: str,
    nit_receptor: str = "CF",
    width: int = Q(default=80, description="Receipt width in mm (58 or 80)"),
    key: ApiKey = require_role(Role.VIEWER),
    db: AsyncSession = Depends(get_db),
):
    check_account_access(key, account_nit)
    try:
        from backend.services.pdf_generator import generate_pos_receipt_from_detail
        import asyncio
        client = await dte_service.session_manager.get_client(db, account_nit)
        detail = await asyncio.to_thread(client.detalle_dte, uuid, account_nit, nit_receptor)

        pdf_bytes = generate_pos_receipt_from_detail(
            detail, nit_emisor=account_nit, width_mm=width,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={uuid}_receipt.pdf"},
        )
    except Exception as e:
        raise HTTPException(502, f"POS receipt error: {e}")
