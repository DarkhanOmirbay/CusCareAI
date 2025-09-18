import logging
from logging import StreamHandler, FileHandler
from app.core.config import settings


formatter = logging.Formatter(
    fmt="%(asctime)s %(name)s:%(levelname)s:%(message)s",
    datefmt="%F %A %T"
)


file_handler = FileHandler(
    filename=settings.LOG_FILENAME,
    encoding="utf-8",
    mode="a+",
)

file_handler.setFormatter(formatter)


console_out = StreamHandler()
console_out.setFormatter(formatter)


root_logger = logging.getLogger()
root_logger.setLevel(settings.LOG_LEVEL.upper())
root_logger.addHandler(file_handler)
root_logger.addHandler(console_out)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai._base_client").setLevel(logging.WARNING)

logger = logging.getLogger("chatbot")
logger.setLevel(settings.LOG_LEVEL.upper())
logger.addHandler(file_handler)
