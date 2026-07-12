import logging
import os

from dotenv import load_dotenv

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

logger = logging.getLogger(__name__)

env_file_loaded = load_dotenv()
logger.info(".env loaded: %s", env_file_loaded)


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
