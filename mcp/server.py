"""
OpenFEL MCP Server — exposes OpenFEL API as tools for AI agents.

Usage:
  OPENFEL_URL=http://localhost:8000 OPENFEL_API_KEY=ofel_k1_... python -m mcp.server

Or set these in a .env file and point to it with OPENFEL_ENV_FILE.
"""
import json
import os
import sys

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    from mcp.server.stdio import run_server
except ImportError:
    print("Install mcp: pip install mcp", file=sys.stderr)
    sys.exit(1)

import httpx

env_file = os.environ.get("OPENFEL_ENV_FILE", ".env")
if os.path.exists(env_file):
    for line in open(env_file):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

BASE_URL = os.environ.get("OPENFEL_URL", "http://localhost:8000")
API_KEY = os.environ.get("OPENFEL_API_KEY", "")

server = Server("openfel-mcp")


def _headers():
    return {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def _call(method: str, path: str, body: dict | None = None) -> str:
    url = f"{BASE_URL}/api{path}"
    with httpx.Client(timeout=60) as client:
        if method == "GET":
            r = client.get(url, headers=_headers(), params=body)
        elif method == "POST":
            r = client.post(url, headers=_headers(), json=body)
        elif method == "PATCH":
            r = client.patch(url, headers=_headers(), json=body)
        elif method == "DELETE":
            r = client.delete(url, headers=_headers())
        else:
            return f"Unknown method: {method}"

    try:
        return json.dumps(r.json(), indent=2, ensure_ascii=False)
    except Exception:
        return r.text


@server.list_tools()
async def list_tools():
    return [
        Tool(name="openfel_health", description="Check SAT server health status", inputSchema={"type": "object", "properties": {}}),
        Tool(name="openfel_nit_lookup", description="Look up a NIT in SAT RTU", inputSchema={
            "type": "object",
            "properties": {
                "account_nit": {"type": "string", "description": "NIT of the OpenFEL account to use"},
                "nit": {"type": "string", "description": "NIT to look up"},
            },
            "required": ["account_nit", "nit"],
        }),
        Tool(name="openfel_emit", description="Emit a DTE. Each item supports regimen: GENERAL, EXENTO, EXPORT, PEQ, NO_AFECTO, TURISMO_HOSPEDAJE, PETROLEO, TURISMO_PASAJES, TIMBRE_PRENSA, BOMBEROS, BEBIDAS_ALCOHOLICAS, TABACO, CEMENTO, BEBIDAS_NO_ALCOHOLICAS, TARIFA_PORTUARIA. Append _N for sub-codes (e.g. PETROLEO_4 for diesel).", inputSchema={
            "type": "object",
            "properties": {
                "account_nit": {"type": "string"},
                "tipo": {"type": "string", "enum": ["FACT", "FCAM", "FPEQ", "FESP", "NABN", "NDEB", "NCRE"], "default": "FACT"},
                "receptor_nit": {"type": "string", "default": "CF"},
                "receptor_nombre": {"type": "string", "default": "Consumidor Final"},
                "items": {"type": "array", "items": {"type": "object", "properties": {
                    "descripcion": {"type": "string"}, "cantidad": {"type": "number"}, "precio_unitario": {"type": "number"},
                    "regimen": {"type": "string", "description": "Tax regime for this item"},
                }}},
            },
            "required": ["account_nit", "items"],
        }),
        Tool(name="openfel_annul", description="Annul a DTE", inputSchema={
            "type": "object",
            "properties": {
                "account_nit": {"type": "string"},
                "uuid": {"type": "string"},
                "motivo": {"type": "string", "default": "Anulación"},
                "nit_receptor": {"type": "string", "default": "CF", "description": "Must match original receptor NIT"},
            },
            "required": ["account_nit", "uuid"],
        }),
        Tool(name="openfel_list_emitted", description="List emitted DTEs for an account", inputSchema={
            "type": "object",
            "properties": {"account_nit": {"type": "string"}},
            "required": ["account_nit"],
        }),
        Tool(name="openfel_list_received", description="List received DTEs for an account", inputSchema={
            "type": "object",
            "properties": {"account_nit": {"type": "string"}},
            "required": ["account_nit"],
        }),
        Tool(name="openfel_list_accounts", description="List all OpenFEL accounts", inputSchema={"type": "object", "properties": {}}),
        Tool(name="openfel_list_keys", description="List all API keys", inputSchema={"type": "object", "properties": {}}),
        Tool(name="openfel_create_account", description="Create a new SAT account", inputSchema={
            "type": "object",
            "properties": {
                "nit": {"type": "string"},
                "login_password": {"type": "string"},
                "cert_password": {"type": "string"},
                "preferred_api": {"type": "string", "enum": ["mixed", "mobile", "web"], "default": "mixed"},
                "affiliation": {"type": "string", "enum": ["GEN", "PEQ"], "default": "GEN"},
            },
            "required": ["nit", "login_password", "cert_password"],
        }),
        Tool(name="openfel_update_branding", description="Update account branding (colors, logo, contact info) for custom PDF generation", inputSchema={
            "type": "object",
            "properties": {
                "nit": {"type": "string", "description": "Account NIT to update"},
                "color_primario": {"type": "string", "description": "Primary hex color, e.g. #1a5276"},
                "color_secundario": {"type": "string", "description": "Secondary hex color, e.g. #2e86c1"},
                "telefono": {"type": "string"},
                "email": {"type": "string"},
                "web": {"type": "string"},
                "logo_b64": {"type": "string", "description": "PNG logo as base64 string (null to remove)"},
            },
            "required": ["nit"],
        }),
        Tool(name="openfel_custom_pdf", description="Download a branded PDF for a DTE (with logo, colors, QR)", inputSchema={
            "type": "object",
            "properties": {
                "account_nit": {"type": "string"},
                "uuid": {"type": "string"},
                "nit_receptor": {"type": "string", "default": "CF"},
                "output_path": {"type": "string", "description": "Local path to save the PDF"},
            },
            "required": ["account_nit", "uuid", "output_path"],
        }),
        Tool(name="openfel_pos_receipt", description="Download a POS thermal receipt PDF for a DTE", inputSchema={
            "type": "object",
            "properties": {
                "account_nit": {"type": "string"},
                "uuid": {"type": "string"},
                "nit_receptor": {"type": "string", "default": "CF"},
                "width": {"type": "integer", "enum": [58, 80], "default": 80, "description": "Receipt width in mm"},
                "output_path": {"type": "string", "description": "Local path to save the PDF"},
            },
            "required": ["account_nit", "uuid", "output_path"],
        }),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "openfel_health":
            result = _call("GET", "/health")
        elif name == "openfel_nit_lookup":
            result = _call("POST", "/nit/lookup", arguments)
        elif name == "openfel_emit":
            result = _call("POST", "/dte/emit", arguments)
        elif name == "openfel_annul":
            result = _call("POST", "/dte/annul", arguments)
        elif name == "openfel_list_emitted":
            result = _call("GET", f"/dte/emitted", {"account_nit": arguments["account_nit"]})
        elif name == "openfel_list_received":
            result = _call("GET", f"/dte/received", {"account_nit": arguments["account_nit"]})
        elif name == "openfel_list_accounts":
            result = _call("GET", "/accounts")
        elif name == "openfel_list_keys":
            result = _call("GET", "/keys")
        elif name == "openfel_create_account":
            result = _call("POST", "/accounts", arguments)
        elif name == "openfel_update_branding":
            nit = arguments.pop("nit")
            branding = {k: v for k, v in arguments.items() if v is not None}
            result = _call("PATCH", f"/accounts/{nit}", {"branding": branding})
        elif name == "openfel_custom_pdf":
            output_path = arguments.get("output_path", "/tmp/custom.pdf")
            url = f"{BASE_URL}/api/dte/{arguments['uuid']}/custom-pdf"
            params = {"account_nit": arguments["account_nit"], "nit_receptor": arguments.get("nit_receptor", "CF")}
            with httpx.Client(timeout=60) as client:
                r = client.get(url, headers=_headers(), params=params)
            if r.status_code == 200 and len(r.content) > 0:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                result = json.dumps({"saved": output_path, "size_bytes": len(r.content)})
            else:
                result = f"Error {r.status_code}: {r.text[:200]}"
        elif name == "openfel_pos_receipt":
            output_path = arguments.get("output_path", "/tmp/receipt.pdf")
            url = f"{BASE_URL}/api/dte/{arguments['uuid']}/pos-receipt"
            params = {"account_nit": arguments["account_nit"], "nit_receptor": arguments.get("nit_receptor", "CF"), "width": arguments.get("width", 80)}
            with httpx.Client(timeout=60) as client:
                r = client.get(url, headers=_headers(), params=params)
            if r.status_code == 200 and len(r.content) > 0:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                result = json.dumps({"saved": output_path, "size_bytes": len(r.content)})
            else:
                result = f"Error {r.status_code}: {r.text[:200]}"
        else:
            result = f"Unknown tool: {name}"
    except Exception as e:
        result = f"Error: {e}"

    return [TextContent(type="text", text=result)]


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_server(server))
