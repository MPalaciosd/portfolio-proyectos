"""
Logger centralizado con rotación diaria de archivos.
Todos los módulos importan desde aquí.
"""
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from backend.core.config import config

os.makedirs(config.LOG_DIR, exist_ok=True)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Evita duplicar handlers si ya fue configurado

    logger.setLevel(config.LOG_LEVEL)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Handler consola
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # Handler archivo con rotación diaria, guarda 90 días
    log_file = os.path.join(config.LOG_DIR, "app.log")
    file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", backupCount=90, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
