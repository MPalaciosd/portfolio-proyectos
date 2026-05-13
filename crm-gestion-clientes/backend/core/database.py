"""
Gestión de conexiones SQLite.
Crea la base de datos y todas las tablas automáticamente si no existen.
"""
import sqlite3
import os
from backend.core.config import config
from backend.core.logger import get_logger

logger = get_logger(__name__)

# SQL de creación del esquema completo
SCHEMA_SQL = """
-- Tabla principal de clientes
CREATE TABLE IF NOT EXISTS clientes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL,
    apellidos       TEXT    NOT NULL,
    empresa         TEXT,
    email           TEXT    NOT NULL UNIQUE,
    telefono        TEXT,
    direccion       TEXT,
    ciudad          TEXT,
    codigo_postal   TEXT,
    pais            TEXT    DEFAULT 'España',
    nif             TEXT    UNIQUE,
    tipo_cliente    TEXT    DEFAULT 'particular'  -- particular | empresa | autonomo
        CHECK(tipo_cliente IN ('particular', 'empresa', 'autonomo')),
    activo          INTEGER DEFAULT 1             -- 1=activo, 0=inactivo
        CHECK(activo IN (0, 1)),
    notas           TEXT,
    fecha_alta      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    fecha_modificacion TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Índices para búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_clientes_email    ON clientes(email);
CREATE INDEX IF NOT EXISTS idx_clientes_empresa  ON clientes(empresa);
CREATE INDEX IF NOT EXISTS idx_clientes_activo   ON clientes(activo);
CREATE INDEX IF NOT EXISTS idx_clientes_ciudad   ON clientes(ciudad);

-- Trigger: actualiza fecha_modificacion automáticamente en cada UPDATE
CREATE TRIGGER IF NOT EXISTS trg_clientes_modificacion
AFTER UPDATE ON clientes
BEGIN
    UPDATE clientes
    SET fecha_modificacion = datetime('now', 'localtime')
    WHERE id = NEW.id;
END;
"""

def get_connection() -> sqlite3.Connection:
    """
    Devuelve una conexión a SQLite con row_factory para acceder
    a columnas por nombre (conn["email"] en vez de conn[2]).
    """
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")   # Activar integridad referencial
    conn.execute("PRAGMA journal_mode = WAL")  # Mejor concurrencia en lectura
    return conn

def init_db() -> None:
    """Crea el esquema si no existe. Seguro llamarlo en cada arranque."""
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
    logger.info("Base de datos inicializada: %s", config.DB_PATH)
