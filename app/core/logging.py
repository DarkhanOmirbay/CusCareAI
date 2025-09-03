import logging
from logging import StreamHandler, FileHandler
from app.core.config import settings

# Общие форматтеры
formatter = logging.Formatter(
    fmt="%(asctime)s %(name)s:%(levelname)s:%(message)s",
    datefmt="%F %A %T"
)

# Хендлер для файла
file_handler = FileHandler(
    filename=settings.LOG_FILENAME,
    encoding="utf-8",
    mode="a",
)
file_handler.setFormatter(formatter)

# Хендлер для консоли
console_out = StreamHandler()
console_out.setFormatter(formatter)

# Root logger (главный)
root_logger = logging.getLogger()
root_logger.setLevel(settings.LOG_LEVEL.upper())
root_logger.addHandler(file_handler)
root_logger.addHandler(console_out)

# Твой именованный логгер
logger = logging.getLogger("chatbot")
