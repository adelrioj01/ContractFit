from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from contractfit.api import (
    configure_processing,
    configure_store,
    get_store,
    router,
    seed_demo,
    seed_demo_identity,
)
from contractfit.config import get_settings
from contractfit.database import build_engine, build_session_factory
from contractfit.runtime import build_document_processor, build_processing_queue
from contractfit.sample_data import SAMPLE_PROFILE
from contractfit.sql_store import SqlAlchemyStore

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.storage_backend == "postgres":
        engine = build_engine(settings.database_url)
        configure_store(SqlAlchemyStore(build_session_factory(engine)))
    configure_processing(
        build_processing_queue(settings),
        build_document_processor(settings, get_store()),
    )
    if settings.seed_demo_data:
        if get_store().get_profile(SAMPLE_PROFILE.organization_id) is None:
            seed_demo()
        else:
            seed_demo_identity()
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
