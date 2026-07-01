"""
SAT Guatemala FEL Mobile API Client
====================================

Pure JSON client for SAT's mobile API (svc.c.sat.gob.gt/api/v3).
Discovered by reverse-engineering the official Flutter FEL app (gob.sat.fel).

Key advantages over the web API:
  - No XML construction needed (server builds XML internally)
  - No AES-256 encryption needed
  - No digital signatures / firmarDocumento step
  - ~40% faster end-to-end (login + emit + annul)
  - Simpler error handling (HTTP status codes + JSON errors)

Usage:
    from sat_movil_api import SatMovilAPI

    api = SatMovilAPI()
    api.login(nit="120405237", clave="password")
    result = api.emitir_factura(...)
    api.anular_dte(uuid="...", ...)
"""

import requests
import time
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants extracted from APK reverse-engineering (libapp.so)
# ---------------------------------------------------------------------------
BASE_URL = "https://svc.c.sat.gob.gt/api/v3"
API_KEY = "XPJHZnixcMm2DWVSla2OQfIL82ZYm3EjT6Hy"
APP_VERSION = 130030001  # Matches the latest APK version string
TOKEN_TTL_SECONDS = 43200  # 12 hours (from JWT exp claim)


class SatMovilAPIError(Exception):
    """Raised when the mobile API returns an error response."""

    def __init__(self, message: str, status_code: int = None, response_body: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class SatMovilAPI:
    """
    Client for SAT Guatemala's mobile FEL API.

    This API is used internally by the official SAT FEL mobile app (Flutter).
    It exposes a JSON-only interface where the server handles all XML/XSD
    construction, digital signing, and certification internally.
    """

    def __init__(self, base_url: str = BASE_URL, api_key: str = API_KEY, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        # Session state
        self._token: Optional[str] = None
        self._token_expires: Optional[float] = None
        self._nit: Optional[str] = None
        self._nombre_emisor: Optional[str] = None
        self._establecimiento: Optional[str] = None
        self._direccion_establecimiento: Optional[dict] = None
        self._establecimientos: list = []
        self._tipo_personeria: str = "0"
        self._afiliacion_iva: Optional[str] = None

        # Reusable session for connection pooling
        self._session = requests.Session()
        self._session.headers.update({
            "apikey": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Dart/3.3 (dart:io)",
        })

    # -----------------------------------------------------------------------
    # Authentication
    # -----------------------------------------------------------------------

    def login(self, nit: str, clave: str) -> dict:
        """
        Authenticate against the mobile API.

        Args:
            nit: NIT of the taxpayer (without dashes or check digit)
            clave: Login password (same as Agencia Virtual password)

        Returns:
            dict with login response including emisor info

        Raises:
            SatMovilAPIError: If credentials are invalid (404) or other error
        """
        payload = {
            "nit": nit,
            "clave": clave,
            "colaborador": False,
            "invitado": False,
            "tokenMovil": "x",
            "tipoMovil": "Android",
            "appVersion": APP_VERSION,
        }

        resp = self._post("/auth/movil/fel/autenticarse", json=payload, authenticated=False)

        # Store session state
        self._token = resp.get("jwToken") or resp.get("token") or resp.get("felToken")
        self._token_expires = time.time() + TOKEN_TTL_SECONDS
        self._nit = nit
        self._nombre_emisor = resp.get("nombre", "")
        self._afiliacion_iva = resp.get("afiliacionIVA", "GEN")
        self._tipo_personeria = str(resp.get("tipoPersoneria") or "0")

        # Guardar TODOS los establecimientos (para que el usuario pueda elegir).
        # NO hay endpoint aparte: la lista completa viene en la respuesta del login.
        self._establecimientos = resp.get("establecimientos", []) or []
        if self._establecimientos:
            est0 = self._establecimientos[0]
            self._establecimiento = str(est0.get("numero", "1"))
            self._direccion_establecimiento = self._dir_est_from(est0)
        else:
            self._establecimiento = "1"
            self._direccion_establecimiento = None

        logger.info(f"Mobile API login OK: NIT={nit}, nombre={self._nombre_emisor}, "
                    f"establecimientos={len(self._establecimientos)}")
        return resp

    @staticmethod
    def _dir_est_from(est: dict) -> dict:
        """Construye direccionEstablecimiento desde un registro de establecimiento del login."""
        num = str(est.get("numero", "1"))
        return {
            "codigoEstablecimiento": num,
            "tipo": "",
            "direccion": est.get("vistaPrevia", "Guatemala"),
            "codigoPostal": "00000",
            "municipio": est.get("municipio", "GUATEMALA"),
            "departamento": est.get("departamento", "GUATEMALA"),
            "pais": "GT",
        }

    def get_establecimientos(self) -> list:
        """
        Lista de establecimientos del emisor para que el usuario ELIJA (sin hardcodear).
        Se obtiene del login (no hay endpoint dedicado). Cada item: numero, nombre,
        direccion, estado. Pasar el 'numero' elegido como `establecimiento=` en emitir_factura.
        """
        return [
            {
                "numero": str(e.get("numero", "")),
                "nombre": e.get("nombre", ""),
                "direccion": e.get("vistaPrevia", ""),
                "estado": e.get("estado", ""),
            }
            for e in self._establecimientos
        ]

    def is_authenticated(self) -> bool:
        """Check if the current token is still valid (not expired)."""
        if not self._token or not self._token_expires:
            return False
        return time.time() < self._token_expires

    def _ensure_auth(self):
        """Raise if not authenticated or token expired."""
        if not self.is_authenticated():
            raise SatMovilAPIError(
                "Not authenticated or token expired. Call login() first.",
                status_code=401,
            )

    def export_session(self) -> dict | None:
        if not self.is_authenticated():
            return None
        return {
            "token": self._token,
            "token_expires": self._token_expires,
            "nit": self._nit,
            "nombre_emisor": self._nombre_emisor,
            "afiliacion_iva": self._afiliacion_iva,
            "establecimiento": self._establecimiento,
            "direccion_establecimiento": self._direccion_establecimiento,
            "establecimientos": self._establecimientos,
            "tipo_personeria": self._tipo_personeria,
        }

    def import_session(self, data: dict) -> bool:
        if not data or not data.get("token"):
            return False
        if time.time() >= data.get("token_expires", 0):
            return False
        self._token = data["token"]
        self._token_expires = data["token_expires"]
        self._nit = data.get("nit")
        self._nombre_emisor = data.get("nombre_emisor", "")
        self._afiliacion_iva = data.get("afiliacion_iva", "GEN")
        self._establecimiento = data.get("establecimiento", "1")
        self._direccion_establecimiento = data.get("direccion_establecimiento")
        self._establecimientos = data.get("establecimientos", []) or []
        self._tipo_personeria = str(data.get("tipo_personeria") or "0")
        logger.info(f"Mobile session restored for NIT={self._nit}, expires in {int(self._token_expires - time.time())}s")
        return True

    # -----------------------------------------------------------------------
    # Core Operations
    # -----------------------------------------------------------------------

    def get_server_time(self) -> dict:
        """Get SAT server time. Useful for syncing emission timestamps."""
        return self._get("/core/core/tiempo")

    def get_exchange_rate(self, moneda: str = "GTQ", fecha: Optional[str] = None) -> dict:
        """
        Get exchange rate from SAT.

        Args:
            moneda: Currency code (default GTQ)
            fecha: Date in dd/mm/yyyy format (default: today)
        """
        if fecha is None:
            fecha = datetime.now().strftime("%d/%m/%Y")
        return self._post("/core/tasa/cambio", json={"moneda": moneda, "fecha": fecha})

    def consultar_nit(self, nit: str) -> dict:
        """
        Look up a NIT in the RTU registry.

        Args:
            nit: NIT to look up (can be "CF" for Consumidor Final)

        Returns:
            dict with receptor name and info
        """
        self._ensure_auth()
        return self._post("/core/receptor/consulta", json={"NIT": nit})

    def consultar_totales(self) -> dict:
        """Get emission totals/statistics for the authenticated issuer."""
        self._ensure_auth()
        return self._get("/core/emisor/consulta/totales")

    # -----------------------------------------------------------------------
    # DTE Emission
    # -----------------------------------------------------------------------

    def emitir_factura(
        self,
        frase_paso: str,
        tipo_dte: str = "FACT",
        nit_receptor: str = "CF",
        nombre_receptor: str = "CONSUMIDOR FINAL",
        direccion_receptor: str = "ciudad",
        items: list = None,
        moneda: str = "GTQ",
        # Complementos and special flags
        exportacion: bool = False,
        cambiaria: bool = False,
        es_factura_especial: bool = False,
        es_nota: bool = False,
        tipo_especial: Optional[str] = None,
        complemento_notas: Optional[dict] = None,
        complemento_exportacion: Optional[dict] = None,
        complemento_factura_especial: Optional[dict] = None,
        complemento_cambiaria: Optional[list] = None,
        frases: Optional[list] = None,
        establecimiento: Optional[str] = None,
        direccion_establecimiento: Optional[dict] = None,
    ) -> dict:
        """
        Emit a DTE (Documento Tributario Electronico) via the mobile API.

        The server handles all XML construction, XSD validation, and digital
        signing internally. You just send the business data as JSON.

        Args:
            frase_paso: Certification password (password_certificacion)
            tipo_dte: DTE type (FACT, FPEQ, FCAM, FESP, NABN, NDEB, NCRE, RDON)
            nit_receptor: Receptor NIT or "CF"
            nombre_receptor: Receptor name
            direccion_receptor: Receptor address
            items: List of item dicts with keys:
                   - descripcion (str)
                   - cantidad (float)
                   - precio_unitario (float)
                   - tipo_bien (str): "B" for goods, "S" for services
                   - descuento (float, optional, default 0)
                   - impuestos (list, optional, for GEN regime)
            moneda: Currency code (default GTQ)
            exportacion: Whether this is an export invoice
            cambiaria: Whether this is a cambiaria invoice
            es_factura_especial: Whether this is a factura especial
            es_nota: Whether this is NCRE/NDEB
            tipo_especial: "CUI" or "EXT" for FESP
            complemento_notas: Dict with original document reference for NCRE/NDEB
            complemento_exportacion: Dict with export details
            complemento_factura_especial: Dict with ISR/IVA retentions for FESP
            complemento_cambiaria: List of payment schedule entries
            frases: List of frase dicts [{"tipo": "1", "escenario": "1"}]
            establecimiento: Override for establishment code
            direccion_establecimiento: Override for establishment address

        Returns:
            dict with UUID, serie, numero, and certification info

        Raises:
            SatMovilAPIError: If emission fails (412 = wrong frase_paso, etc.)
        """
        self._ensure_auth()

        if items is None:
            items = [{"descripcion": "Servicio", "cantidad": 1, "precio_unitario": 1.0,
                      "tipo_bien": "S", "descuento": 0}]

        # Determine affiliation and tax handling
        afiliacion = self._afiliacion_iva or "GEN"
        nodo_impuestos = afiliacion == "GEN" and not es_factura_especial
        iva_automatico = True

        # Build detail items
        detalle = []
        total_impuestos = 0.0
        total_descuentos = 0.0
        total_monto = 0.0

        for idx, item in enumerate(items, 1):
            cantidad = float(item.get("cantidad", 1))
            precio = float(item.get("precio_unitario", 0))
            descuento = float(item.get("descuento", 0))
            subtotal = cantidad * precio
            item_total = subtotal - descuento

            # Calculate IVA for GEN regime
            item_impuestos = 0.0
            lista_impuestos = []
            if nodo_impuestos and item.get("impuestos"):
                lista_impuestos = item["impuestos"]
                item_impuestos = sum(float(i.get("montoImpuesto", i.get("monto", 0)) or 0) for i in lista_impuestos)
            elif nodo_impuestos:
                # Auto-calculate IVA 12% — estructura EXACTA de la app movil:
                # strings de 6 decimales + todos los campos que exige el XSD.
                monto_gravable = round(item_total / 1.12, 6)
                item_impuestos = round(item_total - monto_gravable, 6)
                lista_impuestos = [{
                    "codigoUnidadGravable": "1",
                    "nombreUnidadGravable": "Tasa 12.00%",
                    "nombreCorto": "IVA",
                    "operaSobreCasilla": "MontoGravable",
                    "factor": "0.12",
                    "cantidadUnidadGravable": "null",
                    "montoGravable": f"{monto_gravable:.6f}",
                    "montoImpuesto": f"{item_impuestos:.6f}",
                    "sumaTotal": "false",
                }]

            total_impuestos += item_impuestos
            total_descuentos += descuento
            total_monto += item_total

            detalle.append({
                "orden": idx,
                "tipoBienOServicio": item.get("tipo_bien", "S"),
                "descripcion": item["descripcion"],
                "cantidad": cantidad,
                "precionUnitario": precio,  # Note: SAT uses this typo
                "subtotal": subtotal,
                "descuento": descuento,
                "total": item_total,
                "impuestos": item_impuestos,
                "listaImpuestos": lista_impuestos,
            })

        # Default frases based on DTE type
        if frases is None:
            if afiliacion == "PEQ":
                frases = [{"tipo": "3", "escenario": "1"}]
            elif tipo_dte == "NABN":
                frases = []
            elif tipo_dte in ("NCRE", "NDEB"):
                frases = [{"tipo": "1", "escenario": "1"}]
            else:
                frases = [{"tipo": "1", "escenario": "1"}]

        # Get exchange rate
        tasa_cambio = 7.62313  # Default; ideally call get_exchange_rate()
        try:
            rate_resp = self.get_exchange_rate(moneda)
            if isinstance(rate_resp, dict) and rate_resp.get("tasaCambio"):
                tasa_cambio = float(rate_resp["tasaCambio"])
        except Exception:
            pass  # Use default

        # Resolve establishment — el usuario puede pasar `establecimiento` = numero;
        # la direccion y el nombre se auto-rellenan desde la lista del login (sin hardcodear).
        est_code = str(establecimiento or self._establecimiento or "1")
        _est_rec = next((e for e in self._establecimientos
                         if str(e.get("numero")) == est_code), None)
        _est_nombre = (_est_rec or {}).get("nombre") or self._nombre_emisor
        dir_est = (direccion_establecimiento
                   or (self._dir_est_from(_est_rec) if _est_rec else None)
                   or self._direccion_establecimiento
                   or {
                       "codigoEstablecimiento": est_code, "tipo": "",
                       "direccion": "Guatemala", "codigoPostal": "00000",
                       "municipio": "GUATEMALA", "departamento": "GUATEMALA", "pais": "GT",
                   })

        # Build the full emission payload
        payload = {
            "frasePaso": frase_paso,
            "nitEmisor": self._nit,
            "nombreEmisor": self._nombre_emisor,
            "tipoPersoneria": getattr(self, "_tipo_personeria", "0") or "0",
            "tipoDte": tipo_dte,
            "nitReceptor": nit_receptor,
            "destinoVenta": None,
            "tipoEspecial": tipo_especial,
            "nombreReceptor": nombre_receptor,
            "direccionReceptor": direccion_receptor,
            "fecha": datetime.now().strftime("%d/%m/%Y"),
            "codigoEstablecimiento": est_code,
            "establecimiento": f"{est_code} - {_est_nombre}",
            "moneda": moneda,
            "afiliacionIVA": afiliacion,
            "tasaCambio": tasa_cambio,
            "tasaDolar": tasa_cambio,
            "impuestos": round(total_impuestos, 6),
            "total": round(total_monto, 2),
            "descuentos": round(total_descuentos, 2),
            "exportacion": exportacion,
            "clasificacionEmisor": False,
            "espectaculoPublico": False,
            "cambiaria": cambiaria,
            "nodoImpuestos": nodo_impuestos,
            "ivaAutomatico": iva_automatico,
            "esNotaDebitoCredito": es_nota,
            "cantidadAbonos": 0,
            "frecuenciaVencimientos": 0,
            "detalleCambiaria": complemento_cambiaria or [],
            "complementoMedioDePago": {
                "tipoFormaDePago": "", "numeroTransaccion": "0",
                "fechaTransaccion": "", "montoTransaccion": "0",
            },
            "complementoExportacion": complemento_exportacion or {
                "nombreConsignatario": "", "direccionConsignatario": "",
                "incoterm": "", "codigoConsignatario": "",
                "nombreComprador": "", "direccionComprador": "",
                "codigoComprador": "", "otrasReferencias": "",
                "nombreExportador": "", "codigoExportador": "",
            },
            "complementoNotas": complemento_notas or {
                "fechaEmisionDocumentoOrigen": "", "motivoAjuste": "",
                "numeroAutorizacionDocumentoOrigen": "",
                "numeroDocumentoOrigen": "", "serieDocumentoOrigen": "",
            },
            "complementoConstancias": {
                "fechaEmisionDocumentoOrigen": "",
                "numeroAutorizacionDocumentoOrigen": "",
                "numeroDocumentoOrigen": "", "serieDocumentoOrigen": "",
            },
            "complementoCobroCuentaAjena": {
                "nitContribuyente": "", "numeroDocumento": "",
                "fechaDocumento": "", "conceptoCobro": "",
                "montoCobroDAI": "0", "montoCobroIVA": "0",
                "baseImponible": "0", "montoCobrosOtros": "0",
                "montoCobroTotal": "0",
            },
            "complementoEspectaculosPublicos": {
                "codigoEvento": "", "nombreEvento": "",
                "nombreLocalidad": "", "precioAdmision": "0.00",
                "numeroBoleto": "",
            },
            "esFacturaEspecial": es_factura_especial,
            "habilitaFraseFacturaEspecial": es_factura_especial,
            "complementoFacturaEspecial": complemento_factura_especial or {
                "retencionISR": 0.0, "retencionIVA": 0.0,
                "totalMenosRetenciones": 0.0,
            },
            "detalle": detalle,
            "resumenImpuesto": ([{"nombreCorto": "IVA", "total": f"{total_impuestos:.6f}"}]
                                if nodo_impuestos and total_impuestos else []),
            "frases": frases,
            "direccionEstablecimiento": dir_est,
        }

        # Add export frases if needed
        if exportacion and not any(f.get("tipo") == "4" for f in frases):
            payload["frases"].append({"tipo": "4", "escenario": "1"})

        resp = self._post("/core/dte/emision", json=payload)
        logger.info(f"DTE emitted via mobile API: {resp.get('uuid', 'unknown')}")
        return resp

    # -----------------------------------------------------------------------
    # DTE Annulment
    # -----------------------------------------------------------------------

    def anular_dte(
        self,
        uuid: str,
        frase_paso: str,
        nit_receptor: str = "CF",
        motivo: str = "Error en los datos de la descripcion",
    ) -> dict:
        """
        Annul a previously certified DTE.

        Args:
            uuid: UUID of the DTE to annul
            frase_paso: Certification password
            nit_receptor: NIT of the receptor on the original DTE
            motivo: Reason for annulment

        Returns:
            dict with annulment confirmation

        Raises:
            SatMovilAPIError: If annulment fails
        """
        self._ensure_auth()

        payload = {
            "nitReceptor": nit_receptor,
            "nitEmisor": self._nit,
            "frasePaso": frase_paso,
            "motivoAnulacion": motivo,
            "UUID": uuid,
        }

        resp = self._post("/core/dte/anulacion", json=payload)
        logger.info(f"DTE annulled via mobile API: UUID={uuid}")
        return resp

    # -----------------------------------------------------------------------
    # Query Operations
    # -----------------------------------------------------------------------

    def listar_emitidos(self, nit: Optional[str] = None, establecimiento: str = "") -> dict:
        """
        List issued DTEs for the authenticated taxpayer.

        Args:
            nit: Override NIT (default: authenticated NIT)
            establecimiento: Filter by establishment (empty = all)
        """
        self._ensure_auth()
        return self._post("/core/dte/emitidos", json={
            "nit": nit or self._nit,
            "establecimiento": establecimiento,
        })

    def listar_recibidos(self, nit: Optional[str] = None, establecimiento: str = "") -> dict:
        """
        List received DTEs for the authenticated taxpayer.

        Args:
            nit: Override NIT (default: authenticated NIT)
            establecimiento: Filter by establishment (empty = all)
        """
        self._ensure_auth()
        return self._post("/core/dte/recibidos", json={
            "nit": nit or self._nit,
            "establecimiento": establecimiento,
        })

    def detalle_dte(
        self,
        uuid: str,
        nit_emisor: str,
        nit_receptor: str = "CF",
    ) -> dict:
        """
        Get full details of a specific DTE.

        Args:
            uuid: UUID of the DTE
            nit_emisor: NIT of the issuer
            nit_receptor: NIT of the receptor
        """
        self._ensure_auth()
        return self._post("/core/dte/detalle", json={
            "nitEmisor": nit_emisor,
            "nitReceptor": nit_receptor,
            "UUID": uuid,
            "visualizacion2": True,
        })

    def descargar_pdf(self, uuid: str, nit_emisor: str, nit_receptor: str = "CF") -> bytes:
        """
        Get PDF representation of a DTE.

        Args:
            uuid: UUID of the DTE
            nit_emisor: NIT of the issuer
            nit_receptor: NIT of the receptor

        Returns:
            bytes: Raw PDF binary content
        """
        self._ensure_auth()
        url = f"{self.base_url}/core/dte/representacion/pdf"
        headers = self._build_headers(True)
        resp = self._session.post(url, headers=headers, timeout=self.timeout, json={
            "nitEmisor": nit_emisor,
            "nitReceptor": nit_receptor,
            "UUID": uuid,
        })
        if resp.status_code == 200 and resp.content[:4] == b"%PDF":
            return resp.content
        raise SatMovilAPIError(
            f"PDF download failed: HTTP {resp.status_code}",
            status_code=resp.status_code,
        )

    # -----------------------------------------------------------------------
    # Convenience Methods
    # -----------------------------------------------------------------------

    def emitir_factura_simple(
        self,
        frase_paso: str,
        descripcion: str,
        precio: float,
        nit_receptor: str = "CF",
        nombre_receptor: str = "CONSUMIDOR FINAL",
        tipo_dte: Optional[str] = None,
    ) -> dict:
        """
        Emit a simple single-item invoice. Automatically determines DTE type
        based on the taxpayer's affiliation (GEN→FACT, PEQ→FPEQ).

        Args:
            frase_paso: Certification password
            descripcion: Item description
            precio: Total price (IVA included for GEN)
            nit_receptor: Receptor NIT
            nombre_receptor: Receptor name
            tipo_dte: Override DTE type (default: auto-detect from affiliation)
        """
        if tipo_dte is None:
            tipo_dte = "FPEQ" if self._afiliacion_iva == "PEQ" else "FACT"

        items = [{
            "descripcion": descripcion,
            "cantidad": 1,
            "precio_unitario": precio,
            "tipo_bien": "S",
            "descuento": 0,
        }]

        return self.emitir_factura(
            frase_paso=frase_paso,
            tipo_dte=tipo_dte,
            nit_receptor=nit_receptor,
            nombre_receptor=nombre_receptor,
            items=items,
        )

    def full_cycle_test(self, frase_paso: str) -> dict:
        """
        Run a full emission + annulment cycle for testing.
        Emits a Q1.00 invoice to CF and immediately annuls it.

        Returns:
            dict with timing info and UUIDs
        """
        t0 = time.time()
        emit_resp = self.emitir_factura_simple(
            frase_paso=frase_paso,
            descripcion="PRUEBA CICLO COMPLETO - ANULAR",
            precio=1.00,
        )
        t_emit = time.time() - t0

        uuid = emit_resp.get("uuid") or emit_resp.get("UUID")
        if not uuid:
            raise SatMovilAPIError("Emission did not return a UUID", response_body=emit_resp)

        t1 = time.time()
        anul_resp = self.anular_dte(
            uuid=uuid,
            frase_paso=frase_paso,
            motivo="Error en los datos de la descripcion",
        )
        t_anul = time.time() - t1

        return {
            "uuid": uuid,
            "emission_time_s": round(t_emit, 2),
            "annulment_time_s": round(t_anul, 2),
            "total_time_s": round(time.time() - t0, 2),
            "emission_response": emit_resp,
            "annulment_response": anul_resp,
        }

    # -----------------------------------------------------------------------
    # HTTP Internals
    # -----------------------------------------------------------------------

    def _get(self, path: str, authenticated: bool = True, **kwargs) -> dict:
        """Make an authenticated GET request."""
        url = f"{self.base_url}{path}"
        headers = self._build_headers(authenticated)

        try:
            resp = self._session.get(url, headers=headers, timeout=self.timeout, **kwargs)
        except requests.RequestException as e:
            raise SatMovilAPIError(f"Request failed: {e}")

        return self._handle_response(resp, path)

    def _post(self, path: str, authenticated: bool = True, **kwargs) -> dict:
        """Make an authenticated POST request."""
        url = f"{self.base_url}{path}"
        headers = self._build_headers(authenticated)

        try:
            resp = self._session.post(url, headers=headers, timeout=self.timeout, **kwargs)
        except requests.RequestException as e:
            raise SatMovilAPIError(f"Request failed: {e}")

        return self._handle_response(resp, path)

    def _build_headers(self, authenticated: bool) -> dict:
        """Build request headers, adding feltoken if authenticated."""
        headers = {}
        if authenticated and self._token:
            headers["feltoken"] = self._token
        return headers

    def _handle_response(self, resp: requests.Response, path: str) -> dict:
        """Parse response and raise on errors."""
        # Known error codes
        if resp.status_code == 404 and "autenticarse" in path:
            raise SatMovilAPIError(
                "Invalid credentials (NIT or password incorrect)",
                status_code=404,
                response_body=self._safe_json(resp),
            )
        if resp.status_code == 412:
            raise SatMovilAPIError(
                "Precondition failed — likely wrong frasePaso (certification password)",
                status_code=412,
                response_body=self._safe_json(resp),
            )
        if resp.status_code == 401:
            raise SatMovilAPIError(
                "Unauthorized — token expired or invalid",
                status_code=401,
                response_body=self._safe_json(resp),
            )
        if resp.status_code >= 400:
            body = self._safe_json(resp)
            error_obj = body.get("error", {})
            msg = error_obj.get("message", body.get("mensaje", f"HTTP {resp.status_code}"))
            raise SatMovilAPIError(
                f"API error on {path}: {msg}",
                status_code=resp.status_code,
                response_body=body,
            )

        # Successful response — unwrap SAT's envelope {status, mensaje, data}
        body = self._safe_json(resp)
        if isinstance(body, dict) and "data" in body and body.get("status") == 0:
            return body["data"]
        return body

    @staticmethod
    def _safe_json(resp: requests.Response) -> dict:
        """Try to parse JSON, return empty dict on failure."""
        try:
            return resp.json()
        except (ValueError, TypeError):
            return {"raw_text": resp.text[:2000]}

    # -----------------------------------------------------------------------
    # Context Manager
    # -----------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """Close the underlying requests session."""
        self._session.close()

    def __repr__(self):
        auth_status = "authenticated" if self.is_authenticated() else "not authenticated"
        return f"<SatMovilAPI({auth_status}, nit={self._nit})>"
