"""Logging configuration — plain stdlib `logging`, not structlog/JSON.

That's a deliberate scope call, not an oversight: a consistent
timestamp+level+logger+message format with a per-request correlation id
(added by the middleware in `app/main.py`) covers what this project
actually needs (readable local/CI logs, traceable requests) without a new
dependency. Swapping the formatter for JSON output is the natural next
step if this ever sits behind a log aggregator (Loki, CloudWatch, etc.) —
noted here rather than built speculatively.
"""

import logging
import sys


def configure_logging(environment: str) -> None:
    level = logging.WARNING if environment.lower() == "production" else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z")
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Our own code always logs at INFO+ regardless of environment — the
    # WARNING floor above is for noisy third-party loggers (sqlalchemy.engine,
    # urllib3, etc.), not for app.* messages.
    logging.getLogger("app").setLevel(logging.INFO)
