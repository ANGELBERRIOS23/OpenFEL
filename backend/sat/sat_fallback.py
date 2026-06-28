"""
SAT FEL Fallback Client
========================

Integrates both the Web API (sat_api.py) and Mobile API (sat_movil_api.py)
with automatic failover. If one API fails, the other is tried transparently.

Priority order: Mobile API first (faster, simpler), Web API as fallback.
This can be inverted via the `prefer` parameter.

Usage:
    from sat_fallback import SatFallbackClient

    client = SatFallbackClient(
        nit="120405237",
        password_login="...",
        password_certificacion="...",
    )
    client.login()
    result = client.emitir(items=[...], nit_receptor="CF")
    client.anular(uuid="...", nit_receptor="CF")
"""

import logging
import time
from typing import Optional

from .sat_movil_api import SatMovilAPI, SatMovilAPIError

logger = logging.getLogger(__name__)


def _build_item_taxes(regime: str, amount: float, cantidad: float = 1) -> list:
    """
    Build mobile-API-format impuestos list for a given tax regime.

    Supports ALL SAT catalog taxes (catalogoUnidadesGravables-0.1.4):
    - MontoGravable-based: IVA, TURISMO HOSPEDAJE, TIMBRE DE PRENSA, BOMBEROS
    - CantidadUnidadesGravables-based: PETROLEO, TURISMO PASAJES, BEBIDAS, TABACO, CEMENTO, TARIFA PORTUARIA

    For quantity-based taxes, pass sub_code in regime name:
      "PETROLEO_4" = Diésel (Q1.30/gal), "PETROLEO_1" = Gasolina superior (Q4.70/gal)
    """
    regime = regime.upper()
    if regime in ("EXENTO", "NO_AFECTO", "EXPORT"):
        return [{"nombreCorto": "IVA", "codigoUnidadGravable": "2",
                 "montoGravable": round(amount, 2), "montoImpuesto": 0.0}]
    if regime == "PEQ":
        return []
    if regime == "TURISMO_HOSPEDAJE":
        base = round(amount / 1.12, 2)
        return [
            {"nombreCorto": "IVA", "codigoUnidadGravable": "1",
             "montoGravable": base, "montoImpuesto": round(amount - base, 2)},
            {"nombreCorto": "TURISMO HOSPEDAJE", "codigoUnidadGravable": "1",
             "montoGravable": base, "montoImpuesto": round(base * 0.10, 2)},
        ]

    # Special taxes are ADDITIONAL to IVA — items get both IVA 12% + the special tax
    base_iva = round(amount / 1.12, 2)
    iva_entry = {"nombreCorto": "IVA", "codigoUnidadGravable": "1",
                 "montoGravable": base_iva, "montoImpuesto": round(amount - base_iva, 2)}

    # Quantity-based taxes (factor × cantidad): REGIME or REGIME_subcode
    _QTY_TAXES = {
        "PETROLEO":              ("PETROLEO", "4", 1.3),
        "PETROLEO_1":            ("PETROLEO", "1", 4.7),
        "PETROLEO_2":            ("PETROLEO", "2", 4.6),
        "PETROLEO_3":            ("PETROLEO", "3", 4.7),
        "PETROLEO_4":            ("PETROLEO", "4", 1.3),
        "PETROLEO_5":            ("PETROLEO", "5", 1.3),
        "PETROLEO_6":            ("PETROLEO", "6", 0.5),
        "PETROLEO_7":            ("PETROLEO", "7", 0.5),
        "PETROLEO_9":            ("PETROLEO", "9", 0.5),
        "PETROLEO_10":           ("PETROLEO", "10", 0.5),
        "TURISMO_PASAJES":       ("TURISMO PASAJES", "1", 30.0),
        "TURISMO_PASAJES_1":     ("TURISMO PASAJES", "1", 30.0),
        "TURISMO_PASAJES_2":     ("TURISMO PASAJES", "2", 10.0),
        "TURISMO_PASAJES_3":     ("TURISMO PASAJES", "3", 0.0),
        "BEBIDAS_ALCOHOLICAS":   ("BEBIDAS ALCOHOLICAS", "1", 0.06),
        "BEBIDAS_ALCOHOLICAS_1": ("BEBIDAS ALCOHOLICAS", "1", 0.06),
        "BEBIDAS_ALCOHOLICAS_2": ("BEBIDAS ALCOHOLICAS", "2", 0.075),
        "BEBIDAS_ALCOHOLICAS_6": ("BEBIDAS ALCOHOLICAS", "6", 0.085),
        "TABACO":                ("TABACO", "1", 1.0),
        "TABACO_1":              ("TABACO", "1", 1.0),
        "TABACO_2":              ("TABACO", "2", 0.75),
        "CEMENTO":               ("CEMENTO", "1", 1.5),
        "BEBIDAS_NO_ALCOHOLICAS":   ("BEBIDAS NO ALCOHOLICAS", "1", 0.18),
        "BEBIDAS_NO_ALCOHOLICAS_1": ("BEBIDAS NO ALCOHOLICAS", "1", 0.18),
        "BEBIDAS_NO_ALCOHOLICAS_2": ("BEBIDAS NO ALCOHOLICAS", "2", 0.12),
        "BEBIDAS_NO_ALCOHOLICAS_3": ("BEBIDAS NO ALCOHOLICAS", "3", 0.10),
        "BEBIDAS_NO_ALCOHOLICAS_5": ("BEBIDAS NO ALCOHOLICAS", "5", 0.08),
        "TARIFA_PORTUARIA":      ("TARIFA PORTUARIA", "1", 0.05),
    }
    if regime in _QTY_TAXES:
        nombre, code, factor = _QTY_TAXES[regime]
        special = {"nombreCorto": nombre, "codigoUnidadGravable": code,
                   "cantidadUnidadesGravables": cantidad,
                   "montoImpuesto": round(cantidad * factor, 2)}
        return [iva_entry, special]

    # Amount-based special taxes (factor × monto)
    _AMT_TAXES = {
        "TIMBRE_PRENSA": ("TIMBRE DE PRENSA", "1", 0.005),
        "BOMBEROS":      ("BOMBEROS", "1", 0.02),
    }
    if regime in _AMT_TAXES:
        nombre, code, factor = _AMT_TAXES[regime]
        special = {"nombreCorto": nombre, "codigoUnidadGravable": code,
                   "montoGravable": round(amount, 2),
                   "montoImpuesto": round(amount * factor, 2)}
        return [iva_entry, special]

    # GENERAL — return None so mobile API auto-calculates IVA 12%
    return None


_REGIME_EXTRA_FRASE = {
    "TURISMO_HOSPEDAJE": ("4", "6"),
    "EXPORT": ("4", "1"),
    "TURISMO_PASAJES": ("4", "14"),
}


class SatFallbackClient:
    """
    Unified SAT FEL client with automatic failover between Mobile and Web APIs.

    The Mobile API (svc.c.sat.gob.gt/api/v3) is preferred by default:
      - ~40% faster (5.4s vs 8-10s full cycle)
      - JSON-only (no XML/AES/signing complexity)
      - 12h token TTL (vs 25min web sessions)

    Falls back to Web API when:
      - Mobile API is down or returns unexpected errors
      - An operation requires web-only features (XML download, custom PDF)
    """

    def __init__(
        self,
        nit: str,
        password_login: str,
        password_certificacion: str,
        afiliacion: str = "GEN",
        prefer: str = "mobile",
    ):
        self.nit = nit
        self.password_login = password_login
        self.password_certificacion = password_certificacion
        self.afiliacion = afiliacion
        self.prefer = prefer

        # Mobile API client
        self._movil = SatMovilAPI()
        self._movil_available = True
        self._movil_last_error: Optional[str] = None

        # Web API client (lazy import to avoid circular deps)
        self._web = None
        self._web_available = True
        self._web_last_error: Optional[str] = None

        # Stats
        self._stats = {
            "mobile_calls": 0,
            "mobile_failures": 0,
            "web_calls": 0,
            "web_failures": 0,
            "fallbacks_triggered": 0,
        }

    def login(self) -> dict:
        """Login to both APIs (mobile always, web on-demand)."""
        result = None

        # Always login mobile (fast, 12h token)
        try:
            result = self._movil.login(nit=self.nit, clave=self.password_login)
            self._movil_available = True
            logger.info(f"[fallback] Mobile API login OK: {result.get('nombre', self.nit)}")
        except SatMovilAPIError as e:
            self._movil_available = False
            self._movil_last_error = str(e)
            logger.warning(f"[fallback] Mobile API login failed: {e}")

        if not self._movil_available:
            result = self._login_web()

        return result or {}

    def _login_web(self) -> dict:
        """Lazy-init and login the web API client."""
        try:
            from .sat_api import SatAPI
            self._web = SatAPI()
            self._web.login(self.nit, self.password_login)
            self._web.iniciar_sesion_fel(self.password_certificacion)
            self._web_available = True
            logger.info("[fallback] Web API login OK")
            return {"source": "web", "nit": self.nit}
        except Exception as e:
            self._web_available = False
            self._web_last_error = str(e)
            logger.warning(f"[fallback] Web API login failed: {e}")
            return {}

    def export_session(self) -> dict | None:
        mob = self._movil.export_session() if self._movil_available else None
        if not mob:
            return None
        return {"mobile": mob, "prefer": self.prefer}

    def import_session(self, data: dict) -> bool:
        if not data or "mobile" not in data:
            return False
        ok = self._movil.import_session(data["mobile"])
        if ok:
            self._movil_available = True
            self.afiliacion = data["mobile"].get("afiliacion_iva", self.afiliacion)
        return ok

    def _process_regimes(self, items: list, tipo_dte: str) -> tuple:
        """
        Pre-process items with `regimen` field into mobile API format.

        Returns (processed_items, frases_or_none):
          - processed_items: items with pre-built `impuestos` lists
          - frases: list of frase dicts if any non-default regime, else None
        """
        has_custom_regime = any(item.get("regimen") for item in items)
        if not has_custom_regime:
            return items, None

        processed = []
        extra_frases = set()

        for item in items:
            regime = (item.get("regimen") or "GENERAL").upper()
            cantidad = float(item.get("cantidad", 1))
            precio = float(item.get("precio_unitario", 0))
            descuento = float(item.get("descuento", 0))
            amount = cantidad * precio - descuento

            taxes = _build_item_taxes(regime, amount, cantidad)
            new_item = {k: v for k, v in item.items() if k != "regimen"}
            if taxes is not None:
                new_item["impuestos"] = taxes
            processed.append(new_item)

            if regime in _REGIME_EXTRA_FRASE:
                extra_frases.add(_REGIME_EXTRA_FRASE[regime])

        frases = None
        if extra_frases:
            if self.afiliacion == "PEQ":
                frases = [{"tipo": "3", "escenario": "1"}]
            elif tipo_dte == "NABN":
                frases = []
            elif tipo_dte in ("NCRE", "NDEB"):
                frases = [{"tipo": "1", "escenario": "1"}]
            else:
                frases = [{"tipo": "1", "escenario": "1"}]
            for t, e in extra_frases:
                frases.append({"tipo": t, "escenario": e})

        return processed, frases

    def emitir(
        self,
        items: list,
        tipo_dte: str = None,
        nit_receptor: str = "CF",
        nombre_receptor: str = "CONSUMIDOR FINAL",
        direccion_receptor: str = "ciudad",
        moneda: str = "GTQ",
        **kwargs,
    ) -> dict:
        """
        Emit a DTE with automatic failover.

        Returns:
            dict with at minimum: {"uuid": "...", "source": "mobile"|"web"}
        """
        if tipo_dte is None:
            tipo_dte = "FPEQ" if self.afiliacion == "PEQ" else "FACT"

        # Translate per-item regimen into impuestos + frases for mobile API
        items, regime_frases = self._process_regimes(items, tipo_dte)
        if regime_frases is not None:
            kwargs["frases"] = regime_frases

        # Map generic complemento to specific mobile API parameters
        complemento = kwargs.pop("complemento", None)
        if complemento and isinstance(complemento, dict):
            comp_type = complemento.get("tipo", "")
            comp_data = complemento.get("data", complemento)
            if comp_type in ("NCRE", "NDEB") or "numeroAutorizacionDocumentoOrigen" in str(complemento):
                kwargs.setdefault("complemento_notas", comp_data)
                kwargs.setdefault("es_nota", True)
            elif comp_type == "EXPORTACION" or "incoterm" in str(complemento):
                kwargs.setdefault("complemento_exportacion", comp_data)
            elif comp_type == "FESP" or "retencionISR" in str(complemento):
                kwargs.setdefault("complemento_factura_especial", comp_data)
                kwargs.setdefault("es_factura_especial", True)
            elif comp_type == "CAMBIARIA" or "abonos" in str(complemento):
                kwargs.setdefault("complemento_cambiaria", comp_data.get("abonos", []) if isinstance(comp_data, dict) else comp_data)
                kwargs.setdefault("cambiaria", True)

        # Try preferred API first (mixed = mobile first with web fallback)
        if self.prefer in ("mobile", "mixed") and self._movil_available:
            result = self._try_emitir_movil(
                tipo_dte, nit_receptor, nombre_receptor, direccion_receptor, items, moneda, **kwargs
            )
            if result:
                return result
            # Fallback to web
            self._stats["fallbacks_triggered"] += 1
            logger.warning("[fallback] Mobile emission failed, trying web API...")
            web_result = self._try_emitir_web(
                tipo_dte, nit_receptor, nombre_receptor, direccion_receptor, items, moneda, **kwargs
            )
            if web_result:
                return web_result
            return self._build_both_failed_error("emitir")
        else:
            # Web first, mobile fallback
            result = self._try_emitir_web(
                tipo_dte, nit_receptor, nombre_receptor, direccion_receptor, items, moneda, **kwargs
            )
            if result:
                return result
            self._stats["fallbacks_triggered"] += 1
            logger.warning("[fallback] Web emission failed, trying mobile API...")
            movil_result = self._try_emitir_movil(
                tipo_dte, nit_receptor, nombre_receptor, direccion_receptor, items, moneda, **kwargs
            )
            if movil_result:
                return movil_result
            return self._build_both_failed_error("emitir")

    def _build_both_failed_error(self, operation: str) -> dict:
        """Build a descriptive error dict when both APIs fail."""
        mobile_err = self._movil_last_error or ""
        web_err = self._web_last_error or ""
        mobile_down = not self._movil_available
        web_down = not self._web_available

        if mobile_down and web_down:
            status = "API móvil y web caídas"
        elif mobile_down:
            status = f"API móvil caída — web rechazó la solicitud: {web_err[:100]}"
        elif web_down:
            status = f"API web caída — móvil rechazó la solicitud: {mobile_err[:100]}"
        else:
            status = f"Ambas APIs rechazaron la solicitud"

        return {
            "error": status,
            "mobile_status": "caída" if mobile_down else ("error: " + mobile_err[:150] if mobile_err else "sin respuesta"),
            "web_status": "caída" if web_down else ("error: " + web_err[:150] if web_err else "sin respuesta"),
            "operation": operation,
        }

    def _try_emitir_movil(self, tipo_dte, nit_receptor, nombre_receptor, direccion_receptor, items, moneda, **kwargs):
        try:
            self._stats["mobile_calls"] += 1
            if not self._movil.is_authenticated():
                self._movil.login(nit=self.nit, clave=self.password_login)

            t0 = time.time()
            result = self._movil.emitir_factura(
                frase_paso=self.password_certificacion,
                tipo_dte=tipo_dte,
                nit_receptor=nit_receptor,
                nombre_receptor=nombre_receptor,
                direccion_receptor=direccion_receptor,
                items=items,
                moneda=moneda,
                **kwargs,
            )
            elapsed = time.time() - t0

            uuid = result.get("numeroAutorizacion") or result.get("uuid", "")
            return {"uuid": uuid, "source": "mobile", "time_s": round(elapsed, 2), "raw": result}
        except SatMovilAPIError as e:
            self._stats["mobile_failures"] += 1
            self._movil_last_error = str(e)
            logger.warning(f"[fallback] Mobile emitir failed: {e}")
            if e.status_code == 412:
                raise  # Wrong password — don't fallback, it'll fail on web too
            return None
        except Exception as e:
            self._stats["mobile_failures"] += 1
            self._movil_last_error = str(e)
            return None

    def _try_emitir_web(self, tipo_dte, nit_receptor, nombre_receptor, direccion_receptor, items, moneda, **kwargs):
        try:
            self._stats["web_calls"] += 1
            if not self._web:
                self._login_web()
            if not self._web_available or not self._web:
                return None

            t0 = time.time()

            regimes_used = set()
            web_items_nodes = []
            for idx, item in enumerate(items, 1):
                regime = (item.get("regimen") or "GENERAL").upper()
                regimes_used.add(regime)
                cantidad = float(item.get("cantidad", 1))
                precio = float(item.get("precio_unitario", item.get("precio", 0)))
                descuento = float(item.get("descuento", 0))
                subtotal = cantidad * precio
                total = subtotal - descuento
                taxes = self._web.build_tax_node(total, regime=regime)
                web_items_nodes.append({
                    "NumeroLinea": idx,
                    "BienOServicio": item.get("tipo_bien", "S"),
                    "Cantidad": cantidad,
                    "UnidadMedida": item.get("unidad_medida", "UND"),
                    "Descripcion": item["descripcion"],
                    "PrecioUnitario": round(precio, 2),
                    "Precio": round(subtotal, 2),
                    "Descuento": round(descuento, 2),
                    "Total": round(total, 2),
                    "Impuestos": taxes,
                })

            frase_keys = []
            if self.afiliacion == "PEQ":
                frase_keys.append("PEQ")
            else:
                frase_keys.append("GENERAL")
            if "EXPORT" in regimes_used:
                frase_keys.extend(["EXPORT_GEN", "EXPORT"])
            if "TURISMO_HOSPEDAJE" in regimes_used:
                frase_keys.append("TURISMO_HOSPEDAJE")
            frases_node = self._web.build_frase_node(frase_keys)

            totals_node = self._web.generate_totals(web_items_nodes)

            datos_generales = {
                "Tipo": tipo_dte, "FechaHoraEmision": "",
                "FechaHoraEmisionForm": "ISO", "CodigoMoneda": moneda,
            }
            if kwargs.get("exportacion"):
                datos_generales["Exp"] = "SI"

            datos_emision = {
                "DatosGenerales": datos_generales,
                "Emisor": {
                    "NITEmisor": self.nit,
                    "NombreEmisor": self._movil._nombre_emisor or self.nit,
                    "CodigoEstablecimiento": "1",
                    "NombreComercial": self._movil._nombre_emisor or self.nit,
                    "AfiliacionIVA": self.afiliacion,
                    "DireccionEmisor": {
                        "Direccion": "CIUDAD", "CodigoPostal": 1,
                        "municipio": "GUATEMALA", "departamento": "GUATEMALA", "pais": "GT",
                    },
                },
                "Receptor": {
                    "IDReceptor": nit_receptor,
                    "NombreReceptor": nombre_receptor,
                    "DireccionReceptor": {"Direccion": direccion_receptor or "ciudad"},
                },
                "Frases": frases_node,
                "Items": {"Item": web_items_nodes},
                "Totales": totals_node,
            }

            dte_doc = {
                "SAT": {
                    "DTE": {
                        "DatosEmision": datos_emision,
                        "Certificacion": {
                            "NITCertificador": self._web.nit_certificador,
                            "NombreCertificador": "Superintendencia de Administracion Tributaria",
                            "NumeroAutorizacion": {"Serie": "", "Numero": "", "text": ""},
                            "FechaHoraCertificacion": "",
                        },
                    }
                },
                "Signature": {
                    "SignedInfo": {"CanonicalizationMethod": {}, "SignatureMethod": {},
                                  "Reference": {"DigestMethod": {}, "DigestValue": {}}},
                    "SignatureValue": "",
                },
                "nombreNavegador": "Chrome 133.0.0.0",
            }

            result = self._web.certificar_dte(dte_doc, self.password_certificacion)
            elapsed = time.time() - t0

            if isinstance(result, dict) and result.get("detalle"):
                detalle = result["detalle"]
                if isinstance(detalle, list) and detalle:
                    d = detalle[0]
                    uuid = d.get("numeroAutorizacion", "")
                    return {"uuid": uuid, "source": "web", "time_s": round(elapsed, 2), "raw": result}
            uuid = result.get("uuid", "") if isinstance(result, dict) else ""
            return {"uuid": uuid, "source": "web", "time_s": round(elapsed, 2), "raw": result}
        except Exception as e:
            self._stats["web_failures"] += 1
            self._web_last_error = str(e)
            logger.warning(f"[fallback] Web emitir failed: {e}")
            return None

    def anular(self, uuid: str, nit_receptor: str = "CF", motivo: str = "Error en los datos de la descripcion") -> dict:
        """Annul a DTE with failover."""
        # Try mobile first
        if self._movil_available:
            try:
                self._stats["mobile_calls"] += 1
                if not self._movil.is_authenticated():
                    self._movil.login(nit=self.nit, clave=self.password_login)
                result = self._movil.anular_dte(
                    uuid=uuid,
                    frase_paso=self.password_certificacion,
                    nit_receptor=nit_receptor,
                    motivo=motivo,
                )
                return {"success": True, "source": "mobile", "raw": result}
            except SatMovilAPIError as e:
                self._stats["mobile_failures"] += 1
                self._movil_last_error = str(e)
                if e.status_code == 412:
                    raise

        # Fallback to web
        self._stats["fallbacks_triggered"] += 1
        try:
            self._stats["web_calls"] += 1
            if not self._web:
                self._login_web()
            if self._web:
                result = self._web.anular_dte(uuid=uuid, id_receptor=nit_receptor, motivo=motivo)
                return {"success": True, "source": "web", "raw": result}
        except Exception as e:
            self._stats["web_failures"] += 1
            self._web_last_error = str(e)

        return {"success": False, **self._build_both_failed_error("anular")}

    def listar_emitidos(self) -> list:
        """List issued DTEs (mobile API only — fast and sufficient)."""
        if not self._movil.is_authenticated():
            self._movil.login(nit=self.nit, clave=self.password_login)
        return self._movil.listar_emitidos()

    def listar_recibidos(self) -> list:
        """List received DTEs (mobile API only)."""
        if not self._movil.is_authenticated():
            self._movil.login(nit=self.nit, clave=self.password_login)
        return self._movil.listar_recibidos()

    def detalle_dte(self, uuid: str, nit_emisor: str, nit_receptor: str = "CF") -> dict:
        """Get DTE details."""
        if not self._movil.is_authenticated():
            self._movil.login(nit=self.nit, clave=self.password_login)
        return self._movil.detalle_dte(uuid=uuid, nit_emisor=nit_emisor, nit_receptor=nit_receptor)

    def descargar_pdf(self, uuid: str, nit_emisor: str, nit_receptor: str = "CF") -> bytes:
        """Download PDF of a DTE."""
        if not self._movil.is_authenticated():
            self._movil.login(nit=self.nit, clave=self.password_login)
        return self._movil.descargar_pdf(uuid=uuid, nit_emisor=nit_emisor, nit_receptor=nit_receptor)

    def consultar_nit(self, nit: str) -> str:
        """Look up a NIT, return the taxpayer name."""
        if not self._movil.is_authenticated():
            self._movil.login(nit=self.nit, clave=self.password_login)
        data = self._movil.consultar_nit(nit)
        if isinstance(data, dict):
            return data.get("nombre", str(data))
        return str(data)

    @property
    def stats(self) -> dict:
        """Return usage statistics for both APIs."""
        return {
            **self._stats,
            "mobile_authenticated": self._movil.is_authenticated(),
            "web_authenticated": self._web is not None and self._web_available,
            "mobile_last_error": self._movil_last_error,
            "web_last_error": self._web_last_error,
        }
