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
    kwargs = {}
    if complemento:
        kwargs["complemento"] = complemento
    if export:
        kwargs["exportacion"] = True
    result = await asyncio.to_thread(
        client.emitir,
        tipo_dte=tipo,
        nit_receptor=receptor_nit,
        nombre_receptor=receptor_nombre,
        items=items,
        **kwargs,
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


async def descargar_pdf(db: AsyncSession, account_nit: str, uuid: str, nit_receptor: str = "CF") -> bytes:
    client = await session_manager.get_client(db, account_nit)
    return await asyncio.to_thread(client.descargar_pdf, uuid, account_nit, nit_receptor)


async def descargar_xml(db: AsyncSession, account_nit: str, uuid: str, nit_receptor: str = "CF") -> str:
    client = await session_manager.get_client(db, account_nit)
    detail = await asyncio.to_thread(client.detalle_dte, uuid, account_nit, nit_receptor)
    if isinstance(detail, dict):
        xml = detail.get("xml") or detail.get("xmlCertificado") or detail.get("documentoXML", "")
        if xml:
            return xml
        return _build_xml_from_detail(detail, account_nit)
    raise ValueError("XML not available for this DTE")


def _build_xml_from_detail(d: dict, nit_emisor: str) -> str:
    items_xml = ""
    for item in d.get("items", []):
        items_xml += f"""      <dte:Item BienOServicio="{item.get('bienOServicio','S')}" NumeroLinea="{item.get('orden',1)}">
        <dte:Cantidad>{item.get('cantidad',1)}</dte:Cantidad>
        <dte:Descripcion>{item.get('descripcion','')}</dte:Descripcion>
        <dte:PrecioUnitario>{item.get('precioUnitario', item.get('precio','0'))}</dte:PrecioUnitario>
        <dte:Total>{item.get('total', item.get('subtotal','0'))}</dte:Total>
      </dte:Item>\n"""
    totales = d.get("totales", {})
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<dte:GTDocumento xmlns:dte="http://www.sat.gob.gt/dte/fel/0.2.0" Version="0.1">
  <dte:SAT ClaseDocumento="dte">
    <dte:DTE ID="DatosCertificados">
      <dte:DatosEmision ID="DatosEmision">
        <dte:DatosGenerales CodigoMoneda="{d.get('codigoMoneda','GTQ')}" FechaHoraEmision="{d.get('fechaEmision','')}" Tipo="{d.get('tipo','FACT')}"/>
        <dte:Emisor AfiliacionIVA="GEN" NITEmisor="{nit_emisor}">
          <dte:DireccionEmisor><dte:Direccion>{d.get('direccionEmisor','')}</dte:Direccion><dte:CodigoPostal>01001</dte:CodigoPostal><dte:Municipio>Guatemala</dte:Municipio><dte:Departamento>Guatemala</dte:Departamento><dte:Pais>GT</dte:Pais></dte:DireccionEmisor>
        </dte:Emisor>
        <dte:Receptor IDReceptor="{d.get('nitReceptor','CF')}" NombreReceptor="{d.get('nombreReceptor','CF')}">
          <dte:DireccionReceptor><dte:Direccion>{d.get('direccionReceptor','ciudad')}</dte:Direccion><dte:CodigoPostal>01001</dte:CodigoPostal><dte:Municipio>Guatemala</dte:Municipio><dte:Departamento>Guatemala</dte:Departamento><dte:Pais>GT</dte:Pais></dte:DireccionReceptor>
        </dte:Receptor>
        <dte:Items>
{items_xml}        </dte:Items>
        <dte:Totales><dte:GranTotal>{totales.get('granTotal', d.get('granTotal','0'))}</dte:GranTotal></dte:Totales>
      </dte:DatosEmision>
      <dte:Certificacion>
        <dte:NITCertificador>{d.get('nitCertificador','')}</dte:NITCertificador>
        <dte:NombreCertificador>{d.get('nombreCertificador','')}</dte:NombreCertificador>
        <dte:NumeroAutorizacion Serie="{d.get('serie','')}" Numero="{d.get('numeroDocumento','')}">{d.get('UUID','')}</dte:NumeroAutorizacion>
        <dte:FechaHoraCertificacion>{d.get('fechaCertificacion','')}</dte:FechaHoraCertificacion>
      </dte:Certificacion>
    </dte:DTE>
  </dte:SAT>
</dte:GTDocumento>"""
