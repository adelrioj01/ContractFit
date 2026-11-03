"""Deterministic test configuration independent of the invocation directory."""

import os

# Pydantic settings load ``.env`` relative to the process working directory. Explicit
# test values prevent the repository-level Docker configuration from changing unit-test
# behavior when pytest is launched from the repository root. Integration runs can opt in
# to their external environment deliberately.
if os.getenv("CONTRACTFIT_TEST_USE_EXTERNAL_ENV") != "1":
    os.environ["APP_ENV"] = "test"
    os.environ["STORAGE_BACKEND"] = "memory"
    os.environ["PROCESSING_MODE"] = "inline"
    os.environ["OCR_BACKEND"] = "disabled"
    os.environ["SAM_SYNC_ENABLED"] = "false"
    os.environ["NOTIFICATION_SEND_ENABLED"] = "false"
