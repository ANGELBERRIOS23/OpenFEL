"""
PDF & POS receipt generator for OpenFEL.
Adapted from ViajeXMundo's generate_pdf.py to work with:
  - XML strings (from web API)
  - dict data (from mobile API detail endpoint)
"""
import os
import base64
import tempfile
import xml.etree.ElementTree as ET

import qrcode
from fpdf import FPDF

_C_DARK_DEFAULT = (44, 62, 80)
_C_MID_DEFAULT = (52, 73, 94)
_C_LIGHT_DEFAULT = (236, 240, 241)
_C_BORDER_DEFAULT = (189, 195, 199)


def _hex_to_rgb(hex_str: str) -> tuple | None:
    h = hex_str.lstrip('#')
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _luminance(rgb: tuple) -> float:
    def _lin(c):
        v = c / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast_color(bg_rgb: tuple) -> tuple:
    return _C_DARK_DEFAULT if _luminance(bg_rgb) > 0.179 else (255, 255, 255)


NS = {
    'dte': 'http://www.sat.gob.gt/dte/fel/0.2.0',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
}

FRASE_MAP = {
    (1, 1): "Sujeto a pagos trimestrales ISR",
    (1, 2): "Sujeto a retención definitiva ISR",
    (3, 1): "Sujeto a pagos trimestrales ISR",
    (4, 1): "Exento del IVA por exportación (Art. 7 Ley del IVA)",
    (4, 4): "Exento del IVA (Art. 8 Ley del IVA)",
    (4, 8): "Exento del IVA - Servicios educativos",
    (4, 24): "No afecto al IVA (Fuera del hecho generador artículo 3, Ley del IVA)",
}

MESES_ES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}

TIPO_DTE_NAMES = {
    "FACT": "Factura", "FCAM": "Factura Cambiaria",
    "FPEQ": "Factura Pequeño Contribuyente", "FCAP": "Factura Cambiaria PEQ",
    "FESP": "Factura Especial", "NABN": "Nota de Abono",
    "RDON": "Recibo por Donación", "RECI": "Recibo",
    "NDEB": "Nota de Débito", "NCRE": "Nota de Crédito",
}

AFILIACION_NAMES = {"GEN": "General", "PEQ": "Pequeño Contribuyente", "EXP": "Exportador"}


def numero_a_letras(numero):
    unidades = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
    decenas = ["", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA",
               "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
    especiales = {
        11: "ONCE", 12: "DOCE", 13: "TRECE", 14: "CATORCE", 15: "QUINCE",
        16: "DIECISEIS", 17: "DIECISIETE", 18: "DIECIOCHO", 19: "DIECINUEVE",
        21: "VEINTIUN", 22: "VEINTIDOS", 23: "VEINTITRES", 24: "VEINTICUATRO",
        25: "VEINTICINCO", 26: "VEINTISEIS", 27: "VEINTISIETE", 28: "VEINTIOCHO",
        29: "VEINTINUEVE",
    }
    centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS",
                "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]

    def _conv(n):
        if n == 0: return "CERO"
        if n == 100: return "CIEN"
        parts = []
        if n >= 1000:
            miles = n // 1000; n %= 1000
            parts.append("MIL" if miles == 1 else _conv(miles) + " MIL")
        if n >= 100:
            parts.append(centenas[n // 100]); n %= 100
        if n in especiales:
            parts.append(especiales[n])
        elif n >= 10:
            u = unidades[n % 10]
            parts.append(decenas[n // 10] + (" Y " + u if u else ""))
        elif n > 0:
            parts.append(unidades[n])
        return " ".join(parts)

    entero = int(numero)
    centavos = round((numero - entero) * 100)
    texto = _conv(entero)
    return texto + (f" QUETZALES CON {centavos:02d}/100." if centavos else " QUETZALES EXACTOS.")


def format_nit(nit_str):
    if nit_str and nit_str.upper() != "CF" and len(nit_str) > 1:
        return f"{nit_str[:-1]}-{nit_str[-1]}"
    return "C-F" if nit_str and nit_str.upper() == "CF" else (nit_str or "")


def fmt_date(fecha_iso):
    if not fecha_iso:
        return ""
    if '/' in fecha_iso[:10]:
        return fecha_iso[:10]
    p = fecha_iso[:10].split('-')
    if len(p) == 3:
        return f"{p[2]}/{p[1]}/{p[0]}"
    return fecha_iso[:10]


def fmt_datetime(fecha_iso):
    if not fecha_iso:
        return ""
    date_part = fmt_date(fecha_iso)
    time_part = ""
    if 'T' in fecha_iso:
        time_part = fecha_iso.split('T')[1][:8]
    elif ' ' in fecha_iso:
        time_part = fecha_iso.split(' ')[1][:8] if len(fecha_iso.split(' ')) > 1 else ""
    return f"{date_part} {time_part}".strip()


def date_parts(fecha_iso):
    if not fecha_iso:
        return ["", "", ""]
    if '/' in fecha_iso[:10]:
        p = fecha_iso[:10].split('/')
        return [p[2], p[1], p[0]] if len(p) == 3 else ["", "", ""]
    p = fecha_iso[:10].split('-')
    return int(p[2]), int(p[1]), int(p[0])


def _safe(val, default=""):
    return val if val else default


# ---------------------------------------------------------------------------
# Parse XML string into normalized data dict
# ---------------------------------------------------------------------------

def parse_xml_string(xml_str: str) -> dict:
    root = ET.fromstring(xml_str)
    dte = root.find('.//dte:DTE', NS)
    emision = dte.find('.//dte:DatosEmision', NS)
    dg = emision.find('dte:DatosGenerales', NS)
    em = emision.find('dte:Emisor', NS)
    rec = emision.find('dte:Receptor', NS)
    cert = dte.find('.//dte:Certificacion', NS)

    dir_em = em.find('dte:DireccionEmisor', NS)
    dir_rec = rec.find('dte:DireccionReceptor', NS)

    emisor = {
        'nit': em.get('NITEmisor'),
        'nombre': em.get('NombreEmisor'),
        'nombre_comercial': em.get('NombreComercial', ''),
        'afiliacion': em.get('AfiliacionIVA'),
        'direccion': dir_em.find('dte:Direccion', NS).text or '' if dir_em is not None else '',
        'municipio': dir_em.find('dte:Municipio', NS).text or '' if dir_em is not None else '',
        'departamento': dir_em.find('dte:Departamento', NS).text or '' if dir_em is not None else '',
    }

    receptor = {
        'nit': rec.get('IDReceptor'),
        'nombre': rec.get('NombreReceptor'),
        'correo': rec.get('CorreoReceptor', ''),
        'telefono': rec.get('TelefonoReceptor', ''),
        'direccion': dir_rec.find('dte:Direccion', NS).text if dir_rec is not None else '',
    }

    frases = []
    frases_node = emision.find('dte:Frases', NS)
    if frases_node is not None:
        for f in frases_node.findall('dte:Frase', NS):
            tf = int(f.get('TipoFrase'))
            esc = int(f.get('CodigoEscenario'))
            frases.append(FRASE_MAP.get((tf, esc), f"Frase {tf}/{esc}"))

    items = []
    for el in emision.findall('.//dte:Item', NS):
        imp_el = el.find('.//dte:Impuesto', NS)
        cod_g = int(imp_el.find('dte:CodigoUnidadGravable', NS).text) if imp_el is not None else 1
        monto_i = float(imp_el.find('dte:MontoImpuesto', NS).text) if imp_el is not None else 0.0
        items.append({
            'linea': el.get('NumeroLinea'),
            'bs': el.get('BienOServicio'),
            'cantidad': float(el.find('dte:Cantidad', NS).text),
            'descripcion': el.find('dte:Descripcion', NS).text,
            'precio_unit': float(el.find('dte:PrecioUnitario', NS).text),
            'descuento': float(el.find('dte:Descuento', NS).text),
            'total': float(el.find('dte:Total', NS).text),
            'imp_label': "IVA 12 %" if cod_g == 1 else "Exento 0%",
            'imp_monto': monto_i,
            'cod_gravable': cod_g,
        })

    num_auth = cert.find('dte:NumeroAutorizacion', NS)
    certificacion = {
        'nit_cert': cert.find('dte:NITCertificador', NS).text,
        'nombre_cert': cert.find('dte:NombreCertificador', NS).text,
        'uuid': num_auth.text,
        'serie': num_auth.get('Serie'),
        'numero': num_auth.get('Numero'),
        'fecha': cert.find('dte:FechaHoraCertificacion', NS).text,
    }

    return {
        'tipo': dg.get('Tipo'),
        'fecha_emision': dg.get('FechaHoraEmision'),
        'moneda': dg.get('CodigoMoneda'),
        'emisor': emisor,
        'receptor': receptor,
        'frases': frases,
        'items': items,
        'gran_total': float(emision.find('.//dte:GranTotal', NS).text),
        'certificacion': certificacion,
    }


# ---------------------------------------------------------------------------
# Convert mobile API detail dict to normalized data dict
# ---------------------------------------------------------------------------

def parse_detail_dict(d: dict, nit_emisor: str = "") -> dict:
    items = []
    for item in d.get("items", []):
        items.append({
            'linea': str(item.get('orden', item.get('linea', 1))),
            'bs': item.get('bienOServicio', 'S'),
            'cantidad': float(item.get('cantidad', 1)),
            'descripcion': item.get('descripcion', ''),
            'precio_unit': float(item.get('precioUnitario', item.get('precio', 0))),
            'descuento': float(item.get('descuento', 0)),
            'total': float(item.get('total', item.get('subtotal', 0))),
            'imp_label': item.get('impuestoTexto', 'IVA 12 %'),
            'imp_monto': float(item.get('montoImpuesto', 0)),
            'cod_gravable': item.get('codigoUnidadGravable', 1),
        })

    totales = d.get("totales", {})
    gran_total = float(totales.get('granTotal', d.get('granTotal', d.get('total', 0))))

    return {
        'tipo': d.get('tipo', d.get('tipoDocumento', 'FACT')),
        'fecha_emision': d.get('fechaEmision', d.get('FechaEmision', '')),
        'moneda': d.get('codigoMoneda', 'GTQ'),
        'emisor': {
            'nit': d.get('nitEmisor', nit_emisor),
            'nombre': d.get('nombreEmisor', ''),
            'nombre_comercial': d.get('nombreComercialEmisor', d.get('nombreEmisor', '')),
            'afiliacion': d.get('afiliacionIVA', 'GEN'),
            'direccion': d.get('direccionEmisor', ''),
            'municipio': d.get('municipioEmisor', 'Guatemala'),
            'departamento': d.get('departamentoEmisor', 'Guatemala'),
        },
        'receptor': {
            'nit': d.get('nitReceptor', d.get('NITReceptor', 'CF')),
            'nombre': d.get('nombreReceptor', d.get('NombreReceptor', 'CF')),
            'correo': d.get('correoReceptor', ''),
            'telefono': d.get('telefonoReceptor', ''),
            'direccion': d.get('direccionReceptor', 'ciudad'),
        },
        'frases': d.get('frases', []),
        'items': items,
        'gran_total': gran_total,
        'certificacion': {
            'nit_cert': d.get('nitCertificador', ''),
            'nombre_cert': d.get('nombreCertificador', ''),
            'uuid': d.get('UUID', d.get('uuid', d.get('numeroAutorizacion', ''))),
            'serie': d.get('serie', ''),
            'numero': str(d.get('numeroDocumento', d.get('numero', ''))),
            'fecha': d.get('fechaCertificacion', ''),
        },
    }


# ---------------------------------------------------------------------------
# FacturaPDF class (from ViajeXMundo, adapted)
# ---------------------------------------------------------------------------

class FacturaPDF(FPDF):
    C_WHITE = (255, 255, 255)
    C_LINK = (41, 128, 185)
    PAGE_W = 196
    LEFT = 10

    def __init__(self, data, logo_path=None, branding: dict = None):
        super().__init__('P', 'mm', 'Letter')
        self.data = data
        self.logo_path = logo_path if logo_path and os.path.exists(logo_path) else None
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(10, 10, 10)

        b = branding or {}
        self.C_DARK = _hex_to_rgb(b.get('color_primario', '')) or _C_DARK_DEFAULT
        self.C_MID = _hex_to_rgb(b.get('color_secundario', '')) or _C_MID_DEFAULT
        self.C_LIGHT = _C_LIGHT_DEFAULT
        self.C_BORDER = _C_BORDER_DEFAULT
        self.C_ON_DARK = _contrast_color(self.C_DARK)
        self.C_ON_MID = _contrast_color(self.C_MID)
        self.C_ON_LIGHT = _contrast_color(self.C_LIGHT)
        self.empresa_tel = b.get('telefono', '')
        self.empresa_email = b.get('email', '')
        self.empresa_web = b.get('web', '')

    def fc(self, c): self.set_fill_color(*c)
    def tc(self, c): self.set_text_color(*c)
    def dc(self, c): self.set_draw_color(*c)

    def build(self):
        self.add_page()
        y = self._draw_header()
        y = self._draw_detalle_documento(y)
        y = self._draw_receptor(y)
        y = self._draw_items_table(y)
        y = self._draw_totals(y)
        y = self._draw_authorization(y)
        y = self._draw_detalle_adicional(y)
        self._draw_footer(y)

    def _draw_header(self):
        d = self.data
        em = d['emisor']
        cert = d['certificacion']
        Y0 = 12
        logo_w = 40
        info_x = self.LEFT + logo_w + 3
        info_w = 80
        box_x = self.LEFT + self.PAGE_W - 66
        box_w = 66

        if self.logo_path:
            self.image(self.logo_path, x=self.LEFT, y=Y0, w=logo_w)

        nombre_comercial = em.get('nombre_comercial', '')
        if ' - ' in nombre_comercial:
            nombre_comercial = nombre_comercial.split(' - ', 1)[1]

        self.set_xy(info_x, Y0)
        self.set_font('Helvetica', 'B', 10)
        self.tc(self.C_DARK)
        self.cell(info_w, 5, nombre_comercial or em.get('nombre', ''), align='C')

        self.set_xy(info_x, Y0 + 5)
        self.set_font('Helvetica', '', 7)
        self.cell(info_w, 4, em.get('nombre', ''), align='C')

        dir_full = f"{em.get('direccion','')}, {em.get('municipio','')}, {em.get('departamento','')}"
        self.set_xy(info_x, Y0 + 9)
        self.cell(info_w, 4, dir_full, align='C')

        self.set_xy(info_x, Y0 + 13)
        self.cell(info_w, 4, f"NIT: {format_nit(em['nit'])}", align='C')

        self.set_xy(info_x, Y0 + 17)
        if self.empresa_tel:
            self.cell(info_w, 4, f"Tel: {self.empresa_tel}", align='C')

        row_y = Y0 + 21
        self.tc(self.C_LINK)
        if self.empresa_email:
            self.set_xy(info_x, row_y)
            self.cell(info_w, 4, self.empresa_email, align='C')
            row_y += 4
        if self.empresa_web:
            self.set_xy(info_x, row_y)
            self.cell(info_w, 4, self.empresa_web, align='C')
        self.tc(self.C_DARK)

        tipo_nombre = TIPO_DTE_NAMES.get(d['tipo'], d['tipo'])
        afil_nombre = AFILIACION_NAMES.get(em.get('afiliacion', 'GEN'), em.get('afiliacion', ''))

        self.set_xy(box_x, Y0)
        self.set_font('Helvetica', 'B', 7.5)
        self.tc(self.C_DARK)
        self.cell(box_w, 5, "DOCUMENTO TRIBUTARIO ELECTRONICO", align='C')

        self.set_xy(box_x, Y0 + 5)
        self.fc(self.C_DARK); self.tc(self.C_ON_DARK)
        self.set_font('Helvetica', 'B', 9)
        self.cell(box_w, 7, f"{tipo_nombre} Electronica", fill=True, align='C')

        self.set_xy(box_x, Y0 + 12)
        self.fc(self.C_MID); self.tc(self.C_ON_MID)
        self.set_font('Helvetica', '', 8)
        self.cell(box_w, 5, afil_nombre, fill=True, align='C')

        self.set_xy(box_x, Y0 + 17)
        self.fc(self.C_LIGHT); self.tc(self.C_DARK)
        self.set_font('Helvetica', 'B', 8)
        self.cell(box_w, 4.5, f"Serie: {cert.get('serie','')}", fill=True, align='C')

        self.set_xy(box_x, Y0 + 21.5)
        self.cell(box_w, 4.5, f"No: {cert.get('numero','')}", fill=True, align='C')

        self.dc(self.C_BORDER)
        self.rect(box_x, Y0, box_w, 26)

        return Y0 + 30

    def _draw_detalle_documento(self, Y):
        d = self.data
        Y += 3
        block_w = 120
        block_h = 30

        self.fc(self.C_DARK); self.tc(self.C_ON_DARK)
        self.set_font('Helvetica', 'B', 9)
        self.set_xy(self.LEFT, Y)
        self.cell(block_w, 6, "  Detalle del Documento", fill=True)

        self.fc(self.C_WHITE); self.tc(self.C_DARK)
        self.set_xy(self.LEFT, Y + 6)
        self.cell(block_w, block_h - 6, '', fill=True, border=1)

        moneda_nombre = "Quetzal" if d['moneda'] == "GTQ" else d['moneda']
        lines = [
            ("Forma de Pago:", "Contado"),
            ("Moneda:", moneda_nombre),
            ("Fecha de Emision:", fmt_date(d['fecha_emision']) if d['fecha_emision'] else ''),
        ]
        ly = Y + 8
        for label, val in lines:
            self.set_xy(self.LEFT + 3, ly)
            self.set_font('Helvetica', 'B', 8); self.cell(30, 4, label)
            self.set_font('Helvetica', '', 8); self.cell(60, 4, val)
            ly += 5

        self.dc(self.C_BORDER)
        self.rect(self.LEFT, Y, block_w, block_h)

        if d['fecha_emision']:
            dia, mes_num, anio = date_parts(d['fecha_emision'])
            date_x = self.LEFT + self.PAGE_W - 66
            date_w = 66
            col_w = [22, 32, 12]

            self.fc(self.C_DARK); self.tc(self.C_ON_DARK)
            self.set_font('Helvetica', 'B', 8)
            self.set_xy(date_x, Y)
            for txt, cw in zip(["DIA", "MES", "ANO"], col_w):
                self.cell(cw, 6, txt, fill=True, align='C')

            self.fc(self.C_LIGHT); self.tc(self.C_DARK)
            self.set_xy(date_x, Y + 6)
            self.set_font('Helvetica', '', 10)
            self.cell(col_w[0], 10, str(dia), fill=True, align='C')
            self.set_font('Helvetica', '', 9)
            self.cell(col_w[1], 10, MESES_ES.get(mes_num, ""), fill=True, align='C')
            self.set_font('Helvetica', '', 10)
            self.cell(col_w[2], 10, str(anio), fill=True, align='C')

            self.dc(self.C_BORDER)
            self.rect(date_x, Y, date_w, 16)

        return Y + block_h + 3

    def _draw_receptor(self, Y):
        rec = self.data['receptor']
        nit_display = format_nit(rec['nit'])
        rows = [
            [("Nombre Receptor:", _safe(rec['nombre'], 'CF'), 100), ("NIT:", nit_display, 46)],
            [("Telefono:", _safe(rec.get('telefono'), 'N/A'), 100), ("Email:", _safe(rec.get('correo'), 'N/A'), 46)],
            [("Direccion:", _safe(rec.get('direccion'), ''), 146)],
        ]
        row_h = 6
        self.dc(self.C_BORDER)
        for r_idx, row in enumerate(rows):
            ry = Y + r_idx * row_h
            x = self.LEFT
            for label, val, w in row:
                self.set_xy(x, ry)
                self.set_font('Helvetica', 'B', 8); self.tc(self.C_DARK)
                lw = self.get_string_width(label) + 2
                self.cell(lw, row_h, label)
                self.set_font('Helvetica', '', 8)
                self.cell(w - lw, row_h, val)
                x += w
            if r_idx < len(rows) - 1:
                self.line(self.LEFT, ry + row_h, self.LEFT + self.PAGE_W, ry + row_h)
        self.rect(self.LEFT, Y, self.PAGE_W, row_h * len(rows))
        return Y + row_h * len(rows) + 4

    def _draw_items_table(self, Y):
        items = self.data['items']
        CW = [16, 12, 10, 66, 22, 14, 34, 22]
        HEADERS = ["CANTIDAD", "COD", "B/S", "DESCRIPCION", "P.UNIT", "DESC", "IMPUESTOS", "TOTAL"]
        HDR_H = 6

        self.fc(self.C_DARK); self.tc(self.C_ON_DARK)
        self.set_font('Helvetica', 'B', 7)
        self.set_xy(self.LEFT, Y)
        for h, cw in zip(HEADERS, CW):
            self.cell(cw, HDR_H, h, border=1, align='C', fill=True)
        self.ln()

        self.tc(self.C_DARK)
        self.dc(self.C_BORDER)

        for idx, item in enumerate(items):
            row_y = self.get_y()
            if idx % 2 == 0:
                self.fc(self.C_WHITE)
            else:
                self.fc(self.C_LIGHT)

            desc = item['descripcion']
            self.set_font('Helvetica', '', 7.5)
            desc_lines = self.multi_cell(CW[3], 4, desc, border=0, dry_run=True, output="LINES")
            desc_lines = [l for l in desc_lines if l.strip()]
            row_h = max(8, max(1, len(desc_lines)) * 4 + 2)

            cells = [
                (str(int(item['cantidad'])), 'C'),
                (str(item['linea']), 'C'),
                (item.get('bs', 'S'), 'C'),
                (None, None),
                (f"{item['precio_unit']:.2f}", 'R'),
                (f"{item['descuento']:.2f}", 'R'),
                (f"{item.get('imp_label','IVA')}:  {item.get('imp_monto',0):.2f}", 'C'),
                (f"{item['total']:.2f}", 'R'),
            ]

            x = self.LEFT
            for i, (txt, align) in enumerate(cells):
                cw = CW[i]
                if txt is None:
                    self.set_xy(x, row_y)
                    self.set_font('Helvetica', '', 7.5)
                    self.multi_cell(cw, 4, desc, border=1, align='L',
                                    fill=(idx % 2 != 0), padding=(1, 1, 1, 2))
                else:
                    self.set_xy(x, row_y)
                    self.set_font('Helvetica', '', 7.5)
                    self.cell(cw, row_h, txt, border=1, align=align, fill=(idx % 2 != 0))
                x += cw
            self.set_y(row_y + row_h)

        return self.get_y() + 3

    def _draw_totals(self, Y):
        Y += 2
        gran_total = self.data['gran_total']
        letras = numero_a_letras(gran_total)

        self.set_xy(self.LEFT, Y)
        self.set_font('Helvetica', 'B', 8); self.tc(self.C_DARK)
        self.cell(50, 5, "TOTAL EN LETRAS:")

        self.set_xy(self.LEFT, Y + 5)
        self.set_font('Helvetica', '', 8)
        self.multi_cell(115, 5, letras)

        box_x = self.LEFT + self.PAGE_W - 66
        self.fc(self.C_DARK); self.tc(self.C_ON_DARK)
        self.set_font('Helvetica', 'B', 11)
        self.set_xy(box_x, Y)
        self.cell(28, 10, "TOTAL:", fill=True, align='C')

        self.fc(self.C_LIGHT); self.tc(self.C_DARK)
        self.set_xy(box_x + 28, Y)
        self.cell(38, 10, f"Q {gran_total:,.2f}", fill=True, align='C')

        self.dc(self.C_BORDER)
        self.rect(box_x, Y, 66, 10)

        return Y + 18

    def _draw_authorization(self, Y):
        cert = self.data['certificacion']
        rows = [
            ("NUMERO DE AUTORIZACION:", cert.get('uuid', '')),
            ("FECHA DE CERTIFICACION:", fmt_datetime(cert['fecha']) if cert.get('fecha') else ''),
        ]
        row_h = 6
        self.tc(self.C_DARK)
        self.dc(self.C_BORDER)

        for i, (label, val) in enumerate(rows):
            ry = Y + i * row_h
            self.set_xy(self.LEFT, ry)
            self.set_font('Helvetica', 'B', 8)
            self.cell(52, row_h, label)
            self.set_font('Helvetica', '', 8)
            self.cell(self.PAGE_W - 52, row_h, val)
            if i < len(rows) - 1:
                self.line(self.LEFT, ry + row_h, self.LEFT + self.PAGE_W, ry + row_h)

        self.rect(self.LEFT, Y, self.PAGE_W, row_h * len(rows))
        return Y + row_h * len(rows) + 4

    def _draw_detalle_adicional(self, Y):
        frases = self.data.get('frases', [])
        if not frases:
            return Y

        self.set_xy(self.LEFT, Y)
        self.set_font('Helvetica', 'B', 8); self.tc(self.C_DARK)
        self.cell(40, 5, "Detalle Adicional:")
        Y += 5

        for frase in frases:
            self.set_xy(self.LEFT, Y)
            self.set_font('Helvetica', '', 7.5)
            txt = frase if isinstance(frase, str) else str(frase)
            if "ISR" in txt:
                self.cell(self.PAGE_W, 4, f"Frase de retencion del ISR - {txt} -")
            else:
                self.cell(self.PAGE_W, 4, txt)
            Y += 4

        return Y + 4

    def _draw_footer(self, Y):
        cert = self.data['certificacion']
        em = self.data['emisor']
        rec = self.data['receptor']
        Y += 2

        qr_url = (
            f"https://felpub.c.sat.gob.gt/verificador-web/publico/vistas/verificacionDte.jsf"
            f"?tipo=autorizacion"
            f"&numero={cert.get('uuid','')}"
            f"&emisor={em['nit']}"
            f"&receptor={rec['nit']}"
            f"&monto={self.data['gran_total']}"
        )
        qr_img = qrcode.make(qr_url)
        qr_path = os.path.join(tempfile.gettempdir(), f"qr_{cert.get('serie','tmp')}.png")
        qr_img.save(qr_path)

        qr_size = 28
        self.image(qr_path, x=self.LEFT + self.PAGE_W - qr_size, y=Y, w=qr_size)

        self.set_xy(self.LEFT, Y)
        self.set_font('Helvetica', 'B', 8); self.tc(self.C_DARK)
        self.cell(22, 5, "Certificador:")
        self.set_font('Helvetica', '', 8)
        self.cell(120, 5, f"{cert.get('nombre_cert','')}  Nit: {cert.get('nit_cert','')}")

        self.set_xy(self.LEFT, Y + 6)
        self.set_font('Helvetica', '', 7)
        self.set_text_color(120, 120, 120)
        self.cell(150, 4, "Emitido y autorizado por la Superintendencia de Administracion Tributaria (SAT)")

        if os.path.exists(qr_path):
            os.remove(qr_path)


# ---------------------------------------------------------------------------
# POS Receipt (58mm or 80mm thermal printer)
# ---------------------------------------------------------------------------

class ReciboPOS(FPDF):
    def __init__(self, data, width_mm: int = 80):
        page_w = width_mm
        super().__init__('P', 'mm', (page_w, 297))
        self.data = data
        self.page_w = page_w
        self.margin = 3
        self.usable = page_w - 2 * self.margin
        self.set_margins(self.margin, self.margin, self.margin)
        self.set_auto_page_break(auto=False)

    def build(self):
        self.add_page()
        d = self.data
        em = d['emisor']
        rec = d['receptor']
        cert = d['certificacion']
        y = self.margin

        self.set_font('Helvetica', 'B', 10)
        self.set_xy(self.margin, y)
        self.cell(self.usable, 5, em.get('nombre_comercial', em.get('nombre', '')), align='C')
        y += 5

        self.set_font('Helvetica', '', 7)
        self.set_xy(self.margin, y)
        self.cell(self.usable, 3.5, em.get('nombre', ''), align='C')
        y += 3.5

        self.set_xy(self.margin, y)
        self.cell(self.usable, 3.5, f"NIT: {format_nit(em['nit'])}", align='C')
        y += 3.5

        dir_full = f"{em.get('direccion','')}, {em.get('municipio','')}"
        self.set_xy(self.margin, y)
        self.cell(self.usable, 3.5, dir_full, align='C')
        y += 5

        y = self._dashed_line(y)

        tipo_nombre = TIPO_DTE_NAMES.get(d['tipo'], d['tipo'])
        self.set_font('Helvetica', 'B', 9)
        self.set_xy(self.margin, y)
        self.cell(self.usable, 5, f"{tipo_nombre} Electronica", align='C')
        y += 5

        self.set_font('Helvetica', '', 7)
        self.set_xy(self.margin, y)
        self.cell(self.usable, 3.5, f"Serie: {cert.get('serie','')}  No: {cert.get('numero','')}", align='C')
        y += 3.5

        self.set_xy(self.margin, y)
        fecha_str = fmt_datetime(d['fecha_emision']) if d.get('fecha_emision') else ''
        self.cell(self.usable, 3.5, f"Fecha: {fecha_str}", align='C')
        y += 5

        y = self._dashed_line(y)

        self.set_font('Helvetica', '', 7)
        self.set_xy(self.margin, y)
        self.cell(self.usable, 3.5, f"NIT: {format_nit(rec['nit'])}  {rec.get('nombre','CF')}")
        y += 5

        y = self._dashed_line(y)

        col_desc = self.usable - 30
        col_qty = 10
        col_total = 20

        self.set_font('Helvetica', 'B', 7)
        self.set_xy(self.margin, y)
        self.cell(col_qty, 3.5, "Cant")
        self.cell(col_desc, 3.5, "Descripcion")
        self.cell(col_total, 3.5, "Total", align='R')
        y += 4

        self.set_font('Helvetica', '', 7)
        for item in d['items']:
            self.set_xy(self.margin, y)
            self.cell(col_qty, 3.5, str(int(item['cantidad'])))
            desc = item['descripcion']
            if len(desc) > 30:
                desc = desc[:28] + ".."
            self.cell(col_desc, 3.5, desc)
            self.cell(col_total, 3.5, f"Q{item['total']:.2f}", align='R')
            y += 3.5

        y += 2
        y = self._dashed_line(y)

        self.set_font('Helvetica', 'B', 9)
        self.set_xy(self.margin, y)
        self.cell(self.usable - 25, 5, "TOTAL:")
        self.cell(25, 5, f"Q{d['gran_total']:,.2f}", align='R')
        y += 6

        self.set_font('Helvetica', '', 6)
        letras = numero_a_letras(d['gran_total'])
        self.set_xy(self.margin, y)
        self.multi_cell(self.usable, 3, letras)
        y = self.get_y() + 2

        y = self._dashed_line(y)

        self.set_font('Helvetica', '', 5.5)
        self.set_xy(self.margin, y)
        self.cell(self.usable, 3, f"UUID: {cert.get('uuid','')}", align='C')
        y += 3

        self.set_xy(self.margin, y)
        fecha_cert = fmt_datetime(cert['fecha']) if cert.get('fecha') else ''
        self.cell(self.usable, 3, f"Cert: {fecha_cert}", align='C')
        y += 3

        self.set_xy(self.margin, y)
        self.cell(self.usable, 3, f"Certificador: {cert.get('nombre_cert','')}", align='C')
        y += 5

        qr_url = (
            f"https://felpub.c.sat.gob.gt/verificador-web/publico/vistas/verificacionDte.jsf"
            f"?tipo=autorizacion&numero={cert.get('uuid','')}"
            f"&emisor={em['nit']}&receptor={rec['nit']}&monto={d['gran_total']}"
        )
        qr_img = qrcode.make(qr_url)
        qr_path = os.path.join(tempfile.gettempdir(), f"qr_pos_{cert.get('serie','tmp')}.png")
        qr_img.save(qr_path)

        qr_size = min(self.usable * 0.6, 35)
        qr_x = self.margin + (self.usable - qr_size) / 2
        self.image(qr_path, x=qr_x, y=y, w=qr_size)
        y += qr_size + 3

        self.set_font('Helvetica', '', 5)
        self.set_xy(self.margin, y)
        self.cell(self.usable, 3, "Emitido y autorizado por SAT", align='C')
        y += 4

        if os.path.exists(qr_path):
            os.remove(qr_path)

        pass

    def _dashed_line(self, y):
        x = self.margin
        while x < self.margin + self.usable:
            self.line(x, y, min(x + 2, self.margin + self.usable), y)
            x += 4
        return y + 2


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_custom_pdf(
    data: dict,
    branding: dict = None,
    logo_b64: str = None,
) -> bytes:
    logo_path = None
    try:
        if logo_b64:
            logo_path = os.path.join(tempfile.gettempdir(), "openfel_logo_tmp.png")
            with open(logo_path, "wb") as f:
                f.write(base64.b64decode(logo_b64))

        pdf = FacturaPDF(data, logo_path=logo_path, branding=branding)
        pdf.build()
        return pdf.output()
    finally:
        if logo_path and os.path.exists(logo_path):
            os.remove(logo_path)


def generate_custom_pdf_from_xml(
    xml_str: str,
    branding: dict = None,
    logo_b64: str = None,
) -> bytes:
    data = parse_xml_string(xml_str)
    return generate_custom_pdf(data, branding=branding, logo_b64=logo_b64)


def generate_custom_pdf_from_detail(
    detail: dict,
    nit_emisor: str = "",
    branding: dict = None,
    logo_b64: str = None,
) -> bytes:
    data = parse_detail_dict(detail, nit_emisor=nit_emisor)
    return generate_custom_pdf(data, branding=branding, logo_b64=logo_b64)


def generate_pos_receipt(
    data: dict,
    width_mm: int = 80,
) -> bytes:
    receipt = ReciboPOS(data, width_mm=width_mm)
    receipt.build()
    return receipt.output()


def generate_pos_receipt_from_detail(
    detail: dict,
    nit_emisor: str = "",
    width_mm: int = 80,
) -> bytes:
    data = parse_detail_dict(detail, nit_emisor=nit_emisor)
    return generate_pos_receipt(data, width_mm=width_mm)
