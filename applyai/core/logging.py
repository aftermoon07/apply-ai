"""Logging setup — configures root and applyai loggers from logging.yaml."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path

import yaml

_configured = False

PROJECT_ROOT = Path(__file__).parent.parent.parent


def setup_logging(
    config_path: Path | None = None,
    log_level: str = "INFO",
    log_dir: Path | None = None,
) -> None:
    """
    Configure logging from logging.yaml.

    Falls back to a basic rich console handler if the file is missing.
    Idempotent — safe to call multiple times.
    """
    global _configured
    if _configured:
        return

    resolved = config_path or (PROJECT_ROOT / "config" / "logging.yaml")

    # Ensure the logs directory exists if file logging is configured
    logs_dir = log_dir or (PROJECT_ROOT / "logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    if resolved.exists():
        with open(resolved, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        logging.config.dictConfig(cfg)
    else:
        # Minimal fallback
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        )

    # Apply runtime log level from env/settings
    logging.getLogger("applyai").setLevel(log_level.upper())
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger scoped to the applyai namespace."""
    if not name.startswith("applyai"):
        name = f"applyai.{name}"
    return logging.getLogger(name)
