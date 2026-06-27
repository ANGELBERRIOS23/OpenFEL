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

        # Try preferred API first
        if self.prefer == "mobile" and self._movil_available:
            result = self._try_emitir_movil(
                tipo_dte, nit_receptor, nombre_receptor, direccion_receptor, items, moneda, **kwargs
            )
            if result:
                return result
            # Fallback to web
            self._stats["fallbacks_triggered"] += 1
            logger.warning("[fallback] Mobile emission failed, trying web API...")
            return self._try_emitir_web(
                tipo_dte, nit_receptor, nombre_receptor, direccion_receptor, items, moneda, **kwargs
            ) or {"error": "Both APIs failed", "mobile_error": self._movil_last_error, "web_error": self._web_last_error}
        else:
            # Web first, mobile fallback
            result = self._try_emitir_web(
                tipo_dte, nit_receptor, nombre_receptor, direccion_receptor, items, moneda, **kwargs
            )
            if result:
                return result
            self._stats["fallbacks_triggered"] += 1
            logger.warning("[fallback] Web emission failed, trying mobile API...")
            return self._try_emitir_movil(
                tipo_dte, nit_receptor, nombre_receptor, direccion_receptor, items, moneda, **kwargs
            ) or {"error": "Both APIs failed", "mobile_error": self._movil_last_error, "web_error": self._web_last_error}

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
            # Build items in web API format
            web_items = []
            for item in items:
                web_items.append({
                    "descripcion": item["descripcion"],
                    "cantidad": item.get("cantidad", 1),
                    "precio_unitario": item.get("precio_unitario", item.get("precio", 0)),
                    "descuento": item.get("descuento", 0),
                    "tipo": item.get("tipo_bien", "S"),
                })
            result = self._web.certificar_dte(
                tipo_dte=tipo_dte,
                nit_receptor=nit_receptor,
                nombre_receptor=nombre_receptor,
                items=web_items,
            )
            elapsed = time.time() - t0
            uuid = result.get("uuid", "")
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

        return {"success": False, "error": "Both APIs failed"}

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
