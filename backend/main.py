import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import init_db

logger = logging.getLogger("openfel")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    logger.info("OpenFEL starting...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("OpenFEL shutting down")


app = FastAPI(
    title="OpenFEL",
    description="Multi-account SAT Guatemala FEL platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.routes import api_keys, accounts, dte, health, logs

app.include_router(health.router)
app.include_router(api_keys.router)
app.include_router(accounts.router)
app.include_router(dte.router)
app.include_router(logs.router)

dashboard_dist = Path(__file__).parent.parent / "dashboard" / "dist"
if dashboard_dist.exists():
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=str(dashboard_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        file_path = dashboard_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(dashboard_dist / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
