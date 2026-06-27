import re
import json
import base64
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Hash import SHA256
from Crypto.Random import get_random_bytes

class SatAPI:
    def __init__(self, adaptive: bool = True):
        """Args:
            adaptive: si True (default), envuelve la sesión HTTP con
                SatAdaptiveClient que aplica self-healing reactivo.
                Pasar `adaptive=False` para comportamiento legacy.
        """
        self.session = requests.Session()
        # Mocking browser User-Agent
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
        })
        self.base_url = "https://farm3.sat.gob.gt"
        self.fel_base_url = "https://felav.c.sat.gob.gt"
        self.token = None
        self.validacion = None
        self.authtoken = None        # token para felcons (módulo consulta)
        self.consulta_url = None     # URL del módulo consulta con Nit+Clave
        self._dedup_cache = {}       # {request_id: result} — evita doble certificación

        # ─── Self-healing layer (v4) ────────────────────────────────────────
        # Wrapper opcional sobre self.session que aplica las 4 estrategias de
        # self-heal: header rotation, param discovery, header discovery,
        # relaxed success codes. Cada heal queda loggeado con BEFORE→AFTER en
        # `.sat_heal_log.jsonl` para revisión posterior.
        #
        # Importante: NO reemplazamos self.session — el cliente adaptive
        # comparte la session, así que las cookies y headers base se respetan.
        # Para usarlo, llamar `self._adaptive.get/post(...)` en vez de
        # `self.session.get/post(...)` desde los métodos que querramos curar.
        self._adaptive = None
        if adaptive:
            try:
                from sat_adaptive_client import SatAdaptiveClient
                self._adaptive = SatAdaptiveClient(self)
            except ImportError:
                # adaptive es opcional — si no está el módulo, seguimos sin él.
                pass
        
    def login(self, username, password):
        """Logs into SAT Agencia Virtual and gets session cookies."""
        login_url = f"{self.base_url}/menu/login.jsf"
        
        # 1. Get initial JSF ViewState
        resp = self.session.get(login_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        view_state = soup.find('input', {'name': 'javax.faces.ViewState'})
        if not view_state:
            raise Exception("Could not find ViewState on login page")
            
        # 2. Perform Login POST
        payload = {
            'formContent': 'formContent',
            'formContent:username': username,
            'formContent:password': password,
            'formContent:cmdbtnIngresar': '',
            'javax.faces.ViewState': view_state['value']
        }
        
        resp = self.session.post(login_url, data=payload)
        
        if 'Inicio' in resp.text or 'formMenu' in resp.text or 'Emitir Documento' in resp.text:
            return True
        return False

    def get_fel_credentials(self):
        """Extracts the NIT and dynamic Clave required to start the FEL session."""
        portada_url = f"{self.base_url}/menu/portada.jsf"
        resp = self.session.get(portada_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        dtes_link = soup.find('span', string='Emitir Documento Tributario Electrónico (DTE)')
        if not dtes_link:
            raise Exception("No se encontró el enlace Emitir DTE en la portada")
            
        link_a = dtes_link.find_parent('a')
        onclick_str = link_a['onclick']

        # Source component ID lives in the onclick s:"..." field (the element may have no id attr)
        source_match = re.search(r'\bs:"([^"]+)"', onclick_str)
        link_id = source_match.group(1) if source_match else link_a.get('id', 'frmMenu:j_idt41')
        print(f"[DEBUG] Found link source ID: {link_id}")

        params_raw = re.findall(r'name:"([^"]+)",value:"([^"]*)"', onclick_str)
        ajax_params = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source':          link_id,
            'javax.faces.partial.execute': link_id,
            'javax.faces.partial.render':  link_id,
            link_id: link_id,
            'frmMenu': 'frmMenu',
        }

        view_state = soup.find('input', {'name': 'javax.faces.ViewState'})
        if view_state:
            ajax_params['javax.faces.ViewState'] = view_state['value']

        for k, v in params_raw:
            # Unescape JS-escaped slashes/dashes in param values
            ajax_params[k] = v.replace('\\/', '/').replace('\\-', '-')

        # PrimeFaces AJAX — server re-renders the menu component; the FEL URL with
        # Nit= and Clave= is embedded inside an href in the updated CDATA block
        redirect_resp = self.session.post(portada_url, data=ajax_params, headers={
            'Faces-Request': 'partial/ajax',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': self.base_url,
            'Referer': portada_url,
            'X-Requested-With': 'XMLHttpRequest',
        })

        raw = redirect_resp.text
        import html as _html

        # Strategy 1: <redirect url="..."/> PrimeFaces navigation response
        redirect_tag = re.search(r'<redirect\s+url=["\']([^"\']+)["\']', raw)
        if redirect_tag:
            fel_url = _html.unescape(redirect_tag.group(1)).replace('\\/', '/').replace('\\-', '-')
        else:
            # Strategy 2: URL with Nit= and Clave= embedded in CDATA (HTML href attribute)
            clean = _html.unescape(raw).replace('\\/', '/').replace('\\-', '-')
            match = re.search(
                r'https://felav[0-9a-zA-Z]*\.c\.sat\.gob\.gt/[^"\'\s<]+[?&][Nn]it=\d+[^"\'\s<]*[Cc]lave=[a-fA-F0-9]+',
                clean
            )
            if not match:
                raise Exception(
                    f"No se extrajo URL de FEL con Nit+Clave "
                    f"(status={redirect_resp.status_code}, len={len(raw)})"
                )
            fel_url = match.group(0)

        nit_match   = re.search(r'[Nn]it=(\d+)', fel_url)
        clave_match = re.search(r'[Cc]lave=([a-fA-F0-9]+)', fel_url)

        if not nit_match or not clave_match:
            raise Exception(f"No se pudo extraer Nit o Clave de URL: {fel_url}")
            
        print("[*] Performing GET on FEL URL to establish session...")
        self.fel_url = fel_url
        res = self.session.get(fel_url)
        soup_fel = BeautifulSoup(res.text, 'html.parser')
        api_val = soup_fel.find(id='urlApiRest')
        nit_cert = soup_fel.find(id='nitCertificador')
        
        self.api_rest_url = api_val.text.strip() if api_val else f"{self.fel_base_url}/fel-rest/rest"
        self.nit_certificador = nit_cert.text.strip() if nit_cert else ""
        print(f"[+] urlApiRest extracted: {self.api_rest_url}")
        print(f"[+] NIT Certificador extracted: {self.nit_certificador}")
            
        return nit_match.group(1), clave_match.group(1)

    def iniciar_sesion_fel(self, nit, clave):
        """Calls DatosIniciales endpoint to retrieve the JWT Token and AES Validacion Key."""
        url = f"{self.api_rest_url}/privado/DatosIniciales"
        payload = {
            "usuario": nit,
            "clave": clave
        }
        
        resp = self.session.post(url, json=payload, headers={
            'Content-Type': 'application/json;charset=utf-8',
            'Accept': 'application/json;charset=utf-8',
            'Origin': self.fel_base_url,
            'Referer': self.fel_url
        })
        
        try:
            data = resp.json()
        except Exception:
            raise Exception(f"Fallo al Iniciar FEL (Not JSON) Status: {resp.status_code}, Body: {resp.text}")
            
        if not data.get("respuesta"):
            raise Exception(f"Fallo al iniciar FEL: {resp.text}")
            
        self.token = data["respuesta"].get("tokenJWT")
        self.validacion = data["respuesta"].get("validacion")
        return data["respuesta"]

    def get_consulta_credentials(self) -> tuple[str, str]:
        """
        Encuentra el menu item 'Consultar DTE' en la portada, hace el click AJAX
        y extrae Nit+Clave del módulo felcons.c.sat.gob.gt.
        Retorna (nit, clave).
        """
        portada_url = f"{self.base_url}/menu/portada.jsf"
        resp = self.session.get(portada_url)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Buscar el span del menu item de consulta (varios textos posibles)
        consulta_span = None
        for texto in [
            'Consultar DTE',
            'Consulta DTE',
            'Consulta de DTE',
            'Consultar Documento Tributario Electrónico',
            'Consultar Documento',
            'FEL Consulta',
            'Consulta FEL',
        ]:
            consulta_span = soup.find('span', string=texto)
            if consulta_span:
                break

        if not consulta_span:
            # Búsqueda parcial como fallback
            for span in soup.find_all('span'):
                if span.string and 'onsult' in span.string and 'DTE' in span.string:
                    consulta_span = span
                    break

        if not consulta_span:
            # Listar todos los spans del menú para ayudar al debug
            menu_spans = [s.string for s in soup.find_all('span') if s.string and len(s.string) > 5]
            raise Exception(
                f"No se encontró el enlace Consultar DTE en la portada. "
                f"Spans disponibles: {menu_spans[:20]}"
            )

        link_a = consulta_span.find_parent('a')
        onclick_str = link_a['onclick']

        source_match = re.search(r'\bs:"([^"]+)"', onclick_str)
        link_id = source_match.group(1) if source_match else link_a.get('id', '')
        print(f"[DEBUG] Consulta link source ID: {link_id}")

        params_raw = re.findall(r'name:"([^"]+)",value:"([^"]*)"', onclick_str)
        ajax_params = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source':          link_id,
            'javax.faces.partial.execute': link_id,
            'javax.faces.partial.render':  link_id,
            link_id: link_id,
            'frmMenu': 'frmMenu',
        }

        view_state = soup.find('input', {'name': 'javax.faces.ViewState'})
        if view_state:
            ajax_params['javax.faces.ViewState'] = view_state['value']

        for k, v in params_raw:
            ajax_params[k] = v.replace('\\/', '/').replace('\\-', '-')

        redirect_resp = self.session.post(portada_url, data=ajax_params, headers={
            'Faces-Request': 'partial/ajax',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': self.base_url,
            'Referer': portada_url,
            'X-Requested-With': 'XMLHttpRequest',
        })

        raw = redirect_resp.text
        import html as _html

        redirect_tag = re.search(r'<redirect\s+url=["\']([^"\']+)["\']', raw)
        if redirect_tag:
            consulta_url = _html.unescape(redirect_tag.group(1)).replace('\\/', '/').replace('\\-', '-')
        else:
            clean = _html.unescape(raw).replace('\\/', '/').replace('\\-', '-')
            match = re.search(
                r'https://felcons\.c\.sat\.gob\.gt/[^"\'\s<]+[?&][Nn]it=\d+[^"\'\s<]*[Cc]lave=[a-fA-F0-9]+',
                clean
            )
            if not match:
                raise Exception(
                    f"No se extrajo URL de consulta con Nit+Clave "
                    f"(status={redirect_resp.status_code}, preview={raw[:400]})"
                )
            consulta_url = match.group(0)

        nit_match   = re.search(r'[Nn]it=(\d+)', consulta_url)
        clave_match = re.search(r'[Cc]lave=([a-fA-F0-9]+)', consulta_url)

        if not nit_match or not clave_match:
            raise Exception(f"No se pudo extraer Nit o Clave de URL: {consulta_url}")

        self.consulta_url = consulta_url
        return nit_match.group(1), clave_match.group(1)

    def iniciar_sesion_consulta(self) -> str:
        """
        Inicializa la sesión en el módulo felcons y obtiene el authtoken.

        Flujo:
          1. GET la consulta_url (obtenida de get_consulta_credentials).
          2. El servidor devuelve ACCESS_TOKEN como Set-Cookie (JWT válido 1 hora).
          3. Extrae el token de la cookie y lo guarda en self.authtoken.

        Retorna el authtoken.
        """
        if not self.consulta_url:
            raise Exception("consulta_url no disponible — llame a get_consulta_credentials primero")

        # GET la consulta_url — el servidor devuelve ACCESS_TOKEN como Set-Cookie
        resp_page = self.session.get(self.consulta_url)
        print(f"[debug] consulta page ({resp_page.status_code}, {len(resp_page.text)} bytes)")

        # ACCESS_TOKEN viene en la cookie (la requests.Session lo guarda automáticamente)
        access_token = self.session.cookies.get('ACCESS_TOKEN', domain='felcons.c.sat.gob.gt')
        if not access_token:
            # Fallback: buscar en todos los dominios
            access_token = self.session.cookies.get('ACCESS_TOKEN')
        if not access_token:
            # Buscar en el header Set-Cookie directamente (por si hay duplicados)
            set_cookie = resp_page.headers.get('Set-Cookie', '')
            m = re.search(r'ACCESS_TOKEN=(eyJ[^;]+)', set_cookie)
            if m:
                access_token = m.group(1)

        if not access_token:
            raise Exception(
                f"No se encontró ACCESS_TOKEN en la respuesta de {self.consulta_url}. "
                f"Set-Cookie: {resp_page.headers.get('Set-Cookie', '(vacío)')[:300]}"
            )

        self.authtoken = access_token
        print(f"[+] authtoken (ACCESS_TOKEN) obtenido de cookie")
        return access_token

    def consultar_dte(
        self,
        nit_usuario: str,
        tipo_operacion: str,
        fecha_ini: str,
        fecha_fin: str,
        **filtros,
    ) -> list:
        """
        Consulta DTEs emitidos o recibidos en un rango de fechas.

        Args:
            nit_usuario:     NIT del contribuyente que consulta.
            tipo_operacion:  "E" = Emitidos, "R" = Recibidos.
            fecha_ini:       Fecha inicio en formato dd-MM-yyyy (ej. "01-03-2026").
            fecha_fin:       Fecha fin en formato dd-MM-yyyy (ej. "31-03-2026").
            **filtros:       Filtros opcionales:
                               tipoDte, establecimiento, noAutorizacion,
                               nitIdReceptor, estadoDte, serie, numero,
                               moneda, montoTotalRangoIni, montoTotalRangoFinal,
                               nitCertificador.

        Returns:
            Lista de dicts. Campos clave por ítem:
              numeroUuid, fechaEmision, nombreEmisor, nombreReceptor,
              idReceptor, tipoDte, granTotal, moneda,
              estado (V=Vigente, A=Anulado), fechaAnulacion.

        Requiere haber llamado iniciar_sesion_consulta() previamente.
        """
        if not self.authtoken:
            raise Exception("authtoken no disponible — llame a iniciar_sesion_consulta primero")

        # FIX Mayo 2026: SAT agregó dos parámetros nuevos ('impuesto' y 'resultado')
        # y cambió el header de autenticación de 'authtoken' a 'authorization'.
        # Mantenemos compatibilidad: si la primera variante falla con 401,
        # probamos la legacy automáticamente.
        params = {
            "usuario":              nit_usuario,
            "tipoOperacion":        tipo_operacion,
            "fechaEmisionIni":      fecha_ini,
            "fechaEmisionFinal":    fecha_fin,
            "tipoDte":              filtros.get("tipoDte", ""),
            "establecimiento":      filtros.get("establecimiento", ""),
            "noAutorizacion":       filtros.get("noAutorizacion", ""),
            "nitIdReceptor":        filtros.get("nitIdReceptor", ""),
            "estadoDte":            filtros.get("estadoDte", ""),
            "serie":                filtros.get("serie", ""),
            "numero":               filtros.get("numero", ""),
            "moneda":               filtros.get("moneda", ""),
            "montoTotalRangoIni":   filtros.get("montoTotalRangoIni", ""),
            "montoTotalRangoFinal": filtros.get("montoTotalRangoFinal", ""),
            "impuesto":             filtros.get("impuesto", ""),
            "nitCertificador":      filtros.get("nitCertificador", ""),
            "resultado":            filtros.get("resultado", ""),
        }

        consulta_endpoint = "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/consulta-dte"
        common_headers = {
            "accept":          "application/json, text/plain, */*",
            "accept-language": "es-419,es;q=0.9",
        }
        if self.consulta_url:
            common_headers["referer"] = self.consulta_url

        # v4: si el cliente adaptive está activo, lo usamos. Aplica:
        #   - header rotation (authorization ↔ authtoken)
        #   - param discovery (auto-add si SAT pide uno nuevo)
        #   - header discovery (auto-add Origin/Referer si SAT lo exige)
        # y loggea cada heal verbose en `.sat_heal_log.jsonl`.
        if self._adaptive is not None:
            resp = self._adaptive.get(
                consulta_endpoint,
                params=params,
                headers=common_headers,
                authtoken=self.authtoken,
                timeout=30,
            )
        else:
            # Fallback no-adaptive (legacy): manual rotation
            resp = self.session.get(
                consulta_endpoint, params=params,
                headers={**common_headers, "authorization": self.authtoken},
            )
            if resp.status_code == 401:
                print("[~] consulta-dte 401 con 'authorization', probando legacy 'authtoken'...")
                resp = self.session.get(
                    consulta_endpoint, params=params,
                    headers={**common_headers, "authtoken": self.authtoken},
                )
        print(f"[debug] consultar_dte ({resp.status_code}): {resp.text[:600]}")

        try:
            data = resp.json()
        except Exception:
            raise Exception(f"consultar_dte no-JSON ({resp.status_code}): {resp.text[:400]}")

        detalle = data.get("detalle", {})
        if isinstance(detalle, dict):
            return detalle.get("data", [])
        if isinstance(detalle, list):
            return detalle
        return []

    def descargar_dte(
        self,
        dtes: list,
        formato: str = "pdf",
        ruta_salida: str = None,
        nit_usuario: str = None,
        tipo_operacion: str = "E",
        fecha_ini: str = "",
        fecha_fin: str = "",
        **filtros,
    ) -> bytes:
        """
        Descarga DTEs como ZIP (PDF o XML) o como Excel.

        Args:
            dtes:           Lista de objetos DTE completos devueltos por consultar_dte().
            formato:        "pdf"  → ZIP con archivos PDF  (.zip)
                            "xml"  → ZIP con archivos XML  (.zip)
                            "xls"  → Archivo Excel         (.xls)
            ruta_salida:    Si se especifica, guarda el binario en ese path.
            nit_usuario:    NIT del usuario. Se infiere de los DTEs si no se especifica.
            tipo_operacion: "E" (Emitidos) o "R" (Recibidos). Default "E".
            fecha_ini:      Fecha inicio en formato dd-MM-yyyy (mismo que en consultar_dte).
            fecha_fin:      Fecha fin en formato dd-MM-yyyy.
            **filtros:      Filtros adicionales opcionales (tipoDte, estadoDte, etc.).

        Returns:
            bytes con el contenido del archivo descargado.

        Ejemplo:
            dtes = api.consultar_dte("<NIT>", "E", "01-03-2026", "31-03-2026")
            api.descargar_dte(dtes, "pdf", "facturas.zip", tipo_operacion="E",
                              fecha_ini="01-03-2026", fecha_fin="31-03-2026")
        """
        import base64 as _b64
        import zipfile as _zf
        import io as _io

        if not self.authtoken:
            raise Exception("authtoken no disponible — llame a iniciar_sesion_consulta primero")
        if not dtes:
            raise Exception("Lista de DTEs vacía")

        fmt = formato.lower()
        if fmt not in ("pdf", "xml", "xls"):
            raise Exception(f"Formato '{formato}' no válido. Use: pdf, xml, xls")

        if nit_usuario is None:
            nit_usuario = dtes[0].get("nitEmisor") or dtes[0].get("nitReceptor", "")

        base_url   = "https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/consulta-dte"
        # FIX Mayo 2026: header 'authorization' + params nuevos 'impuesto' y 'resultado'.
        auth_hdr   = {"authorization": self.authtoken}
        query_params = {
            "usuario":              nit_usuario,
            "tipoOperacion":        tipo_operacion,
            "fechaEmisionIni":      fecha_ini,
            "fechaEmisionFinal":    fecha_fin,
            "tipoDte":              filtros.get("tipoDte", ""),
            "establecimiento":      filtros.get("establecimiento", ""),
            "noAutorizacion":       filtros.get("noAutorizacion", ""),
            "nitIdReceptor":        filtros.get("nitIdReceptor", ""),
            "estadoDte":            filtros.get("estadoDte", ""),
            "serie":                filtros.get("serie", ""),
            "numero":               filtros.get("numero", ""),
            "moneda":               filtros.get("moneda", ""),
            "montoTotalRangoIni":   filtros.get("montoTotalRangoIni", ""),
            "montoTotalRangoFinal": filtros.get("montoTotalRangoFinal", ""),
            "impuesto":             filtros.get("impuesto", ""),
            "nitCertificador":      filtros.get("nitCertificador", ""),
            "resultado":            filtros.get("resultado", ""),
        }
        json_hdr = {**auth_hdr, "content-type": "application/json;charset=utf-8", "accept": "*/*"}
        if self.consulta_url:
            json_hdr["referer"] = self.consulta_url

        if fmt in ("xls", "xml"):
            # XLS/XML: POST returns binary directly
            #   /xls  → Excel binary
            #   /zip-xml → ZIP of XMLs binary
            endpoint = "xls" if fmt == "xls" else "zip-xml"
            resp = self.session.post(
                f"{base_url}/{endpoint}",
                params=query_params, json=dtes, headers=json_hdr,
            )
            if resp.status_code != 200:
                raise Exception(f"descargar_dte ({fmt}) HTTP {resp.status_code}: {resp.text[:300]}")
            content = resp.content

        else:
            # PDF: two-step process via token (Cod)
            #   Step 1: POST /zip-pdfCod → [{uuid, clave}, ...]
            #   Step 2: for each token GET /codpdfbase with header clave → Base64 PDF
            resp_cod = self.session.post(
                f"{base_url}/zip-pdfCod",
                params=query_params, json=dtes, headers=json_hdr,
            )
            if resp_cod.status_code != 200:
                raise Exception(
                    f"descargar_dte (pdf) step1 HTTP {resp_cod.status_code}: {resp_cod.text[:300]}"
                )
            try:
                tokens = resp_cod.json()
            except Exception:
                raise Exception(
                    f"descargar_dte (pdf) step1 non-JSON: {resp_cod.text[:300]}"
                )

            # Step 2: fetch each PDF and build a ZIP in memory
            buf = _io.BytesIO()
            with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as zf:
                for tok in tokens:
                    uuid_tok = tok.get("uuid", "")
                    clave    = tok.get("clave", "")
                    resp_file = self.session.get(
                        f"{base_url}/codpdfbase",
                        headers={**auth_hdr, "clave": clave},
                    )
                    if resp_file.status_code != 200:
                        print(f"[!] {uuid_tok} → HTTP {resp_file.status_code}, omitido")
                        continue
                    file_bytes = _b64.b64decode(resp_file.content)
                    zf.writestr(f"{uuid_tok}.pdf", file_bytes)
                    print(f"[+] {uuid_tok}.pdf ({len(file_bytes):,} bytes)")
            content = buf.getvalue()

        if ruta_salida:
            import os
            os.makedirs(os.path.dirname(os.path.abspath(ruta_salida)), exist_ok=True) \
                if os.path.dirname(ruta_salida) else None
            with open(ruta_salida, "wb") as f:
                f.write(content)
            print(f"[+] Guardado en {ruta_salida} ({len(content):,} bytes)")
        return content

    def recuperar_por_uuid(
        self,
        uuid: str,
        nit_emisor: str,
        tipo_operacion: str = "E",
        formato: str = "xml",
        ruta_salida: str = None,
    ) -> bytes:
        """
        Recupera un DTE (XML, PDF o XLS) directamente por UUID sin conocer el
        rango de fechas.  Equivalente al RetornaXML / RetornaPDF de Megaprint.

        Internamente llama a consultar_dte(noAutorizacion=uuid) con rango amplio
        y luego descarga con descargar_dte.  Si no se encuentra como Emitido ("E")
        lo reintenta como Recibido ("R").

        Args:
            uuid:           UUID / Número de Autorización del DTE.
            nit_emisor:     NIT del emisor del DTE.
            tipo_operacion: "E" (Emitidos, default) o "R" (Recibidos).
            formato:        "xml" (default), "pdf" o "xls".
            ruta_salida:    Si se indica, guarda el archivo en ese path.

        Returns:
            bytes con el contenido descargado (ZIP para xml/pdf, Excel para xls).
        Raises:
            Exception si el DTE no se encuentra.
        """
        if not self.authtoken:
            raise Exception("authtoken no disponible — llame a iniciar_sesion_consulta primero")

        DATE_INI = "01-01-2020"
        DATE_FIN = "31-12-2030"

        dtes = self.consultar_dte(
            nit_emisor, tipo_operacion, DATE_INI, DATE_FIN,
            noAutorizacion=uuid,
        )

        # Si no se encontró como Emitido, reintentar como Recibido
        if not dtes and tipo_operacion == "E":
            print(f"[~] UUID no encontrado como Emitido, intentando como Recibido...")
            dtes = self.consultar_dte(
                nit_emisor, "R", DATE_INI, DATE_FIN,
                noAutorizacion=uuid,
            )
            tipo_operacion = "R"

        if not dtes:
            raise Exception(f"DTE con UUID {uuid} no encontrado para NIT {nit_emisor}")

        dte = dtes[0]
        nit_real  = dte.get("nitEmisor", nit_emisor)
        fecha_em  = dte.get("fechaEmision", "")

        # Acotar el rango a la fecha exacta de emisión (más eficiente)
        try:
            from datetime import datetime as _dt
            for fmt_in in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    fecha_dt = _dt.strptime(fecha_em.split("T")[0], fmt_in)
                    DATE_INI = fecha_dt.strftime("%d-%m-%Y")
                    DATE_FIN = fecha_dt.strftime("%d-%m-%Y")
                    break
                except ValueError:
                    continue
        except Exception:
            pass

        return self.descargar_dte(
            dtes, formato, ruta_salida,
            nit_usuario=nit_real,
            tipo_operacion=tipo_operacion,
            fecha_ini=DATE_INI,
            fecha_fin=DATE_FIN,
            noAutorizacion=uuid,
        )

    def _limpiar_documento(self, doc):
        """Removes empty nodes that cause XSD validation errors."""
        if "SAT" in doc and "DTE" in doc["SAT"] and "DatosEmision" in doc["SAT"]["DTE"]:
            emision = doc["SAT"]["DTE"]["DatosEmision"]
            
            # Clean items
            items = emision.get("Items", {}).get("Item", [])
            for item in items:
                if "Impuestos" in item and (not item["Impuestos"] or len(item["Impuestos"]) == 0):
                    del item["Impuestos"]
            
            # Clean totals
            if "Totales" in emision:
                totals = emision["Totales"]
                if "TotalImpuestos" in totals:
                    impuestos = totals["TotalImpuestos"].get("TotalImpuesto", [])
                    if not impuestos or len(impuestos) == 0:
                        del totals["TotalImpuestos"]
            
            # Clean complementos
            if "Complementos" in emision:
                comps = emision["Complementos"].get("Complemento", [])
                if not comps or len(comps) == 0:
                    del emision["Complementos"]
                    
        return doc

    def _encriptar_payload(self, content_str: str) -> str:
        """Replicates codificar.js AES Encrypt"""
        if not self.validacion:
            raise Exception("Falta llave de validacion (llame a iniciar_sesion_fel primero)")
            
        key_hash = SHA256.new(self.validacion.encode('utf-8')).hexdigest()
        hashed_key = bytes.fromhex(key_hash)
        iv = get_random_bytes(16)
        
        cipher = AES.new(hashed_key, AES.MODE_CBC, iv)
        padded_data = pad(content_str.encode('utf-8'), AES.block_size)
        encrypted = cipher.encrypt(padded_data)
        
        return base64.b64encode(iv + encrypted).decode('utf-8')

    def procesar_documento(self, gte_documento):
        """Processes the DTE without signing (equivalent to preview)."""
        gte_documento = self._limpiar_documento(gte_documento)
        json_data = json.dumps(gte_documento)
        encrypted_data = self._encriptar_payload(json_data)
        
        headers = {
            'Authorization': self.token,
            'pValidacion': self.validacion,
            'Content-Type': 'application/json' # Reverted
        }
        
        url = f"{self.api_rest_url}/publico/procesarDocumento"
        resp = self.session.post(url, json=encrypted_data, headers=headers)
        
        try:
            return resp.json()
        except:
            print(f"[!] Server returned non-JSON processing: {resp.status_code}")
            print(resp.text)
            return {}

    def certificar_dte(self, gte_documento, password: str, request_id: str = None):
        """
        Encrypts the DTE JSON and calls firmarDocumento.  Returns XML Document.

        Args:
            gte_documento: Dict con la estructura GTE del DTE.
            password:      Contraseña de firma electrónica.
            request_id:    Clave de idempotencia opcional.  Si se suministra y ya
                           existe una respuesta para este request_id en la sesión,
                           se devuelve el resultado cacheado sin volver a certificar.
                           Útil para reintentos seguros.
        """
        # Deduplicación: evita emitir el mismo DTE dos veces
        if request_id and request_id in self._dedup_cache:
            print(f"[+] Dedup hit: retornando resultado cacheado para request_id={request_id}")
            return self._dedup_cache[request_id]

        if not self.token or not self.validacion:
            raise Exception("No ha iniciado sesión en FEL API (token/validacion missing)")

        gte_documento = self._limpiar_documento(gte_documento)

        # SAT FEL requiere llamar procesarDocumento ANTES de firmarDocumento.
        # El servidor establece estado de sesión en el paso de procesarDocumento;
        # sin este paso previo, firmarDocumento solo valida la estructura (no firma).
        pre = self.procesar_documento(gte_documento)
        pre_detalle = pre.get("detalle", [{}])
        pre_primer = pre_detalle[0] if isinstance(pre_detalle, list) and pre_detalle else {}
        # procesarDocumento puede fallar de dos formas: con error=True (bool) o con
        # codigoError="ERROR" SIN el bool. Si no lo detectamos, el código seguía a
        # firmarDocumento, que sin un procesarDocumento exitoso SOLO valida la
        # estructura (no firma) → devuelve estadoHttp 200 pero sin numeroAutorizacion
        # → KeyError. Devolvemos aquí el error REAL de procesarDocumento.
        if pre_primer.get("error", False) or pre_primer.get("codigoError") == "ERROR":
            return pre

        encrypted_data = self._encriptar_payload(json.dumps(gte_documento))
        encrypted_password = self._encriptar_payload(password)

        # As per the JS reverse-engineering
        headers = {
            'Authorization': self.token,
            'pValidacion': self.validacion,
            'pCadena': encrypted_password,
            'Content-Type': 'application/json;charset=utf-8',
            'Accept': 'application/json;charset=utf-8'
        }

        url = f"{self.api_rest_url}/publico/firmarDocumento"
        resp = self.session.post(url, json=encrypted_data, headers=headers)

        try:
            result = resp.json()
        except:
            print(f"[!] Server returned non-JSON: {resp.status_code}")
            print(resp.text)
            return {}

        # Guardar en caché solo si fue exitoso (evita cachear errores)
        detalle = result.get("detalle", [{}])
        primer = detalle[0] if isinstance(detalle, list) and detalle else {}
        if request_id and not primer.get("error", True):
            self._dedup_cache[request_id] = result
            print(f"[+] Resultado cacheado con request_id={request_id}")

        return result
        
    def descargar_pdf(self, nit_receptor, uuid):
        """Downloads the generated PDF for a given UUID."""
        if not self.token:
            raise Exception("No ha iniciado sesión en FEL API")
            
        headers = {
            'Authorization': self.token,
            'pReceptor': nit_receptor,
            'pUuid': uuid,
            'Content-Type': 'application/json;charset=utf-8',
            'Accept': 'application/json;charset=utf-8'
        }
        
        url = f"{self.api_rest_url}/publico/descargapdf/"
        resp = self.session.post(url, headers=headers)
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    # SAT returns PDF as Base64 in data[0]
                    return base64.b64decode(data[0])
                elif isinstance(data, dict) and "data" in data and len(data["data"]) > 0:
                    return base64.b64decode(data["data"][0])
                else:
                    print(f"[-] Unexpected PDF response format: {data}")
                    return None
            except Exception as e:
                print(f"[-] Failed to parse PDF JSON: {e}")
                print(f"[DEBUG] Raw PDF Response: {resp.text[:200]}")
                return None
        else:
            print(f"[!] PDF Download Error: {resp.status_code} - {resp.text}")
            return None
    def build_tax_node(self, amount, regime="GRAVABLE", **kwargs):
        """
        Builds the Impuestos list for an Item based on tax regime.

        regime values:
          GRAVABLE / GENERAL  → IVA 12% incluido en precio (CodigoUnidadGravable=1)
          EXENTO / NO_AFECTO / EXPORT / IVA_CERO
                              → IVA 0%, monto exento (CodigoUnidadGravable=2)
          PEQ                 → Sin nodo de impuesto (Pequeño Contribuyente)
          TURISMO_PASAJES     → Impuesto "TURISMO PASAJES"
          TURISMO_HOSPEDAJE   → Impuesto "TURISMO HOSPEDAJE"
          PETROLEO            → Impuesto "PETROLEO"
          BOMBEROS            → Impuesto "BOMBEROS"
          TIMBRE_PRENSA       → Impuesto "TIMBRE DE PRENSA"
          TASA_MUNICIPAL      → Impuesto "TASA MUNICIPAL"

        Para impuestos especiales (TURISMO_*, PETROLEO, etc.) se puede pasar:
          monto_impuesto     → monto del impuesto directamente
          monto_gravable     → base gravable (si difiere del amount)
          codigo_unidad      → CodigoUnidadGravable (default 1)
          cantidad_unidades  → CantidadUnidadesGravables (opcional, para PETROLEO etc.)
        """
        if regime == "PEQ":
            return []

        # ── Turismo: Hospedaje (INGUAT) — incluido en el precio, como el IVA ──
        # Catálogo SAT catalogoUnidadesGravables-0.1.4: "TURISMO HOSPEDAJE",
        # operaSobreCasilla=MontoGravable, código 1=Tasa 10% / 2=Exento (factor 0).
        # En Guatemala el hospedaje de hotel lleva IVA 12% + INGUAT 10% (base = total/1.22).
        if regime in ("HOSPEDAJE", "HOSPEDAJE_IVA"):
            # TURISMO HOSPEDAJE (INGUAT 10%) es un impuesto SUMABLE: su MontoImpuesto
            # se AÑADE al Total de la línea (FEL_RCP348), NO va incluido en el precio.
            # El IVA, en cambio, SÍ va incluido en el precio (no se suma).
            if regime == "HOSPEDAJE_IVA":
                base = round(amount / 1.12, 2)   # el precio típico ya trae IVA incluido
                return [
                    {"NombreCorto": "IVA", "CodigoUnidadGravable": 1,
                     "MontoGravable": base, "MontoImpuesto": round(amount - base, 2)},
                    {"NombreCorto": "TURISMO HOSPEDAJE", "CodigoUnidadGravable": 1,
                     "MontoGravable": base, "MontoImpuesto": round(base * 0.10, 2)},
                ]
            # Solo hospedaje (sin IVA): el precio es la base; el 10% se suma encima.
            base = round(amount, 2)
            return [{"NombreCorto": "TURISMO HOSPEDAJE", "CodigoUnidadGravable": 1,
                     "MontoGravable": base, "MontoImpuesto": round(base * 0.10, 2)}]

        # ── Turismo: Pasajes — tasa de salida fija por pasajero, se SUMA al total ──
        # operaSobreCasilla=CantidadUnidadesGravables. factor: aérea USD30 / marítima USD10
        # / aérea exenta 0. La cantidad de pasajeros viene en kwargs["cantidad"].
        _PASAJES = {"PASAJES_AEREA": (1, 30.0), "PASAJES_MARITIMA": (2, 10.0), "PASAJES_EXENTA": (3, 0.0)}
        if regime in _PASAJES:
            cod, factor = _PASAJES[regime]
            cant = int(kwargs.get("cantidad", 1) or 1)
            return [{"NombreCorto": "TURISMO PASAJES", "CodigoUnidadGravable": cod,
                     "CantidadUnidadesGravables": cant, "MontoImpuesto": round(factor * cant, 2)}]

        if regime in ["EXENTO", "EXPORT", "IVA_CERO", "NO_AFECTO"]:
            return [{
                "NombreCorto": "IVA",
                "CodigoUnidadGravable": 2,
                "MontoGravable": round(amount, 2),
                "MontoImpuesto": 0.00
            }]

        # ── Impuestos especiales ──────────────────────────────────────────────
        _SPECIAL = {
            "TURISMO_PASAJES":   "TURISMO PASAJES",
            "TURISMO_HOSPEDAJE": "TURISMO HOSPEDAJE",
            "PETROLEO":          "PETROLEO",
            "BOMBEROS":          "BOMBEROS",
            "TIMBRE_PRENSA":     "TIMBRE DE PRENSA",
            "TASA_MUNICIPAL":    "TASA MUNICIPAL",
        }
        if regime in _SPECIAL:
            nodo = {
                "NombreCorto":         _SPECIAL[regime],
                "CodigoUnidadGravable": kwargs.get("codigo_unidad", 1),
                "MontoImpuesto":        round(kwargs.get("monto_impuesto", 0.0), 2),
            }
            if "monto_gravable" in kwargs:
                nodo["MontoGravable"] = round(kwargs["monto_gravable"], 2)
            if "cantidad_unidades" in kwargs:
                nodo["CantidadUnidadesGravables"] = kwargs["cantidad_unidades"]
            return [nodo]

        # ── IVA estándar régimen general (12% incluido) ───────────────────────
        monto_gravable = round(amount / 1.12, 2)
        monto_impuesto = round(amount - monto_gravable, 2)
        return [{
            "NombreCorto":         "IVA",
            "CodigoUnidadGravable": 1,
            "MontoGravable":        monto_gravable,
            "MontoImpuesto":        monto_impuesto,
        }]

    def build_frase_node(self, regimes=None):
        """
        Builds Frases node from a list of regime keys.

        Keys:
          PEQ              → Tipo 3, Escenario 1  (Pequeño Contribuyente)
          GENERAL          → Tipo 1, Escenario 1  (Régimen general)
          EXPORT           → Tipo 4, Escenario 1  (Exportación)
          EXENTO_EDUCACION → Tipo 4, Escenario 8
          AGENCIA_VIAJES   → Tipo 4, Escenario 24 (Servicios no afectos turismo)
          FESP             → Tipo 2, Escenario 1  (Factura Especial)
          FESP_AGRICOLA    → Tipo 2, Escenario 2
          TURISMO_PASAJES  → Tipo 4, Escenario 14 (pasajes internacionales)
          TURISMO_HOSPEDAJE→ Tipo 4, Escenario 6
          COMBUSTIBLE      → Tipo 5, Escenario 1
        """
        if regimes is None:
            regimes = ["PEQ"]
        mapping = {
            "PEQ":               {"tipo": 3, "escenario": 1},
            "GENERAL":           {"tipo": 1, "escenario": 1},
            "EXPORT_GEN":        {"tipo": 1, "escenario": 2},
            "EXPORT":            {"tipo": 4, "escenario": 1},
            "EXENTO_EDUCACION":  {"tipo": 4, "escenario": 8},
            "AGENCIA_VIAJES":    {"tipo": 4, "escenario": 24},
            "FESP":              {"tipo": 2, "escenario": 1},
            "FESP_AGRICOLA":     {"tipo": 2, "escenario": 2},
            "TURISMO_PASAJES":   {"tipo": 4, "escenario": 14},
            "TURISMO_HOSPEDAJE": {"tipo": 4, "escenario": 6},
            "COMBUSTIBLE":       {"tipo": 5, "escenario": 1},
        }
        return {"Frase": [mapping[r] for r in regimes if r in mapping]}

    def build_complemento_node(self, tipo="NCRE", data=None):
        """
        Builds the Complementos node for the DTE JSON.

        tipo values and required data keys:
          NCRE / NDEB      → uuid_origen, fecha_origen (yyyy-MM-dd), motivo (optional)
          CAMBIARIA        → abonos: [{fecha: "yyyy-MM-dd", monto: float}, ...]
          FESP             → retencion_isr, total_menos_retenciones,
                             retencion_iva (optional)
          EXPORTACION      → nombre_consignatario, direccion_consignatario,
                             incoterm (EXW|FCA|FAS|FOB|CFR|CIF|CPT|CIP|DDP|DAP|DAT|ZZZ),
                             nombre_comprador (opt), direccion_comprador (opt),
                             otra_referencia (opt), nombre_exportador (opt)
        """
        if data is None:
            data = {}

        if tipo in ("NCRE", "NDEB"):
            return {
                "Complemento": [{
                    "IDComplemento": "NOTAS",
                    "NombreComplemento": "ReferenciaNotas",
                    "URIComplemento": "http://www.sat.gob.gt/face2/ComplementoReferenciaNota/0.1.0",
                    "ReferenciasNota": {
                        "version": "1",
                        "NumeroAutorizacionDocumentoOrigen": data.get("uuid_origen", ""),
                        "FechaEmisionDocumentoOrigen":       data.get("fecha_origen", ""),
                        "MotivoAjuste":                      data.get("motivo", "Ajuste"),
                    }
                }]
            }

        if tipo == "CAMBIARIA":
            abonos = []
            for i, abono in enumerate(data.get("abonos", []), start=1):
                abonos.append({
                    "NumeroAbono":     i,
                    "FechaVencimiento": abono.get("fecha"),
                    "MontoAbono":       round(abono.get("monto", 0), 2),
                })
            return {
                "Complemento": [{
                    "IDComplemento":  "1",
                    "NombreComplemento": "Abono",
                    "URIComplemento": "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0",
                    "AbonosFacturaCambiaria": {
                        "xmlns:cfc": "http://www.sat.gob.gt/dte/fel/CompCambiaria/0.1.0",
                        "Version": "1",
                        "Abono":   abonos,
                    }
                }]
            }

        if tipo == "FESP":
            nodo = {
                "retencionISR":          round(data.get("retencion_isr", 0.0), 2),
                "totalMenosRetenciones": round(data.get("total_menos_retenciones", 0.0), 2),
            }
            if "retencion_iva" in data:
                nodo["retencionIVA"] = round(data["retencion_iva"], 2)
            return {
                "Complemento": [{
                    "IDComplemento":  "FESP",
                    "NombreComplemento": "RetencionesFacturaEspecial",
                    "URIComplemento": "http://www.sat.gob.gt/face2/ComplementoFacturaEspecial/0.1.0",
                    "Retenciones": {
                        "version": 1,
                        **nodo,
                    }
                }]
            }

        if tipo == "EXPORTACION":
            exp = {
                "NombreConsignatarioODestinatario":   data.get("nombre_consignatario", ""),
                "DireccionConsignatarioODestinatario": data.get("direccion_consignatario", ""),
                "incoterm":                            data.get("incoterm", "FOB"),
            }
            for k_in, k_out in [
                ("nombre_comprador",    "NombreComprador"),
                ("direccion_comprador", "DireccionComprador"),
                ("otra_referencia",     "OtraReferencia"),
                ("nombre_exportador",   "NombreExportador"),
                ("codigo_exportador",   "CodigoExportador"),
            ]:
                if data.get(k_in):
                    exp[k_out] = data[k_in]
            return {
                "Complemento": [{
                    "IDComplemento":  "EXP",
                    "NombreComplemento": "Exportacion",
                    "URIComplemento": "http://www.sat.gob.gt/face2/ComplementoExportaciones/0.1.0",
                    "Exportacion": {
                        "version": "1",
                        **exp,
                    }
                }]
            }

        return {}

    def consultar_receptor(self, nit: str) -> dict:
        """
        Consulta nombre y estado de un NIT en el RTU de la SAT.

        Descubierto via DevTools en el portal FEL:
        - POST /publico/consultaRecep  (body vacío; NIT encriptado en header pCadena)
        - GET  /publico/consultaFallecido/{nit}

        Requiere sesión FEL activa (token + validacion).

        Retorna dict con al menos: nombre, respuestaNit (bool), omiso, fallecido.
        """
        if not self.token or not self.validacion:
            raise Exception("Sesión FEL no iniciada — llame a iniciar_sesion_fel primero")

        nit_clean = nit.strip()
        encrypted_nit = self._encriptar_payload(nit_clean)

        headers = {
            'Authorization': self.token,
            'pValidacion': self.validacion,
            'pCadena': encrypted_nit,
            'Content-Type': 'application/json;charset=utf-8',
            'Accept': 'application/json;charset=utf-8',
        }

        # POST con body vacío — el NIT viaja encriptado en pCadena
        url_recep = f"{self.api_rest_url}/publico/consultaRecep"
        resp = self.session.post(url_recep, headers=headers)

        try:
            data = resp.json()
        except Exception:
            return {"error": f"Respuesta no JSON ({resp.status_code}): {resp.text[:200]}"}

        # Verificación secundaria: ¿está registrado como fallecido?
        fallecido = False
        try:
            url_fall = f"{self.api_rest_url}/publico/consultaFallecido/{nit_clean}"
            resp_fall = self.session.get(url_fall, headers={
                'Authorization': self.token,
                'pValidacion': self.validacion,
                'Accept': 'application/json;charset=utf-8',
            })
            if resp_fall.status_code == 200:
                data_fall = resp_fall.json()
                # El campo puede ser 'fallecido', 'resultado', o similar
                fallecido = bool(
                    data_fall.get('fallecido')
                    or data_fall.get('resultado')
                    or data_fall.get('esFallecido')
                )
        except Exception:
            pass

        data['fallecido'] = fallecido
        return data

    # ─── Session persistence ──────────────────────────────────────────────────

    def save_session(self, filepath: str) -> None:
        """
        Persiste la sesión activa en disco (JSON).
        Incluye cookies, token, validacion y metadatos necesarios para restaurarla.
        El archivo sobrevive reinicios del script.
        """
        import time as _time
        data = {
            'saved_at':      _time.time(),
            'token':         self.token,
            'validacion':    self.validacion,
            'api_rest_url':  getattr(self, 'api_rest_url', ''),
            'fel_url':       getattr(self, 'fel_url', ''),
            'nit_certificador': getattr(self, 'nit_certificador', ''),
            'authtoken':     getattr(self, 'authtoken', None),
            'consulta_url':  getattr(self, 'consulta_url', None),
            'cookies':       [
                {'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path}
                for c in self.session.cookies
            ],
        }
        import os
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True) if os.path.dirname(filepath) else None
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        print(f"[+] Sesión guardada en {filepath}")

    def load_session(self, filepath: str) -> bool:
        """
        Carga sesión desde disco y verifica que sigue activa con un ping liviano.
        Retorna True si la sesión fue restaurada y está válida, False en caso contrario.
        """
        import os, time as _time
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Rechazar sesiones guardadas hace más de 25 minutos sin verificar
            age = _time.time() - data.get('saved_at', 0)
            if age > 1500:  # 25 min — token SAT suele expirar ~30 min
                print(f"[~] Caché expirado ({age/60:.0f} min). Se hará login nuevo.")
                return False

            self.token            = data['token']
            self.validacion       = data['validacion']
            self.api_rest_url     = data.get('api_rest_url', f"{self.fel_base_url}/fel-rest/rest")
            self.fel_url          = data.get('fel_url', '')
            self.nit_certificador = data.get('nit_certificador', '')
            self.authtoken        = data.get('authtoken')
            self.consulta_url     = data.get('consulta_url')
            raw_cookies = data.get('cookies', {})
            if isinstance(raw_cookies, list):
                for c in raw_cookies:
                    self.session.cookies.set(c['name'], c['value'], domain=c.get('domain'), path=c.get('path'))
            else:
                self.session.cookies.update(raw_cookies)

            # Ping liviano: consultar CF (siempre da 422 pero confirma que el token es válido)
            headers = {
                'Authorization': self.token,
                'pValidacion':   self.validacion,
                'pCadena':       self._encriptar_payload('CF'),
                'Accept':        'application/json;charset=utf-8',
            }
            resp = self.session.post(
                f"{self.api_rest_url}/publico/consultaRecep",
                headers=headers
            )
            if resp.status_code in (200, 422):
                print(f"[+] Sesión restaurada desde caché ({age/60:.1f} min de antigüedad).")
                return True
            print(f"[~] Sesión en caché inválida (status {resp.status_code}). Re-login.")
            return False
        except Exception as e:
            print(f"[~] No se pudo cargar caché: {e}")
            return False

    def _consulta_referencia(self, numero_autorizacion: str, nit_emisor: str, id_receptor: str) -> dict:
        """GET consultaReferencia: obtiene datos del DTE (estado, fechaEmisionFormato, etc.).

        Reintenta 2 veces ante 502/503/504 (transient SAT outages).
        """
        import time as _time
        import requests as _rq
        last_status = None
        for attempt in range(3):
            try:
                resp = self.session.get(
                    f"{self.api_rest_url}/publico/consultaReferencia",
                    headers={
                        'Authorization': self.token,
                        'NitEmisor':     nit_emisor,
                        'pReceptor':     id_receptor,
                        'pUuid':         numero_autorizacion,
                        'Accept':        'application/json;charset=utf-8',
                    },
                    timeout=35,
                )
            except (_rq.exceptions.Timeout, _rq.exceptions.ConnectionError) as e:
                # SAT (felav02) a veces tarda/corta la conexión. Reintentar en vez
                # de propagar la excepción (que abortaría toda la anulación).
                print(f"[~] consultaReferencia timeout/conexión (intento {attempt+1}/3): {e}")
                if attempt < 2:
                    _time.sleep(3 * (attempt + 1))
                    continue
                return {"_http_status": 0, "_raw": f"timeout: {e}"}
            last_status = resp.status_code
            if resp.status_code in (502, 503, 504) and attempt < 2:
                print(f"[~] consultaReferencia {resp.status_code}, reintentando ({attempt+1}/2)...")
                _time.sleep(3 * (attempt + 1))
                continue
            try:
                data = resp.json()
            except Exception:
                return {"_http_status": resp.status_code, "_raw": resp.text[:300]}
            data["_http_status"] = resp.status_code
            return data
        return {"_http_status": last_status, "_raw": "max retries"}

    # Códigos de estado de DTE en consultaReferencia/consultar_dte:
    #   "V" = Vigente (no anulado)
    #   "I" = Anulado (Inactivo) ← este es el código real, NO "A" como
    #         se documentaba antes en la API
    #   ""  = desconocido / no se pudo determinar
    DTE_ESTADO_ANULADO = "I"
    DTE_ESTADO_VIGENTE = "V"

    def _estado_dte(self, numero_autorizacion: str, nit_emisor: str, id_receptor: str) -> str:
        """Devuelve 'V' (vigente), 'I' (anulado), o '' si no se puede determinar."""
        data = self._consulta_referencia(numero_autorizacion, nit_emisor, id_receptor)
        detalle = data.get("detalle", [{}])
        if isinstance(detalle, list) and detalle:
            est = detalle[0].get("estado", "") or detalle[0].get("estadoDte", "")
            return est
        return data.get("estadoDte", "")

    def _is_anulado(self, numero_autorizacion: str, nit_emisor: str, id_receptor: str) -> bool:
        return self._estado_dte(numero_autorizacion, nit_emisor, id_receptor) == self.DTE_ESTADO_ANULADO

    def _receptor_de_dte_emitido(self, numero_autorizacion: str, nit_emisor: str):
        """Busca un DTE EMITIDO por su UUID y devuelve el idReceptor REAL.

        consultaReferencia exige el receptor exacto del DTE; si el id_receptor
        guardado no coincide (p.ej. la factura se emitió a otro NIT), falla. Acá
        usamos el módulo de consulta (authtoken) para hallar el DTE por UUID en los
        últimos ~120 días y devolver su receptor real. Devuelve None si no se halla.
        """
        if not getattr(self, "authtoken", None):
            return None
        import time as _t_r
        from datetime import datetime as _dt_r, timedelta as _td_r, timezone as _tz_r
        hoy = _dt_r.now(_tz_r(_td_r(hours=-6)))
        ini = (hoy - _td_r(days=60)).strftime("%d-%m-%Y")
        fin = hoy.strftime("%d-%m-%Y")
        uup = (numero_autorizacion or "").upper()
        # consultar_dte a veces devuelve un error transitorio de SAT
        # ("Ocurrió un error realizando la consulta, intente nuevamente más tarde",
        # detalle=null → lista vacía). Reintentamos con backoff.
        for attempt in range(4):
            try:
                dtes = self.consultar_dte(nit_emisor, "E", ini, fin, noAutorizacion=numero_autorizacion)
            except Exception as e:
                print(f"[debug] consultar_dte (buscar receptor) intento {attempt + 1} excepción: {e}")
                dtes = []
            dtes = dtes or []
            for d in dtes:
                if str(d.get("numeroUuid") or d.get("uuid") or "").upper() == uup:
                    return d.get("idReceptor") or d.get("nitReceptor")
            # Si SAT ignoró el filtro pero solo hay un resultado, usarlo.
            if len(dtes) == 1:
                return dtes[0].get("idReceptor") or dtes[0].get("nitReceptor")
            if attempt < 3:
                print(f"[debug] consultar_dte vacío/transitorio (intento {attempt + 1}/4), reintentando…")
                _t_r.sleep(3)
        return None

    # Variantes de headers/payload para anulación. SAT ha rotado el formato
    # entre versiones — el cliente intenta primero la variante actual y si
    # la anulación no se propaga, reintenta con la legacy.
    _ANULAR_VARIANTES = [
        {  # Variante 1: actual (Mayo 2026+)
            "nombre":         "nueva (Origin+Referer, fechaUTC)",
            "use_origin_ref": True,
            "fecha_utc":      True,
        },
        {  # Variante 2: legacy (pre-Mayo 2026)
            "nombre":         "legacy (sin Origin/Referer, fecha local)",
            "use_origin_ref": False,
            "fecha_utc":      False,
        },
    ]

    def anular_dte(
        self,
        password: str,
        numero_autorizacion: str,
        nit_emisor: str,
        id_receptor: str,
        motivo: str = "Error en los datos de la descripción",
        fecha_emision: str = None,
    ) -> dict:
        """
        Anula un DTE ya certificado por la SAT, con fallback automático
        entre el formato actual (Mayo 2026) y el legacy.

        Args:
            password:            Contraseña de firma electrónica.
            numero_autorizacion: UUID del DTE a anular.
            nit_emisor:          NIT del emisor.
            id_receptor:         IDReceptor (NIT o "CF").
            motivo:              Texto del motivo (catálogo SAT).
            fecha_emision:       Fallback si consultaReferencia no devuelve fechaEmisionFormato.

        Returns:
            dict con resultado.
              Éxito:  {"resultado": "OK", "verificado": True, "variante": "...", ...}
              Error:  {"error": "...", "intentos": [...]}
        """
        if not self.token or not self.validacion:
            raise Exception("Sesión FEL no iniciada — llame a iniciar_sesion_fel primero")

        # Si ya está anulado, terminamos
        if self._is_anulado(numero_autorizacion, nit_emisor, id_receptor):
            return {"resultado": "OK", "verificado": True, "ya_anulado": True}

        # Obtener fechaEmisionFormato vía consultaReferencia. OJO: consultaReferencia
        # EXIGE que el id_receptor coincida EXACTO con el receptor del DTE; si no,
        # devuelve codigoError=ERROR + ConsultaConstancias vacío (no es timing).
        import time as _t_anular

        def _extraer_fecha(dref):
            fe = dref.get("fechaEmisionFormato")
            if not fe:
                det = dref.get("detalle", [{}])
                if isinstance(det, list) and det:
                    fe = det[0].get("fechaEmisionFormato") or det[0].get("fechaEmision")
            return fe

        # 1) Intento con el receptor dado (un reintento corto por si SAT aún no indexó).
        fecha_em = None
        data_ref = {}
        for _try in range(2):
            data_ref = self._consulta_referencia(numero_autorizacion, nit_emisor, id_receptor)
            fecha_em = _extraer_fecha(data_ref)
            if fecha_em:
                break
            if _try < 1:
                print("[debug] consultaReferencia vacío, reintentando una vez…")
                _t_anular.sleep(3)

        # 2) Si sigue vacío, casi seguro el id_receptor NO coincide con el del DTE
        #    (p.ej. factura emitida a otro NIT). Buscamos el DTE por UUID en los
        #    emitidos para sacar el receptor REAL y reintentamos con ese.
        if not fecha_em:
            real_rcpt = None
            try:
                real_rcpt = self._receptor_de_dte_emitido(numero_autorizacion, nit_emisor)
            except Exception as e:
                print(f"[debug] no se pudo buscar el receptor real por UUID: {e}")
            if real_rcpt and str(real_rcpt) != str(id_receptor):
                print(f"[debug] receptor real del DTE = {real_rcpt} (≠ {id_receptor}); reintentando consultaReferencia")
                id_receptor = str(real_rcpt)
                data_ref = self._consulta_referencia(numero_autorizacion, nit_emisor, id_receptor)
                fecha_em = _extraer_fecha(data_ref)

        # 3) Último recurso: fecha_emision provista por el cliente.
        fecha_em = fecha_em or fecha_emision
        print(f"[debug] anular_dte → id_receptor={id_receptor}, fechaEmision={fecha_em}")
        if not fecha_em:
            raise Exception(
                "No se pudo obtener la fecha de emisión del DTE para anular. "
                "Verificá que el NIT del receptor sea el correcto. "
                f"Respuesta SAT: {json.dumps(data_ref)[:300]}"
            )

        # Iterar variantes
        intentos = []
        for variant in self._ANULAR_VARIANTES:
            print(f"\n[*] Intentando anulación con variante: {variant['nombre']}")
            try:
                result = self._anular_intento(
                    password=password,
                    numero_autorizacion=numero_autorizacion,
                    nit_emisor=nit_emisor,
                    id_receptor=id_receptor,
                    motivo=motivo,
                    fecha_em=fecha_em,
                    variant=variant,
                )
                intentos.append({"variante": variant["nombre"], "result": result})

                # Verificar después: ¿quedó anulado? SAT usa "I" (Inactivo)
                # para anulado, NO "A" como sugerían viejos docs.
                import time as _time
                _time.sleep(2)
                estado = self._estado_dte(numero_autorizacion, nit_emisor, id_receptor)
                print(f"[+] Estado post-intento '{variant['nombre']}': {estado!r}")
                if estado == self.DTE_ESTADO_ANULADO:
                    return {
                        "resultado":  "OK",
                        "verificado": True,
                        "variante":   variant["nombre"],
                        "estado":     estado,
                        "intentos":   intentos,
                    }
                print(f"[~] Variante '{variant['nombre']}' completó pero estado={estado!r}")
            except Exception as e:
                print(f"[~] Variante '{variant['nombre']}' excepción: {e}")
                intentos.append({"variante": variant["nombre"], "error": str(e)})

        # Ninguna variante propagó la anulación — verificación final
        estado_final = self._estado_dte(numero_autorizacion, nit_emisor, id_receptor)
        return {
            "error":         f"Anulación no se propagó tras todas las variantes (estado actual={estado_final!r})",
            "estado_final":  estado_final,
            "intentos":      intentos,
        }

    def _anular_intento(
        self,
        password: str,
        numero_autorizacion: str,
        nit_emisor: str,
        id_receptor: str,
        motivo: str,
        fecha_em: str,
        variant: dict,
    ) -> dict:
        """Ejecuta los 3 POSTs de anulación con la configuración de un variant."""
        from datetime import datetime as _dt

        # fechaAnulacionForm según variante
        if variant["fecha_utc"]:
            fecha_anulacion = _dt.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        else:
            fecha_anulacion = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")

        # IMPORTANTE: el orden de las keys en anulacionDte sí importa para SAT
        # (afecta la canonicalización XML que se firma internamente).
        # Orden capturado del navegador: datosAnulacion → id → Certificacion.
        gt_anulacion = {
            "SAT": {
                "anulacionDte": {
                    "datosAnulacion": {
                        "id":                    "DatosAnulacion",
                        "numeroDocumentoAnular": numero_autorizacion,
                        "nitEmisor":             nit_emisor,
                        "idReceptor":            id_receptor,
                        "fechaEmision":          fecha_em,
                        "fechaAnulacionForm":    fecha_anulacion,
                        "observacion":           motivo,
                    },
                    "id": "DatosCertificados",
                    "Certificacion": {
                        "NITCertificador":        self.nit_certificador,
                        "NombreCertificador":     "Superintendencia de Administracion Tributaria",
                        "FechaHoraCertificacion": "2019-02-11T00:00:00-06:00",
                    },
                }
            },
            "Signature": {
                "SignedInfo": {
                    "CanonicalizationMethod": {},
                    "SignatureMethod":        {},
                    "Reference": {"DigestMethod": {}, "DigestValue": {}},
                },
                "SignatureValue": "",
            },
        }

        # Headers base según variante
        base = {
            'Authorization':   self.token,
            'pValidacion':     self.validacion,
            'Content-Type':    'application/json;charset=utf-8',
            'Accept':          'application/json;charset=utf-8',
            'Accept-Language': 'es-419,es;q=0.9',
        }
        if variant["use_origin_ref"]:
            base['Origin']  = 'https://felav.c.sat.gob.gt'
            base['Referer'] = 'https://felav.c.sat.gob.gt/'

        # Paso 1: validarDocumento
        r1 = self.session.post(
            f"{self.api_rest_url}/publico/validarDocumento",
            json=gt_anulacion, headers=base,
        )
        try:
            d1 = r1.json()
        except Exception:
            raise Exception(f"validarDocumento no-JSON ({r1.status_code}): {r1.text[:300]}")
        print(f"  [paso1 validarDocumento {r1.status_code}] {json.dumps(d1)[:200]}")
        if r1.status_code != 200:
            raise Exception(f"validarDocumento HTTP {r1.status_code}")

        # Paso 2: firmarDocumentoAnular
        encrypted_password = self._encriptar_payload(password)
        r2 = self.session.post(
            f"{self.api_rest_url}/publico/firmarDocumentoAnular",
            json=gt_anulacion, headers={**base, 'pCadena': encrypted_password},
        )
        try:
            d2 = r2.json()
        except Exception:
            raise Exception(f"firmarDocumentoAnular no-JSON ({r2.status_code}): {r2.text[:300]}")
        print(f"  [paso2 firmarDocumentoAnular {r2.status_code}] {json.dumps(d2)[:200]}")
        detalle2 = d2.get("detalle", [{}])[0]
        xml_firmado = detalle2.get("mensaje")
        if not xml_firmado or detalle2.get("error", True):
            raise Exception(f"firmarDocumentoAnular sin XML firmado: {json.dumps(d2)[:300]}")
        cod2 = detalle2.get("codigoError", "")
        OK_CODES = {"", "000", "FEL_RCP000", "FEL_GEN000"}
        if cod2 not in OK_CODES:
            raise Exception(f"firmarDocumentoAnular codigoError={cod2}")

        # Paso 3: anulacionDocumento (POST XML)
        r3 = self.session.post(
            f"{self.api_rest_url}/publico/anulacionDocumento",
            data=xml_firmado.encode('utf-8'),
            headers={**base, 'Content-Type': 'text/plain;charset=utf-8'},
        )
        try:
            d3 = r3.json()
        except Exception:
            raise Exception(f"anulacionDocumento no-JSON ({r3.status_code}): {r3.text[:300]}")
        print(f"  [paso3 anulacionDocumento {r3.status_code}] {json.dumps(d3)[:200]}")
        detalle3 = d3.get("detalle", [{}])[0]
        if r3.status_code != 200 or detalle3.get("error", True):
            raise Exception(f"anulacionDocumento error: {json.dumps(d3)[:300]}")

        return {
            "faseId": detalle3.get("faseId"),
            "raw":    d3,
        }

    def generate_totals(self, items):
        """
        Calculates GranTotal and TotalImpuestos automatically from a list of item nodes.
        Accepts both flat list impuestos and nested {"Impuesto": [...]} format.
        """
        gran_total = 0
        total_impuestos_map = {} # {NombreCorto: total_amount}

        for item in items:
            gran_total += item.get("Total", 0)
            impuestos_raw = item.get("Impuestos", [])
            # Handle both {"Impuesto": [...]} and flat list
            if isinstance(impuestos_raw, dict):
                impuestos = impuestos_raw.get("Impuesto", [])
            else:
                impuestos = impuestos_raw if isinstance(impuestos_raw, list) else []
            for imp in impuestos:
                nombre = imp.get("NombreCorto")
                monto = imp.get("MontoImpuesto", 0)
                total_impuestos_map[nombre] = total_impuestos_map.get(nombre, 0) + monto
        
        total_impuestos_list = []
        for nombre, monto in total_impuestos_map.items():
            total_impuestos_list.append({
                "NombreCorto": nombre,
                "TotalMontoImpuesto": round(monto, 2)
            })
            
        return {
            "TotalImpuestos": {"TotalImpuesto": total_impuestos_list},
            "GranTotal": round(gran_total, 2)
        }

# Test if it runs correctly (no credentials)
if __name__ == "__main__":
    api = SatAPI()
    print("API Wrapper successfully loaded")


# ---------------------------------------------------------------------------
# Adenda — post-certification XML injection
# ---------------------------------------------------------------------------

def inject_adenda(xml_str: str, adenda: dict) -> str:
    """
    Injects a <dte:Adenda> block into a SAT-certified XML string.

    SAT's XmlDSig signature only covers <DatosEmision ID="DatosEmision">.
    Adding <dte:Adenda> inside <dte:SAT> but outside <dte:DTE> does NOT
    invalidate the signature — this is the same approach used by Megaprint.

    Args:
        xml_str: Certified XML string returned by certificar_dte.
        adenda:  Dict of arbitrary key-value pairs (flat structure).
                 Keys become XML element names; values become text content.
                 Example: {"OrdenCompra": "OC-001", "CentroCosto": "CC-OPS"}

    Returns:
        Modified XML string with <dte:Adenda> inserted before </dte:SAT>.
    """
    if not adenda:
        return xml_str

    lines = ["<dte:Adenda>"]
    for k, v in adenda.items():
        # Sanitize value: replace < > & to avoid breaking XML
        safe_v = str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"  <{k}>{safe_v}</{k}>")
    lines.append("</dte:Adenda>")
    adenda_xml = "\n".join(lines)

    # Insert just before </dte:SAT> (appears once in every certified XML)
    return xml_str.replace("</dte:SAT>", f"\n{adenda_xml}\n</dte:SAT>", 1)
