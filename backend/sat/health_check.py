#!/usr/bin/env python3
"""
SAT FEL Health Check
=====================

Checks the health of all SAT Guatemala FEL infrastructure endpoints.
Can be run standalone (CLI) or imported as a module.

Checks:
  1. Mobile API (svc.c.sat.gob.gt) — GET /core/core/tiempo
  2. Web API - Emisión (felav02.c.sat.gob.gt) — TCP connect
  3. Web API - Consulta (felcons.c.sat.gob.gt) — TCP connect
  4. Login portal (farm3.sat.gob.gt) — HTTPS GET
  5. DNS resolution for all domains
  6. Optional: authenticated check (login + NIT lookup)

Usage:
    python health_check.py              # Quick check (no credentials needed)
    python health_check.py --full       # Full check including auth (needs .env)
    python health_check.py --json       # Output as JSON
"""

import socket
import ssl
import time
import json
import sys
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

# Domains and their expected roles
ENDPOINTS = {
    "mobile_api": {
        "domain": "svc.c.sat.gob.gt",
        "port": 443,
        "description": "API Móvil (emisión, consulta, PDF)",
        "health_path": "/api/v3/core/core/tiempo",
        "method": "GET",
        "extra_headers": {"apikey": "XPJHZnixcMm2DWVSla2OQfIL82ZYm3EjT6Hy"},
    },
    "web_emission": {
        "domain": "felav02.c.sat.gob.gt",
        "port": 443,
        "description": "API Web — Emisión/Anulación FEL",
        "health_path": "/fel-rest/",
        "method": "GET",
        "extra_headers": {},
    },
    "web_consulta": {
        "domain": "felcons.c.sat.gob.gt",
        "port": 443,
        "description": "API Web — Consulta/Descargas",
        "health_path": "/dte-agencia-virtual/api/",
        "method": "GET",
        "extra_headers": {},
    },
    "login_portal": {
        "domain": "farm3.sat.gob.gt",
        "port": 443,
        "description": "Portal Login (Agencia Virtual)",
        "health_path": "/menu/",
        "method": "GET",
        "extra_headers": {},
    },
}


def check_dns(domain: str) -> dict:
    """Resolve domain and return IPs + latency."""
    t0 = time.time()
    try:
        ips = socket.getaddrinfo(domain, 443, socket.AF_INET)
        unique_ips = list(set(addr[4][0] for addr in ips))
        return {
            "status": "ok",
            "ips": unique_ips,
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }
    except socket.gaierror as e:
        return {
            "status": "down",
            "error": str(e),
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }


def check_tls_connect(domain: str, port: int = 443, timeout: float = 10.0) -> dict:
    """TLS handshake check — verifies the server is accepting connections."""
    t0 = time.time()
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                latency = round((time.time() - t0) * 1000, 1)
                return {
                    "status": "ok",
                    "latency_ms": latency,
                    "tls_version": ssock.version(),
                    "cert_subject": dict(x[0] for x in cert.get("subject", [])),
                    "cert_expires": cert.get("notAfter", ""),
                }
    except (socket.timeout, ConnectionRefusedError, ssl.SSLError, OSError) as e:
        return {
            "status": "down",
            "error": str(e),
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }


def check_http(domain: str, path: str, method: str = "GET",
               extra_headers: dict = None, timeout: float = 10.0) -> dict:
    """Make an HTTP request and check response."""
    import urllib.request
    import urllib.error

    url = f"https://{domain}{path}"
    t0 = time.time()
    try:
        req = urllib.request.Request(url, method=method)
        req.add_header("User-Agent", "SAT-FEL-HealthCheck/1.0")
        if extra_headers:
            for k, v in extra_headers.items():
                req.add_header(k, v)

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body_bytes = resp.read(500)
            latency = round((time.time() - t0) * 1000, 1)
            return {
                "status": "ok" if status < 500 else "degraded",
                "http_status": status,
                "latency_ms": latency,
                "body_preview": body_bytes.decode("utf-8", errors="replace")[:200],
            }
    except urllib.error.HTTPError as e:
        latency = round((time.time() - t0) * 1000, 1)
        # 401/403/404 still means the server is UP and responding
        if e.code < 500:
            return {
                "status": "ok",
                "http_status": e.code,
                "latency_ms": latency,
                "note": f"Server responded with {e.code} (expected for unauthenticated health check)",
            }
        return {
            "status": "degraded",
            "http_status": e.code,
            "latency_ms": latency,
            "error": str(e),
        }
    except Exception as e:
        return {
            "status": "down",
            "error": str(e),
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }


def check_auth_mobile() -> dict:
    """Authenticated check: login + NIT lookup via mobile API."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "sat_fel_api_v5_cloud"))
        from dotenv import load_dotenv

        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv(Path(os.environ.get("SAT_ENV_FILE", "")))

        nit = os.environ.get("SAT_NIT", "")
        password = os.environ.get("SAT_PASSWORD", "") or os.environ.get("SAT_CLAVE", "")

        if not nit or not password:
            return {"status": "skipped", "reason": "No credentials in .env"}

        from sat_movil_api import SatMovilAPI, SatMovilAPIError

        api = SatMovilAPI()
        t0 = time.time()
        api.login(nit=nit, clave=password)
        login_ms = round((time.time() - t0) * 1000, 1)

        t1 = time.time()
        # Use the authenticated NIT itself for lookup (always exists)
        result = api.consultar_nit(nit)
        nit_ms = round((time.time() - t1) * 1000, 1)

        nombre = ""
        if isinstance(result, dict):
            nombre = result.get("nombre", result.get("NOMBRE", str(result)))
        else:
            nombre = str(result)

        return {
            "status": "ok",
            "login_ms": login_ms,
            "nit_lookup_ms": nit_ms,
            "nit_result": nombre,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def run_health_check(full: bool = False) -> dict:
    """Run all health checks and return results."""
    results = {
        "timestamp": datetime.now().isoformat(),
        "endpoints": {},
        "summary": {},
    }

    all_ok = True
    for name, cfg in ENDPOINTS.items():
        endpoint_result = {
            "description": cfg["description"],
            "domain": cfg["domain"],
        }

        # DNS check
        endpoint_result["dns"] = check_dns(cfg["domain"])

        # TLS connect
        endpoint_result["tls"] = check_tls_connect(cfg["domain"], cfg["port"])

        # HTTP check
        endpoint_result["http"] = check_http(
            cfg["domain"], cfg["health_path"],
            method=cfg["method"],
            extra_headers=cfg.get("extra_headers"),
        )

        # Overall status for this endpoint
        statuses = [
            endpoint_result["dns"]["status"],
            endpoint_result["tls"]["status"],
            endpoint_result["http"]["status"],
        ]
        if "down" in statuses:
            endpoint_result["overall"] = "DOWN"
            all_ok = False
        elif "degraded" in statuses:
            endpoint_result["overall"] = "DEGRADED"
        else:
            endpoint_result["overall"] = "OK"

        results["endpoints"][name] = endpoint_result

    # Authenticated check (optional)
    if full:
        results["auth_check"] = check_auth_mobile()
        if results["auth_check"]["status"] == "error":
            all_ok = False

    # Summary
    results["summary"] = {
        "all_healthy": all_ok,
        "mobile_api": results["endpoints"]["mobile_api"]["overall"],
        "web_emission": results["endpoints"]["web_emission"]["overall"],
        "web_consulta": results["endpoints"]["web_consulta"]["overall"],
        "login_portal": results["endpoints"]["login_portal"]["overall"],
        "failover_available": (
            results["endpoints"]["mobile_api"]["overall"] == "OK"
            or results["endpoints"]["web_emission"]["overall"] == "OK"
        ),
        "recommendation": _get_recommendation(results["endpoints"]),
    }

    return results


def _get_recommendation(endpoints: dict) -> str:
    """Generate a human-readable recommendation based on health status."""
    mobile_ok = endpoints["mobile_api"]["overall"] == "OK"
    web_ok = endpoints["web_emission"]["overall"] == "OK"
    consulta_ok = endpoints["web_consulta"]["overall"] == "OK"
    login_ok = endpoints["login_portal"]["overall"] == "OK"

    if mobile_ok and web_ok:
        return "All systems operational. Both APIs available for failover."
    elif mobile_ok and not web_ok:
        return "USE MOBILE API ONLY. Web API is down — mobile handles emission/annulment/queries."
    elif web_ok and not mobile_ok:
        return "USE WEB API ONLY. Mobile API is down — web handles everything (slower)."
    elif not mobile_ok and not web_ok:
        return "CRITICAL: Both emission APIs are down. No DTE operations possible."
    elif not login_ok and mobile_ok:
        return "Login portal down — web API unusable. Mobile API works independently (use it)."
    elif not consulta_ok and mobile_ok:
        return "Web consulta down (no XML/XLS exports). Mobile API handles PDF + listing."
    return "Partial outage detected. Check individual endpoint status."


def print_human_readable(results: dict):
    """Print results in a human-readable format."""
    print(f"\n{'='*60}")
    print(f"  SAT FEL Health Check — {results['timestamp']}")
    print(f"{'='*60}\n")

    for name, data in results["endpoints"].items():
        status_icon = {"OK": "✅", "DEGRADED": "⚠️", "DOWN": "❌"}.get(data["overall"], "❓")
        latency = data["http"].get("latency_ms", "?")
        ips = ", ".join(data["dns"].get("ips", []))
        print(f"  {status_icon} {data['description']}")
        print(f"     Domain: {data['domain']} → {ips}")
        print(f"     HTTP: {data['http'].get('http_status', '?')} ({latency}ms)")
        print()

    if "auth_check" in results:
        auth = results["auth_check"]
        if auth["status"] == "ok":
            print(f"  ✅ Auth check: login {auth['login_ms']}ms, NIT lookup {auth['nit_lookup_ms']}ms")
        elif auth["status"] == "skipped":
            print(f"  ⏭️  Auth check: {auth['reason']}")
        else:
            print(f"  ❌ Auth check: {auth.get('error', 'unknown error')}")
        print()

    summary = results["summary"]
    print(f"{'─'*60}")
    print(f"  Failover available: {'YES' if summary['failover_available'] else 'NO'}")
    print(f"  Recommendation: {summary['recommendation']}")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    full_mode = "--full" in sys.argv
    json_mode = "--json" in sys.argv

    results = run_health_check(full=full_mode)

    if json_mode:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_human_readable(results)

    # Exit code: 0 = all healthy, 1 = something down
    sys.exit(0 if results["summary"]["all_healthy"] else 1)
