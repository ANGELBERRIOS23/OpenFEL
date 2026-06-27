import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.schemas.health import HealthResponse, ServerStatus

router = APIRouter(tags=["Health"])


@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    from backend.sat.health_check import run_health_check
    result = await asyncio.to_thread(run_health_check, False)

    servers = []
    for key, s in result.get("endpoints", {}).items():
        dns_ok = s.get("dns", {}).get("status") == "ok"
        tls_ok = s.get("tls", {}).get("status") == "ok"
        http_ok = s.get("http", {}).get("status") == "ok"
        http_latency = s.get("http", {}).get("latency_ms")
        ips = s.get("dns", {}).get("ips", [])

        servers.append(ServerStatus(
            server=s.get("description", key),
            domain=s.get("domain", ""),
            ip=ips[0] if ips else None,
            dns=dns_ok,
            tls=tls_ok,
            http=http_ok,
            latency_ms=int(http_latency) if http_latency else None,
            status="online" if http_ok else "offline",
        ))

    all_ok = all(s.status == "online" for s in servers)
    some_ok = any(s.status == "online" for s in servers)
    overall = "healthy" if all_ok else ("degraded" if some_ok else "down")

    return HealthResponse(
        overall=overall,
        servers=servers,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
