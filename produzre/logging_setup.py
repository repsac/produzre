"""Logging configuration helpers for Produzre.

Produzre uses a single named logger ("produzre") across the codebase.
This module configures consistent console and optional file logging for CLI and
programmatic usage.

Conventions:
- Console logs use a compact format suitable for terminal output.
- File logs (when enabled) include timestamps and logger name for debugging.
- All handlers are cleared when configuring to avoid duplicate logs in tests.
"""

import logging
import pathlib
from typing import Optional


def configure_logging(
    verbose: bool = False,
    log_file: Optional[pathlib.Path] = None,
) -> logging.Logger:
    """Configure the Produzre logger.

    This function sets up the named `logging.Logger` used throughout Produzre
    ("produzre") and attaches:

    - A console handler at INFO level by default (DEBUG when `verbose=True`).
    - An optional file handler at DEBUG level when `log_file` is provided.

    The logger is always set to DEBUG so handler levels control what is emitted.

    Duplicate-handlers protection:
        Existing handlers are cleared each time this function is called. This is
        particularly helpful for test runs and for repeated CLI invocations in a
        single Python process.

    Args:
        verbose: If True, console logs are emitted at DEBUG level.
        log_file: Optional path to a log file to write detailed DEBUG logs.

    Returns:
        logging.Logger: Configured Produzre logger instance.
    """
    logger = logging.getLogger("produzre")
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers (helpful when running tests)
    logger.handlers.clear()

    console_level = logging.DEBUG if verbose else logging.INFO
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    if log_file is not None:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(fh)

    return logger
