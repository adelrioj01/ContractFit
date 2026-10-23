from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from contractfit.api import router, seed_demo
from contractfit.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    seed_demo()
    yield


app = FastAPI(
    title="ContractFit API",
    version="0.1.0",
    description="Evidence-grounded government opportunity matching for facilities contractors.",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    dashboard_path = Path(__file__).with_name("static") / "index.html"
    return FileResponse(dashboard_path)
