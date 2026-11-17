import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse

from contractfit.api import (
    configure_processing,
    configure_store,
    get_store,
    router,
    seed_demo,
    seed_demo_companies,
    seed_synthetic_catalog,
)
from contractfit.config import get_settings
from contractfit.database import build_engine, build_session_factory
from contractfit.runtime import build_document_processor, build_processing_queue
from contractfit.sample_data import SAMPLE_PROFILE
from contractfit.sql_store import SqlAlchemyStore

settings = get_settings()
logger = logging.getLogger(__name__)


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
            seed_demo_companies()
            seed_synthetic_catalog()
    yield


app = FastAPI(
    title="ContractFit API",
    version="0.1.0",
    description="Evidence-grounded government opportunity matching for facilities contractors.",
    lifespan=lifespan,
)
app.include_router(router)


@app.middleware("http")
async def log_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("x-request-id") or str(uuid4())
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed",
            extra={"request_id": request_id, "method": request.method, "path": request.url.path},
        )
        raise
    duration_ms = round((perf_counter() - started) * 1000, 3)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    dashboard_path = Path(__file__).with_name("static") / "index.html"
    return FileResponse(dashboard_path)
