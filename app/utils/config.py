import logging
import os

from dotenv import load_dotenv

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

logger = logging.getLogger(__name__)

env_file_loaded = load_dotenv()
logger.info(".env loaded: %s", env_file_loaded)


BOT_TOKEN = os.getenv("BOT_TOKEN", "")


def _get_positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        logger.warning("Invalid %s value; using %s", name, default)
        return default
    return value if value > 0 else default


ALERT_CHECK_INTERVAL_SECONDS = _get_positive_int("ALERT_CHECK_INTERVAL_SECONDS", 60)
