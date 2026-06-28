from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from backend.auth.dependencies import require_role, Role
from backend.database import get_db
from backend.models.api_key import ApiKey
from backend.schemas.account import AccountCreate, AccountUpdate, AccountResponse
from backend.services import account_service

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])


@router.get("")
async def list_accounts(
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    accounts = await account_service.list_accounts(db)
    return [AccountResponse.from_orm_account(a) for a in accounts]


@router.post("", status_code=201)
async def create_account(
    body: AccountCreate,
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    existing = await account_service.get_account(db, body.nit)
    if existing:
        raise HTTPException(409, f"Account {body.nit} already exists")

    account = await account_service.create_account(
        db,
        nit=body.nit,
        login_password=body.login_password,
        cert_password=body.cert_password,
        preferred_api=body.preferred_api,
        affiliation=body.affiliation,
        name=body.name,
    )
    return AccountResponse.from_orm_account(account)


@router.get("/{nit}")
async def get_account(
    nit: str,
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    account = await account_service.get_account(db, nit)
    if not account:
        raise HTTPException(404, "Account not found")
    return AccountResponse.from_orm_account(account)


@router.patch("/{nit}")
async def update_account(
    nit: str,
    body: AccountUpdate,
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    updated = await account_service.update_account(
        db,
        nit=nit,
        login_password=body.login_password,
        cert_password=body.cert_password,
        preferred_api=body.preferred_api,
        affiliation=body.affiliation,
        name=body.name,
        status=body.status,
        branding=body.branding.model_dump() if body.branding else None,
    )
    if not updated:
        raise HTTPException(404, "Account not found")
    return AccountResponse.from_orm_account(updated)


@router.delete("/{nit}", status_code=204)
async def delete_account(
    nit: str,
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    if not await account_service.delete_account(db, nit):
        raise HTTPException(404, "Account not found")


class PreviewBranding(BaseModel):
    color_primario: str = ""
    color_secundario: str = ""
    telefono: str = ""
    email: str = ""
    web: str = ""
    logo_b64: str = ""


class PreviewRequest(BaseModel):
    branding: Optional[PreviewBranding] = None


@router.post("/{nit}/preview-pdf")
async def preview_pdf(
    nit: str,
    body: PreviewRequest = PreviewRequest(),
    _key: ApiKey = require_role(Role.ADMIN),
    db: AsyncSession = Depends(get_db),
):
    account = await account_service.get_account(db, nit)
    if not account:
        raise HTTPException(404, "Account not found")

    from backend.services.pdf_generator import generate_custom_pdf

    if body.branding:
        branding = body.branding.model_dump()
    else:
        branding = {
            "color_primario": account.color_primario or "",
            "color_secundario": account.color_secundario or "",
            "telefono": account.telefono or "",
            "email": account.email or "",
            "web": account.web or "",
        }

    logo_b64 = (body.branding.logo_b64 if body.branding and body.branding.logo_b64 else account.logo_b64) or None

    afiliacion = account.affiliation or "GEN"
    nombre = account.name or "EMPRESA DE EJEMPLO S.A."
    tipo = "FPEQ" if afiliacion == "PEQ" else "FACT"

    sample_data = {
        'tipo': tipo,
        'fecha_emision': '2026-01-15T10:30:00',
        'moneda': 'GTQ',
        'emisor': {
            'nit': nit,
            'nombre': nombre,
            'nombre_comercial': nombre,
            'afiliacion': afiliacion,
            'direccion': '5 Avenida 10-20 Zona 1',
            'municipio': 'Guatemala',
            'departamento': 'Guatemala',
        },
        'receptor': {
            'nit': 'CF',
            'nombre': 'CONSUMIDOR FINAL',
            'correo': 'cliente@ejemplo.com',
            'telefono': '5555-0000',
            'direccion': 'Ciudad de Guatemala',
        },
        'frases': ['Sujeto a pagos trimestrales ISR'],
        'items': [
            {'linea': '1', 'bs': 'S', 'cantidad': 2.0,
             'descripcion': 'Servicio de consultoria profesional',
             'precio_unit': 500.0, 'descuento': 0.0, 'total': 1000.0,
             'imp_label': 'IVA 12 %' if afiliacion == 'GEN' else 'Exento',
             'imp_monto': 107.14 if afiliacion == 'GEN' else 0.0,
             'cod_gravable': 1 if afiliacion == 'GEN' else 2},
            {'linea': '2', 'bs': 'B', 'cantidad': 1.0,
             'descripcion': 'Licencia de software anual',
             'precio_unit': 350.0, 'descuento': 50.0, 'total': 300.0,
             'imp_label': 'IVA 12 %' if afiliacion == 'GEN' else 'Exento',
             'imp_monto': 32.14 if afiliacion == 'GEN' else 0.0,
             'cod_gravable': 1 if afiliacion == 'GEN' else 2},
        ],
        'gran_total': 1300.0,
        'certificacion': {
            'nit_cert': '12521337',
            'nombre_cert': 'INFILE S.A.',
            'uuid': 'A1B2C3D4-E5F6-7890-ABCD-EF1234567890',
            'serie': 'ABCD1234',
            'numero': '123456789',
            'fecha': '2026-01-15T10:30:05',
        },
    }

    pdf_bytes = generate_custom_pdf(sample_data, branding=branding, logo_b64=logo_b64)
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=preview_{nit}.pdf"},
    )
