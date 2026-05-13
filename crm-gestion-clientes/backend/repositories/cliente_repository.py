"""
Repositorio de Clientes — única capa que toca SQL.
Los servicios llaman a este repositorio; nunca escriben SQL directamente.
Todos los parámetros usan placeholders (?) para prevenir SQL injection.
"""
from typing import Optional
from backend.core.database import get_connection
from backend.models.cliente import Cliente


class ClienteRepository:

    # ── CREATE ───────────────────────────────────────────────────────────────
    def crear(self, datos: dict) -> Cliente:
        sql = """
            INSERT INTO clientes
                (nombre, apellidos, empresa, email, telefono, direccion,
                 ciudad, codigo_postal, pais, nif, tipo_cliente, activo, notas)
            VALUES
                (:nombre, :apellidos, :empresa, :email, :telefono, :direccion,
                 :ciudad, :codigo_postal, :pais, :nif, :tipo_cliente, :activo, :notas)
        """
        defaults = {
            "empresa": None, "telefono": None, "direccion": None,
            "ciudad": None, "codigo_postal": None, "pais": "España",
            "nif": None, "tipo_cliente": "particular", "activo": 1, "notas": None
        }
        defaults.update(datos)
        defaults["activo"] = 1 if defaults.get("activo", True) else 0

        with get_connection() as conn:
            cursor = conn.execute(sql, defaults)
            new_id = cursor.lastrowid
        return self.obtener_por_id(new_id)

    # ── READ — por ID ────────────────────────────────────────────────────────
    def obtener_por_id(self, cliente_id: int) -> Optional[Cliente]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM clientes WHERE id = ?", (cliente_id,)
            ).fetchone()
        return Cliente.from_row(row) if row else None

    # ── READ — por email ─────────────────────────────────────────────────────
    def obtener_por_email(self, email: str) -> Optional[Cliente]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM clientes WHERE email = ?", (email.lower(),)
            ).fetchone()
        return Cliente.from_row(row) if row else None

    # ── READ — listar con filtros opcionales ─────────────────────────────────
    def listar(
        self,
        solo_activos: bool = True,
        tipo_cliente: Optional[str] = None,
        ciudad: Optional[str] = None,
        busqueda: Optional[str] = None,
        limite: int = 100,
        offset: int = 0
    ) -> list[Cliente]:
        condiciones = []
        params: list = []

        if solo_activos:
            condiciones.append("activo = 1")

        if tipo_cliente:
            condiciones.append("tipo_cliente = ?")
            params.append(tipo_cliente)

        if ciudad:
            condiciones.append("ciudad LIKE ?")
            params.append(f"%{ciudad}%")

        if busqueda:
            condiciones.append("""
                (nombre LIKE ? OR apellidos LIKE ?
                 OR empresa LIKE ? OR email LIKE ?)
            """)
            termino = f"%{busqueda}%"
            params.extend([termino, termino, termino, termino])

        where = "WHERE " + " AND ".join(condiciones) if condiciones else ""
        sql = f"SELECT * FROM clientes {where} ORDER BY nombre ASC LIMIT ? OFFSET ?"
        params.extend([limite, offset])

        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [Cliente.from_row(r) for r in rows]

    # ── READ — total de registros ─────────────────────────────────────────────
    def contar(self, solo_activos: bool = True) -> int:
        where = "WHERE activo = 1" if solo_activos else ""
        with get_connection() as conn:
            return conn.execute(
                f"SELECT COUNT(*) FROM clientes {where}"
            ).fetchone()[0]

    # ── UPDATE ───────────────────────────────────────────────────────────────
    def actualizar(self, cliente_id: int, datos: dict) -> Optional[Cliente]:
        if not datos:
            return self.obtener_por_id(cliente_id)

        if "activo" in datos:
            datos["activo"] = 1 if datos["activo"] else 0

        columnas = ", ".join(f"{col} = ?" for col in datos)
        valores  = list(datos.values()) + [cliente_id]

        with get_connection() as conn:
            conn.execute(
                f"UPDATE clientes SET {columnas} WHERE id = ?", valores
            )
        return self.obtener_por_id(cliente_id)

    # ── DELETE lógico (desactivar) ────────────────────────────────────────────
    def desactivar(self, cliente_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.execute(
                "UPDATE clientes SET activo = 0 WHERE id = ?", (cliente_id,)
            )
        return cursor.rowcount > 0

    # ── DELETE físico (solo para tests / admin) ───────────────────────────────
    def eliminar_permanente(self, cliente_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM clientes WHERE id = ?", (cliente_id,)
            )
        return cursor.rowcount > 0

    # ── Verificar existencia de email (para duplicados) ───────────────────────
    def email_existe(self, email: str, excluir_id: Optional[int] = None) -> bool:
        sql    = "SELECT 1 FROM clientes WHERE email = ?"
        params = [email.lower()]
        if excluir_id:
            sql    += " AND id != ?"
            params.append(excluir_id)
        with get_connection() as conn:
            return conn.execute(sql, params).fetchone() is not None
