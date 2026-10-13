"""Logging to the console and to the game's log file."""
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

LOGGER_NAME = "lottery"


@contextmanager
def logging_to(log_file: Path) -> Iterator[logging.Logger]:
    """Sends the package's messages to stdout and, with a timestamp, to log_file (append-only)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(message)s"))
    file = logging.FileHandler(log_file, encoding="utf-8")
    file.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handlers = (console, file)
    for handler in handlers:
        logger.addHandler(handler)
    try:
        yield logger
    finally:
        for handler in handlers:
            logger.removeHandler(handler)
            handler.close()
