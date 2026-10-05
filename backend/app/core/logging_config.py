"""
Structured logging setup.

Emits JSON log lines in non-local environments (so they're ingestible by
any log aggregator) and human-readable lines locally. Every request gets
a correlation id attached (see middleware.py) so a single transaction's
logs can be traced end to end — important for an auditable financial
system, not just convenience.
"""
import json
import logging
import sys
from datetime import datetime, timezone

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            payload["user_id"] = record.user_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)

    handler = logging.StreamHandler(sys.stdout)
    if settings.LOG_JSON and settings.ENVIRONMENT != "local":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        )

    root.handlers = [handler]

    # Quiet noisy third-party loggers at DEBUG.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
