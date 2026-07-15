"""Central logging setup. Import `get_logger(__name__)` anywhere instead
of calling `logging.getLogger` directly, so log format stays consistent."""
import logging
import sys

_CONFIGURED = False


def _configure():
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(name)
