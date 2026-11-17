from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import Engine, text

from contractfit.config import Settings, get_settings
from contractfit.database import build_engine, build_session_factory
from contractfit.sam_ingestion import SamOpportunitiesClient
from contractfit.sam_models import SamIngestionRun
from contractfit.sam_sync import SamIngestionService, SamSyncError
from contractfit.sql_store import SqlAlchemyStore

logger = logging.getLogger(__name__)
SAM_SYNC_ADVISORY_LOCK_ID = 0x434F4E5452414354


class SamSyncAlreadyRunning(RuntimeError):
    """Raised when another process owns the global SAM synchronization lock."""


@contextmanager
def sam_sync_lock(engine: Engine) -> Iterator[None]:
    """Prevent scheduler and one-shot SAM imports from overlapping in PostgreSQL."""

    with engine.connect() as connection:
        acquired: bool = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": SAM_SYNC_ADVISORY_LOCK_ID},
            ).scalar_one()
        )
        if not acquired:
            raise SamSyncAlreadyRunning("another SAM.gov synchronization is already running")
        try:
            yield
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": SAM_SYNC_ADVISORY_LOCK_ID},
            )


def synchronize_once(settings: Settings) -> SamIngestionRun:
    """Run one persisted SAM.gov synchronization for the configured lookback window."""

    if settings.storage_backend != "postgres":
        raise RuntimeError("SAM synchronization requires STORAGE_BACKEND=postgres")
    if not settings.sam_api_key or not settings.sam_api_key.strip():
        raise RuntimeError("SAM synchronization requires SAM_API_KEY")

    engine = build_engine(settings.database_url)
    with sam_sync_lock(engine):
        store = SqlAlchemyStore(build_session_factory(engine))
        today = datetime.now(UTC).date()
        posted_from = today - timedelta(days=settings.sam_lookback_days - 1)
        with httpx.Client() as http_client:
            source = SamOpportunitiesClient(
                http_client,
                api_key=settings.sam_api_key,
                timeout_seconds=settings.sam_request_timeout_seconds,
            )
            return SamIngestionService(
                source,
                store,
                page_size=settings.sam_page_size,
            ).synchronize(posted_from=posted_from, posted_to=today)


def run_scheduler(settings: Settings) -> None:
    if not settings.sam_sync_enabled:
        raise RuntimeError("Scheduled SAM synchronization requires SAM_SYNC_ENABLED=true")

    delay_seconds = settings.sam_sync_interval_minutes * 60
    while True:
        try:
            run = synchronize_once(settings)
            logger.info(
                "SAM sync completed: run=%s fetched=%s created=%s updated=%s unchanged=%s",
                run.id,
                run.records_fetched,
                run.created_count,
                run.updated_count,
                run.unchanged_count,
            )
        except SamSyncError as exc:
            logger.error("SAM sync failed: %s", exc)
        except Exception:
            logger.exception("SAM scheduler could not start a synchronization")
        time.sleep(delay_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize SAM.gov opportunities")
    parser.add_argument(
        "--once",
        action="store_true",
        help="run once even when scheduled synchronization is disabled",
    )
    args = parser.parse_args()
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    if args.once:
        run = synchronize_once(settings)
        logger.info("SAM sync completed: run=%s fetched=%s", run.id, run.records_fetched)
        return
    run_scheduler(settings)


if __name__ == "__main__":
    main()
