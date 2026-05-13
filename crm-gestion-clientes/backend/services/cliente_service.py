"""
Servicio de Clientes — lógica de negocio central.
Orquesta validación → repositorio → logging.
Es la única capa que los controladores/CLI deben llamar.
"""
from typing import Optional
from backend.models.cliente import Cliente
from backend.repositories.cliente_repository import ClienteRepository
from backend.schemas.cliente_schema import validar_cliente
from backend.core.exceptions import ClienteNoEncontrado, ClienteDuplicado
from backend.core.logger import get_logger

logger = get_logger(__name__)
_repo  = ClienteRepository()


class ClienteService:

    # ── CREAR ─────────────────────────────────────────────────────────────────
    def crear_cliente(self, datos: dict) -> Cliente:
        """
        Crea un nuevo cliente.
        Lanza ValidacionError si los datos son incorrectos.
        Lanza ClienteDuplicado si el email ya existe.
        """
        validar_cliente(datos)

        if _repo.email_existe(datos["email"]):
            raise ClienteDuplicado(datos["email"])

        cliente = _repo.crear(datos)
        logger.info("Cliente creado | id=%s | email=%s", cliente.id, cliente.email)
        return cliente

    # ── OBTENER POR ID ────────────────────────────────────────────────────────
    def obtener_cliente(self, cliente_id: int) -> Cliente:
        cliente = _repo.obtener_por_id(cliente_id)
        if not cliente:
            raise ClienteNoEncontrado(cliente_id)
        return cliente

    # ── OBTENER POR EMAIL ─────────────────────────────────────────────────────
    def obtener_por_email(self, email: str) -> Cliente:
        cliente = _repo.obtener_por_email(email)
        if not cliente:
            raise ClienteNoEncontrado(email)
        return cliente

    # ── LISTAR ────────────────────────────────────────────────────────────────
    def listar_clientes(
        self,
        solo_activos: bool = True,
        tipo_cliente: Optional[str] = None,
        ciudad: Optional[str] = None,
        busqueda: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 20,
    ) -> dict:
        """
        Devuelve clientes paginados con metadatos de paginación.
        """
        offset   = (pagina - 1) * por_pagina
        clientes = _repo.listar(
            solo_activos=solo_activos,
            tipo_cliente=tipo_cliente,
            ciudad=ciudad,
            busqueda=busqueda,
            limite=por_pagina,
            offset=offset,
        )
        total = _repo.contar(solo_activos=solo_activos)
        return {
            "clientes":   clientes,
            "total":      total,
            "pagina":     pagina,
            "por_pagina": por_pagina,
            "paginas":    -(-total // por_pagina),  # ceil division
        }

    # ── ACTUALIZAR ────────────────────────────────────────────────────────────
    def actualizar_cliente(self, cliente_id: int, datos: dict) -> Cliente:
        """
        Actualización parcial: solo modifica los campos enviados.
        Lanza ClienteNoEncontrado si el ID no existe.
        Lanza ClienteDuplicado si el nuevo email ya lo usa otro cliente.
        """
        if not _repo.obtener_por_id(cliente_id):
            raise ClienteNoEncontrado(cliente_id)

        validar_cliente(datos, es_actualizacion=True)

        if "email" in datos and _repo.email_existe(datos["email"], excluir_id=cliente_id):
            raise ClienteDuplicado(datos["email"])

        cliente = _repo.actualizar(cliente_id, datos)
        logger.info("Cliente actualizado | id=%s | campos=%s", cliente_id, list(datos.keys()))
        return cliente

    # ── DESACTIVAR (baja lógica) ──────────────────────────────────────────────
    def desactivar_cliente(self, cliente_id: int) -> None:
        if not _repo.obtener_por_id(cliente_id):
            raise ClienteNoEncontrado(cliente_id)
        _repo.desactivar(cliente_id)
        logger.info("Cliente desactivado | id=%s", cliente_id)

    # ── REACTIVAR ─────────────────────────────────────────────────────────────
    def reactivar_cliente(self, cliente_id: int) -> Cliente:
        if not _repo.obtener_por_id(cliente_id):
            raise ClienteNoEncontrado(cliente_id)
        cliente = _repo.actualizar(cliente_id, {"activo": True})
        logger.info("Cliente reactivado | id=%s", cliente_id)
        return cliente

    # ── ELIMINAR PERMANENTE ───────────────────────────────────────────────────
    def eliminar_cliente(self, cliente_id: int) -> None:
        """Eliminación física. Usar solo en casos justificados (RGPD, etc.)."""
        if not _repo.obtener_por_id(cliente_id):
            raise ClienteNoEncontrado(cliente_id)
        _repo.eliminar_permanente(cliente_id)
        logger.warning("Cliente ELIMINADO permanentemente | id=%s", cliente_id)

    # ── ESTADÍSTICAS ──────────────────────────────────────────────────────────
    def estadisticas(self) -> dict:
        from backend.core.database import get_connection
        with get_connection() as conn:
            stats = {}
            stats["total_activos"]   = conn.execute(
                "SELECT COUNT(*) FROM clientes WHERE activo = 1"
            ).fetchone()[0]
            stats["total_inactivos"] = conn.execute(
                "SELECT COUNT(*) FROM clientes WHERE activo = 0"
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT tipo_cliente, COUNT(*) as n FROM clientes WHERE activo=1 GROUP BY tipo_cliente"
            ).fetchall()
            stats["por_tipo"] = {r["tipo_cliente"]: r["n"] for r in rows}
            rows = conn.execute(
                "SELECT ciudad, COUNT(*) as n FROM clientes WHERE activo=1 AND ciudad IS NOT NULL "
                "GROUP BY ciudad ORDER BY n DESC LIMIT 5"
            ).fetchall()
            stats["top_ciudades"] = {r["ciudad"]: r["n"] for r in rows}
        return stats
