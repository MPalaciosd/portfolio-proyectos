"""
Configuración centralizada del sistema.
Lee variables de entorno con valores por defecto para desarrollo.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Config:
    # Base de datos
    DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "data" / "database" / "crm.db"))

    # Logging
    LOG_DIR: str = os.getenv("LOG_DIR", str(BASE_DIR / "logs" / "app"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Aplicación
    APP_NAME: str = "CRM-ASIR"
    VERSION: str = "1.0.0"

config = Config()
