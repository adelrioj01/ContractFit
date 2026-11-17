"""Scheduled alert materialization and optional SMTP delivery."""

import logging
import time

from contractfit.config import get_settings
from contractfit.database import build_engine, build_session_factory
from contractfit.notifications import SmtpEmailSender, dispatch_pending, materialize_deliveries
from contractfit.sql_store import SqlAlchemyStore
from contractfit.watching import refresh_opportunity_alerts

logger = logging.getLogger(__name__)


def process_once(store: SqlAlchemyStore, sender: SmtpEmailSender | None) -> None:
    for preference in store.list_notification_preferences(enabled_only=True):
        refresh_opportunity_alerts(store, preference.organization_id)
        materialize_deliveries(store, preference)
    if sender is not None:
        dispatch_pending(store, sender)


def run_worker() -> None:
    settings = get_settings()
    store = SqlAlchemyStore(build_session_factory(build_engine(settings.database_url)))
    sender = (
        SmtpEmailSender(settings.smtp_host, settings.smtp_port, settings.notification_from_email)
        if settings.notification_send_enabled and settings.smtp_host
        else None
    )
    while True:
        try:
            process_once(store, sender)
        except Exception:
            logger.exception("Notification cycle failed")
        time.sleep(settings.notification_poll_seconds)


if __name__ == "__main__":
    run_worker()
