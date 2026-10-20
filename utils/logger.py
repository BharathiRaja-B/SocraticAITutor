"""
utils/logger.py — centralized logging configuration
"""
import logging
import sys

LOG_LEVEL = logging.DEBUG

logger = logging.getLogger("tutor")
logger.setLevel(LOG_LEVEL)

# Console handler
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(LOG_LEVEL)

# Formatter
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
ch.setFormatter(formatter)

# Avoid duplicate handlers if module reloaded
if not logger.handlers:
    logger.addHandler(ch)

# Convenience
def get_logger(name: str = None):
    return logger if name is None else logger.getChild(name)
