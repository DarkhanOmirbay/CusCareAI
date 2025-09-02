import logging
from logging import getLogger,StreamHandler,FileHandler,basicConfig
from app.core.config import settings


logger = getLogger(__name__)
console_out = StreamHandler()

file_handler = FileHandler(
    filename=settings.LOG_FILENAME,
    encoding="utf-8",
    mode="a",
)

FORMAT = "%(asctime)s %(name)s:%(levelname)s:%(message)s"
DATEFMT="%F %A %T"

basicConfig(handlers=[file_handler,console_out],
                    format=FORMAT,
                    datefmt=DATEFMT,
                    level=settings.LOG_LEVEL.upper(),
                    )