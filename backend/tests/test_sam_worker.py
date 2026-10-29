from unittest.mock import MagicMock

import pytest

from contractfit.sam_worker import SamSyncAlreadyRunning, sam_sync_lock


def test_sam_sync_lock_releases_postgres_advisory_lock() -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = True

    with sam_sync_lock(engine):
        pass

    assert connection.execute.call_count == 2
    assert "pg_try_advisory_lock" in str(connection.execute.call_args_list[0].args[0])
    assert "pg_advisory_unlock" in str(connection.execute.call_args_list[1].args[0])


def test_sam_sync_lock_rejects_overlapping_run() -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = False

    with pytest.raises(
        SamSyncAlreadyRunning, match="already running"
    ), sam_sync_lock(engine):
        pass

    assert connection.execute.call_count == 1
