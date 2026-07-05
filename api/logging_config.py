"""Shared logging setup for the FastAPI backend."""

from __future__ import annotations

import logging
import os
import sys

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

_QUIET_LOGGERS = (
    "httpx",
    "httpcore",
    "chromadb",
    "sentence_transformers",
    "urllib3",
)


def setup_logging() -> None:
    """Configure root logging from LOG_LEVEL (default INFO)."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
        root.addHandler(handler)
    root.setLevel(level)

    if level > logging.DEBUG:
        for name in _QUIET_LOGGERS:
            logging.getLogger(name).setLevel(logging.WARNING)
