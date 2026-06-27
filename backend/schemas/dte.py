from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class NitLookup(BaseModel):
    nit: str
    account_nit: str


class NitResponse(BaseModel):
    nit: str
    nombre: str
    estado: str


class DteEmit(BaseModel):
    account_nit: str
    tipo: str = "FACT"
    receptor_nit: str = "CF"
    receptor_nombre: str = "Consumidor Final"
    items: list[dict[str, Any]]
    complemento: Optional[dict[str, Any]] = None
    export: bool = False


class DteAnnul(BaseModel):
    account_nit: str
    uuid: str
    motivo: str = "Anulación"
    nit_receptor: str = "CF"


class DteQuery(BaseModel):
    account_nit: str
    fecha_inicio: str
    fecha_fin: str
    tipo: Optional[str] = None


class DteDownload(BaseModel):
    account_nit: str
    uuids: list[str]
    formato: str = "pdf"


class DteListResponse(BaseModel):
    total: int
    items: list[dict[str, Any]]
    source: str


class DteDetailResponse(BaseModel):
    uuid: str
    data: dict[str, Any]
    source: str


class DteEmitResponse(BaseModel):
    uuid: str
    serie: str
    numero: str
    fecha_certificacion: str
    source: str


class DteAnnulResponse(BaseModel):
    uuid: str
    estado: str
    source: str
