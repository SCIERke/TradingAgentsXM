"""Persistent rotating error/warning logger for the trade pipeline."""
from __future__ import annotations
import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_PATH = os.path.expanduser("~/.tradingagents/errors.log")
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 2


def get_run_logger(name: str = "tradingagents.trade") -> logging.Logger:
    """Return a logger that writes warnings+ to ~/.tradingagents/errors.log."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
    handler = RotatingFileHandler(
        _LOG_PATH, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setLevel(logging.WARNING)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    return logger
