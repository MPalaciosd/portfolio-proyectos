"""
Punto de entrada principal del sistema CRM-ASIR.
Uso:
    python main.py demo       — Ejecuta ejemplos de uso completos
    python main.py stats      — Muestra estadísticas de la BD actual
    python main.py --help     — Ayuda
"""
import sys
from backend.core.database import init_db
from backend.services.cliente_service import ClienteService
from backend.core.exceptions import CRMException


def demo():
    """Demuestra todas las operaciones CRUD con datos reales."""
    servicio = ClienteService()
    sep = "-" * 60

    print(f"\n{'='*60}")
    print("   CRM-ASIR — Demo del Sistema de Gestión de Clientes")
    print(f"{'='*60}\n")

    # -- 1. CREAR clientes -------------------------------------------
    print(f"[1] CREAR CLIENTES\n{sep}")
    clientes_demo = [
        {
            "nombre": "María", "apellidos": "González Ruiz",
            "email": "maria.gonzalez@empresa.es",
            "telefono": "+34 612 111 222",
            "empresa": "González Consulting S.L.",
            "tipo_cliente": "empresa",
            "ciudad": "Madrid", "codigo_postal": "28001",
            "nif": "B87654321",
            "notas": "Cliente preferente, contactar los lunes"
        },
        {
            "nombre": "Carlos", "apellidos": "Martínez López",
            "email": "carlos.martinez@gmail.com",
            "telefono": "+34 699 333 444",
            "tipo_cliente": "autonomo",
            "ciudad": "Barcelona", "codigo_postal": "08001",
            "nif": "12345678Z",
        },
        {
            "nombre": "Sofía", "apellidos": "Fernández Torres",
            "email": "sofia.fernandez@outlook.com",
            "ciudad": "Valencia",
            "tipo_cliente": "particular",
        },
    ]

    creados = []
    for datos in clientes_demo:
        try:
            c = servicio.crear_cliente(datos)
            print(f"  OK Creado: [{c.id:02d}] {c.nombre_completo} <{c.email}>")
            creados.append(c)
        except CRMException as e:
            print(f"  FAIL Error: {e}")

    # -- 2. LEER — obtener por ID ------------------------------------
    print(f"\n[2] OBTENER POR ID\n{sep}")
    if creados:
        c = servicio.obtener_cliente(creados[0].id)
        print(f"  ID:        {c.id}")
        print(f"  Nombre:    {c.nombre_completo}")
        print(f"  Empresa:   {c.empresa}")
        print(f"  Email:     {c.email}")
        print(f"  Teléfono:  {c.telefono}")
        print(f"  Ciudad:    {c.ciudad}")
        print(f"  Tipo:      {c.tipo_cliente}")
        print(f"  Alta:      {c.fecha_alta}")

    # -- 3. LISTAR con paginación ------------------------------------
    print(f"\n[3] LISTAR CLIENTES (página 1, 2 por página)\n{sep}")
    resultado = servicio.listar_clientes(por_pagina=2, pagina=1)
    for c in resultado["clientes"]:
        estado = "ACTIVO" if c.activo else "INACTIVO"
        print(f"  [{c.id:02d}] {c.nombre_completo:<30} {c.tipo_cliente:<12} {estado}")
    print(f"\n  Total: {resultado['total']} | Página {resultado['pagina']}/{resultado['paginas']}")

    # -- 4. BUSCAR ---------------------------------------------------
    print(f"\n[4] BUSCAR por texto 'carlos'\n{sep}")
    resultado = servicio.listar_clientes(busqueda="carlos")
    for c in resultado["clientes"]:
        print(f"  Encontrado: {c.nombre_completo} — {c.email}")

    # -- 5. ACTUALIZAR -----------------------------------------------
    print(f"\n[5] ACTUALIZAR CLIENTE\n{sep}")
    if creados:
        c = servicio.actualizar_cliente(creados[1].id, {
            "telefono": "+34 699 999 000",
            "ciudad":   "Girona",
            "notas":    "Cambió de ciudad en 2024"
        })
        print(f"  Actualizado: {c.nombre_completo}")
        print(f"  Nuevo tel:   {c.telefono}")
        print(f"  Nueva ciudad:{c.ciudad}")
        print(f"  Modificado:  {c.fecha_modificacion}")

    # -- 6. VALIDACIONES — intentos fallidos -------------------------
    print(f"\n[6] VALIDACIONES (errores esperados)\n{sep}")
    casos_erroneos = [
        ({"nombre": "Test", "apellidos": "User", "email": "no-valido"},
         "Email inválido"),
        ({"nombre": "Test", "apellidos": "User", "email": "maria.gonzalez@empresa.es"},
         "Email duplicado"),
        ({"nombre": "Test", "apellidos": "User", "email": "ok@ok.com",
          "tipo_cliente": "empresa"},
         "Empresa requerida para tipo=empresa"),
        ({"nombre": "Test", "apellidos": "User", "email": "ok2@ok.com",
          "codigo_postal": "AAAAA"},
         "Código postal inválido"),
    ]
    for datos, descripcion in casos_erroneos:
        try:
            servicio.crear_cliente(datos)
            print(f"  FAIL FALLO — debería haber fallado: {descripcion}")
        except CRMException as e:
            print(f"  OK Capturado correctamente [{descripcion}]: {e}")

    # -- 7. DESACTIVAR -----------------------------------------------
    print(f"\n[7] DESACTIVAR Y REACTIVAR\n{sep}")
    if creados:
        servicio.desactivar_cliente(creados[2].id)
        print(f"  Desactivado: {creados[2].nombre_completo}")
        total_activos   = servicio.listar_clientes(solo_activos=True)["total"]
        total_todos     = servicio.listar_clientes(solo_activos=False)["total"]
        print(f"  Activos: {total_activos} / Total: {total_todos}")

        servicio.reactivar_cliente(creados[2].id)
        print(f"  Reactivado: {creados[2].nombre_completo}")

    # -- 8. ESTADÍSTICAS ---------------------------------------------
    print(f"\n[8] ESTADÍSTICAS\n{sep}")
    stats = servicio.estadisticas()
    print(f"  Clientes activos:   {stats['total_activos']}")
    print(f"  Clientes inactivos: {stats['total_inactivos']}")
    print(f"  Por tipo:")
    for tipo, n in stats["por_tipo"].items():
        print(f"    - {tipo:<15} {n}")
    if stats["top_ciudades"]:
        print(f"  Top ciudades:")
        for ciudad, n in stats["top_ciudades"].items():
            print(f"    - {ciudad:<15} {n}")

    print(f"\n{'='*60}")
    print("   Demo completada con éxito")
    print(f"{'='*60}\n")


def mostrar_stats():
    servicio = ClienteService()
    stats = servicio.estadisticas()
    print(f"\nEstadísticas CRM")
    print(f"{'-'*30}")
    print(f"Activos:   {stats['total_activos']}")
    print(f"Inactivos: {stats['total_inactivos']}")
    for tipo, n in stats.get("por_tipo", {}).items():
        print(f"  {tipo}: {n}")
    print()


if __name__ == "__main__":
    init_db()  # Crea DB y tablas si no existen

    comando = sys.argv[1] if len(sys.argv) > 1 else "demo"

    if comando == "demo":
        demo()
    elif comando == "stats":
        mostrar_stats()
    else:
        print(f"Comandos disponibles: demo | stats")
        sys.exit(1)
