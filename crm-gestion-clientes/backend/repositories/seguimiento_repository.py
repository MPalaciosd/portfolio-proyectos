"""
Repositorio de seguimientos — única capa que accede a SQL.
Gestiona la tabla 'seguimientos' y la columna 'estado_comercial' en 'clientes'.
"""
from typing import Optional
from backend.core.database import get_connection
from backend.models.seguimiento import EstadoCliente, RegistroSeguimiento, TipoAccion

# SQL de creación de tablas (se llama desde database.py al ampliar el esquema)
SCHEMA_SEGUIMIENTO = """
CREATE TABLE IF NOT EXISTS seguimientos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id       INTEGER NOT NULL REFERENCES clientes(id),
    estado           TEXT    NOT NULL,
    tipo_contacto    TEXT    NOT NULL,
    descripcion      TEXT,
    resultado        TEXT    DEFAULT 'neutro'
        CHECK(resultado IN ('positivo','negativo','neutro','sin_respuesta')),
    usuario          TEXT    DEFAULT 'sistema',
    proximo_contacto TEXT,
    fecha            TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_seg_cliente ON seguimientos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_seg_fecha   ON seguimientos(fecha);

-- Columnas de seguimiento en la tabla clientes
-- (ALTER TABLE ignorado si ya existen)
"""

ALTERS_CLIENTES = [
    "ALTER TABLE clientes ADD COLUMN estado_comercial TEXT DEFAULT 'nuevo'",
    "ALTER TABLE clientes ADD COLUMN fecha_ultimo_contacto TEXT",
    "ALTER TABLE clientes ADD COLUMN fecha_cambio_estado   TEXT",
    "ALTER TABLE clientes ADD COLUMN score_interes         INTEGER DEFAULT 0",
]


def init_seguimiento_schema() -> None:
    """Amplía el esquema con las tablas de seguimiento."""
    with get_connection() as conn:
        conn.executescript(SCHEMA_SEGUIMIENTO)
        for alter in ALTERS_CLIENTES:
            try:
                conn.execute(alter)
            except Exception:
                pass  # Columna ya existe — ignorar


class SeguimientoRepository:

    # ── Registros de seguimiento ──────────────────────────────────────────────

    def registrar(self, seg: RegistroSeguimiento) -> int:
        sql = """
            INSERT INTO seguimientos
                (cliente_id, estado, tipo_contacto, descripcion,
                 resultado, usuario, proximo_contacto)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with get_connection() as conn:
            cur = conn.execute(sql, (
                seg.cliente_id, seg.estado.value, seg.tipo_contacto.value,
                seg.descripcion, seg.resultado, seg.usuario, seg.proximo_contacto,
            ))
            new_id = cur.lastrowid
        return new_id

    def historial_cliente(self, cliente_id: int, limite: int = 50) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM seguimientos
                   WHERE cliente_id = ?
                   ORDER BY fecha DESC LIMIT ?""",
                (cliente_id, limite),
            ).fetchall()
        return [dict(r) for r in rows]

    def ultimo_contacto(self, cliente_id: int) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM seguimientos
                   WHERE cliente_id = ?
                   ORDER BY fecha DESC LIMIT 1""",
                (cliente_id,),
            ).fetchone()
        return dict(row) if row else None

    def total_contactos(self, cliente_id: int) -> int:
        with get_connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM seguimientos WHERE cliente_id = ?",
                (cliente_id,),
            ).fetchone()[0]

    # ── Estado comercial en tabla clientes ────────────────────────────────────

    def actualizar_estado(
        self,
        cliente_id: int,
        nuevo_estado: EstadoCliente,
        score: Optional[int] = None,
    ) -> None:
        campos = {
            "estado_comercial":   nuevo_estado.value,
            "fecha_cambio_estado": "datetime('now','localtime')",
            "fecha_ultimo_contacto": "datetime('now','localtime')",
        }
        if score is not None:
            campos["score_interes"] = str(score)

        sets  = ", ".join(
            f"{k} = {v}" if "datetime" in str(v) else f"{k} = ?"
            for k, v in campos.items()
        )
        vals  = [v for v in campos.values() if "datetime" not in str(v)]
        vals.append(cliente_id)

        with get_connection() as conn:
            conn.execute(f"UPDATE clientes SET {sets} WHERE id = ?", vals)

    def estado_cliente(self, cliente_id: int) -> Optional[dict]:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT estado_comercial, fecha_ultimo_contacto,
                          fecha_cambio_estado, score_interes,
                          nombre, apellidos, empresa, email
                   FROM clientes WHERE id = ?""",
                (cliente_id,),
            ).fetchone()
        return dict(row) if row else None

    # ── Consultas de análisis masivo (para el motor de reglas) ────────────────

    def clientes_por_estado(self, estado: EstadoCliente) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT id, nombre, apellidos, empresa, email,
                          estado_comercial, fecha_ultimo_contacto,
                          fecha_cambio_estado, score_interes
                   FROM clientes
                   WHERE estado_comercial = ? AND activo = 1""",
                (estado.value,),
            ).fetchall()
        return [dict(r) for r in rows]

    def clientes_sin_contacto_desde(self, dias: int) -> list[dict]:
        """Clientes activos cuyo último contacto fue hace más de N días."""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT id, nombre, apellidos, empresa, email,
                          estado_comercial, fecha_ultimo_contacto,
                          fecha_cambio_estado, score_interes
                   FROM clientes
                   WHERE activo = 1
                     AND (
                         fecha_ultimo_contacto IS NULL
                         OR julianday('now') - julianday(fecha_ultimo_contacto) > ?
                     )
                     AND estado_comercial NOT IN ('cerrado_ganado','cerrado_perdido')""",
                (dias,),
            ).fetchall()
        return [dict(r) for r in rows]

    def dias_en_estado(self, cliente_id: int) -> int:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT CAST(julianday('now') - julianday(fecha_cambio_estado) AS INTEGER)
                   FROM clientes WHERE id = ?""",
                (cliente_id,),
            ).fetchone()
        return row[0] if (row and row[0] is not None) else 0

    def dias_sin_contacto(self, cliente_id: int) -> int:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT CAST(julianday('now') - julianday(fecha_ultimo_contacto) AS INTEGER)
                   FROM clientes WHERE id = ?""",
                (cliente_id,),
            ).fetchone()
        return row[0] if (row and row[0] is not None) else 999
