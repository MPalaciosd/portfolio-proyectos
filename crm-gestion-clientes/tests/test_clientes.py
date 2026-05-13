"""
Tests del sistema de gestión de clientes.
Usa una base de datos temporal en memoria para cada test.
Ejecutar: python -m pytest tests/test_clientes.py -v
"""
import os
import pytest

# Apuntar a DB en memoria antes de importar nada del backend
os.environ["DB_PATH"] = ":memory:"

from backend.core.database import init_db
from backend.services.cliente_service import ClienteService
from backend.core.exceptions import (
    ClienteNoEncontrado, ClienteDuplicado, ValidacionError
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_db(monkeypatch, tmp_path):
    """Crea un DB temporal limpia antes de cada test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)

    # Recargar config y database con el nuevo path
    import importlib
    import backend.core.config as cfg_mod
    import backend.core.database as db_mod

    cfg_mod.config.DB_PATH = db_path
    importlib.reload(db_mod)
    db_mod.init_db()

@pytest.fixture
def servicio():
    return ClienteService()

@pytest.fixture
def datos_validos():
    return {
        "nombre":       "Ana",
        "apellidos":    "García López",
        "email":        "ana.garcia@empresa.com",
        "telefono":     "+34 612 345 678",
        "empresa":      "Tech Solutions S.L.",
        "tipo_cliente": "empresa",
        "ciudad":       "Madrid",
        "codigo_postal": "28001",
        "nif":          "B12345678",
    }

# ── Tests de CREACIÓN ─────────────────────────────────────────────────────────

class TestCrearCliente:

    def test_crear_cliente_valido(self, servicio, datos_validos):
        cliente = servicio.crear_cliente(datos_validos)
        assert cliente.id is not None
        assert cliente.email == "ana.garcia@empresa.com"
        assert cliente.activo is True

    def test_email_se_normaliza_a_minusculas(self, servicio, datos_validos):
        datos_validos["email"] = "ANA.GARCIA@EMPRESA.COM"
        cliente = servicio.crear_cliente(datos_validos)
        assert cliente.email == "ana.garcia@empresa.com"

    def test_nif_se_normaliza_a_mayusculas(self, servicio, datos_validos):
        datos_validos["nif"] = "b12345678"
        cliente = servicio.crear_cliente(datos_validos)
        assert cliente.nif == "B12345678"

    def test_email_duplicado_lanza_excepcion(self, servicio, datos_validos):
        servicio.crear_cliente(datos_validos)
        with pytest.raises(ClienteDuplicado):
            servicio.crear_cliente(datos_validos)

    def test_email_invalido_lanza_validacion_error(self, servicio, datos_validos):
        datos_validos["email"] = "no-es-un-email"
        with pytest.raises(ValidacionError) as exc:
            servicio.crear_cliente(datos_validos)
        assert exc.value.campo == "email"

    def test_nombre_obligatorio(self, servicio):
        with pytest.raises(ValidacionError) as exc:
            servicio.crear_cliente({"apellidos": "López", "email": "x@x.com"})
        assert exc.value.campo == "nombre"

    def test_empresa_requerida_si_tipo_empresa(self, servicio):
        with pytest.raises(ValidacionError) as exc:
            servicio.crear_cliente({
                "nombre": "Juan", "apellidos": "Pérez",
                "email": "j@j.com", "tipo_cliente": "empresa"
            })
        assert exc.value.campo == "empresa"

    def test_tipo_cliente_invalido(self, servicio):
        with pytest.raises(ValidacionError) as exc:
            servicio.crear_cliente({
                "nombre": "Juan", "apellidos": "Pérez",
                "email": "j@j.com", "tipo_cliente": "invalido"
            })
        assert exc.value.campo == "tipo_cliente"

# ── Tests de LECTURA ──────────────────────────────────────────────────────────

class TestObtenerCliente:

    def test_obtener_por_id(self, servicio, datos_validos):
        creado = servicio.crear_cliente(datos_validos)
        encontrado = servicio.obtener_cliente(creado.id)
        assert encontrado.email == creado.email

    def test_id_inexistente_lanza_excepcion(self, servicio):
        with pytest.raises(ClienteNoEncontrado):
            servicio.obtener_cliente(9999)

    def test_obtener_por_email(self, servicio, datos_validos):
        servicio.crear_cliente(datos_validos)
        cliente = servicio.obtener_por_email("ana.garcia@empresa.com")
        assert cliente.nombre == "Ana"

    def test_listar_devuelve_paginacion(self, servicio):
        nombres = ["Ana", "Luis", "Marta", "Pedro", "Rosa"]
        for i, nombre in enumerate(nombres):
            servicio.crear_cliente({
                "nombre": nombre, "apellidos": "Test",
                "email": f"cliente{i}@test.com"
            })
        resultado = servicio.listar_clientes(por_pagina=3)
        assert len(resultado["clientes"]) == 3
        assert resultado["total"] == 5
        assert resultado["paginas"] == 2

    def test_busqueda_por_texto(self, servicio, datos_validos):
        servicio.crear_cliente(datos_validos)
        servicio.crear_cliente({
            "nombre": "Pedro", "apellidos": "Martínez",
            "email": "pedro@otro.com"
        })
        resultado = servicio.listar_clientes(busqueda="Ana")
        assert len(resultado["clientes"]) == 1
        assert resultado["clientes"][0].nombre == "Ana"

# ── Tests de ACTUALIZACIÓN ────────────────────────────────────────────────────

class TestActualizarCliente:

    def test_actualizar_telefono(self, servicio, datos_validos):
        cliente = servicio.crear_cliente(datos_validos)
        actualizado = servicio.actualizar_cliente(
            cliente.id, {"telefono": "+34 699 000 111"}
        )
        assert actualizado.telefono == "+34 699 000 111"
        assert actualizado.nombre == "Ana"  # Resto sin cambios

    def test_actualizar_email_a_duplicado_falla(self, servicio, datos_validos):
        c1 = servicio.crear_cliente(datos_validos)
        c2 = servicio.crear_cliente({
            "nombre": "Luis", "apellidos": "Sanz",
            "email": "luis@otro.com"
        })
        with pytest.raises(ClienteDuplicado):
            servicio.actualizar_cliente(c2.id, {"email": datos_validos["email"]})

    def test_actualizar_id_inexistente(self, servicio):
        with pytest.raises(ClienteNoEncontrado):
            servicio.actualizar_cliente(9999, {"telefono": "123"})

# ── Tests de DESACTIVACIÓN / ELIMINACIÓN ──────────────────────────────────────

class TestDesactivarEliminar:

    def test_desactivar_cliente(self, servicio, datos_validos):
        cliente = servicio.crear_cliente(datos_validos)
        servicio.desactivar_cliente(cliente.id)
        # No aparece en listado de activos
        resultado = servicio.listar_clientes(solo_activos=True)
        ids = [c.id for c in resultado["clientes"]]
        assert cliente.id not in ids

    def test_reactivar_cliente(self, servicio, datos_validos):
        cliente = servicio.crear_cliente(datos_validos)
        servicio.desactivar_cliente(cliente.id)
        servicio.reactivar_cliente(cliente.id)
        resultado = servicio.listar_clientes(solo_activos=True)
        ids = [c.id for c in resultado["clientes"]]
        assert cliente.id in ids

    def test_eliminar_permanente(self, servicio, datos_validos):
        cliente = servicio.crear_cliente(datos_validos)
        servicio.eliminar_cliente(cliente.id)
        with pytest.raises(ClienteNoEncontrado):
            servicio.obtener_cliente(cliente.id)

# ── Tests de ESTADÍSTICAS ─────────────────────────────────────────────────────

class TestEstadisticas:

    def test_estadisticas_correctas(self, servicio, datos_validos):
        servicio.crear_cliente(datos_validos)
        servicio.crear_cliente({
            "nombre": "Luis", "apellidos": "Sanz", "email": "luis@otro.com",
            "tipo_cliente": "particular"
        })
        stats = servicio.estadisticas()
        assert stats["total_activos"] == 2
        assert stats["por_tipo"]["empresa"] == 1
        assert stats["por_tipo"]["particular"] == 1
