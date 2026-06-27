# OpenFEL

Multi-account SAT Guatemala FEL (Factura Electrónica en Línea) platform with API key management, automatic web/mobile API fallback, and React dashboard.

## Quick Start

### Local Development

```bash
# Backend
pip install -r requirements.txt
cp .env.example .env
python -m backend.main

# Dashboard (separate terminal)
cd dashboard
npm install
npm run dev
```

On first boot, the master encryption key and an admin API key are printed to stdout. Save both.

### Docker

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8000` for the dashboard.

## API

All endpoints (except `/api/health`) require the `X-API-Key` header.

| Endpoint | Method | Role | Description |
|----------|--------|------|-------------|
| `/api/health` | GET | public | SAT server status (4 servers) |
| `/api/nit/lookup` | POST | VIEWER | Consultar NIT en RTU |
| `/api/dte/emit` | POST | OPERATOR | Emitir DTE |
| `/api/dte/annul` | POST | OPERATOR | Anular DTE |
| `/api/dte/emitted` | GET | VIEWER | Listar emitidos |
| `/api/dte/received` | GET | VIEWER | Listar recibidos |
| `/api/dte/{uuid}/detail` | GET | VIEWER | Detalle DTE |
| `/api/dte/{uuid}/pdf` | GET | VIEWER | Descargar PDF |
| `/api/accounts` | GET/POST | ADMIN | CRUD cuentas SAT |
| `/api/accounts/{nit}` | GET/PATCH/DELETE | ADMIN | Gestionar cuenta |
| `/api/keys` | GET/POST | ADMIN | CRUD API keys |
| `/api/keys/{id}` | PATCH/DELETE | ADMIN | Gestionar key |
| `/api/logs` | GET | ADMIN | Audit log |

## Roles

- **VIEWER**: Read-only (consultas, NIT lookup, PDF download)
- **OPERATOR**: + Emitir y anular DTEs
- **ADMIN**: + Gestionar cuentas, API keys y ver logs

## Architecture

```
SAT Guatemala
├── Mobile API (svc.c.sat.gob.gt) ─ JSON, 12h token, fast
├── Web Emission (felav02.c.sat.gob.gt) ─ AES+XML, 25min session
├── Web Consultation (felcons.c.sat.gob.gt) ─ PDF/XML/XLS download
└── Login Portal (farm3.sat.gob.gt) ─ Authentication

OpenFEL wraps both APIs with automatic fallback:
Mobile first → Web fallback (or vice versa per account config)
```

## Security

- Credentials encrypted at rest with Fernet (AES-128-CBC)
- API keys stored as SHA-256 hashes (full key shown only once)
- Master key auto-generated on first boot, saved to `data/.openfel_master_key`
- Role-based access control on all endpoints
- Full audit logging of all operations
