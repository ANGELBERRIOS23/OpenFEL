import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.schemas.health import HealthResponse, ServerStatus

router = APIRouter(tags=["Health"])


@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    from backend.sat.health_check import run_health_check
    result = await asyncio.to_thread(run_health_check, full=False)

    servers = []
    for s in result.get("servers", []):
        servers.append(ServerStatus(
            server=s.get("name", ""),
            domain=s.get("domain", ""),
            ip=s.get("ip"),
            dns=s.get("dns", False),
            tls=s.get("tls", False),
            http=s.get("http", False),
            latency_ms=s.get("latency_ms"),
            status="online" if s.get("http") else "offline",
        ))

    all_ok = all(s.status == "online" for s in servers)
    some_ok = any(s.status == "online" for s in servers)
    overall = "healthy" if all_ok else ("degraded" if some_ok else "down")

    return HealthResponse(
        overall=overall,
        servers=servers,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
