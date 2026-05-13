"""
Demo completo del sistema de generación de presupuestos PDF.
Genera 3 presupuestos con distintos escenarios:
  1. Empresa con descuentos en líneas
  2. Autónomo sin descuentos
  3. Particular con estado ACEPTADO

Ejecutar: PYTHONIOENCODING=utf-8 python demo_presupuestos.py
"""
import os
import sys
from backend.core.database import init_db
from backend.models.presupuesto import (
    Presupuesto, LineaPresupuesto, EmpresaEmisora, ClientePresupuesto
)
from backend.services.pdf_service import PDFService

SEP = "-" * 60

# ── Datos de la empresa emisora (compartidos en todos los presupuestos) ────────

EMISOR = EmpresaEmisora(
    nombre        = "TechSoluciones S.L.",
    nif           = "B12345678",
    direccion     = "Calle Mayor, 42, 2ºA",
    ciudad        = "Madrid",
    codigo_postal = "28001",
    pais          = "España",
    telefono      = "+34 91 123 45 67",
    email         = "info@techsoluciones.es",
    web           = "www.techsoluciones.es",
)


def generar_presupuesto_1(servicio: PDFService) -> str:
    """Empresa cliente con múltiples servicios y descuentos."""
    presupuesto = Presupuesto(
        numero        = "PRES-2024-001",
        fecha_emision = "15/11/2024",
        fecha_validez = "15/12/2024",
        emisor        = EMISOR,
        cliente       = ClientePresupuesto(
            nombre        = "María",
            apellidos     = "González Ruiz",
            empresa       = "González Consulting S.L.",
            nif           = "B87654321",
            email         = "maria.gonzalez@gonzalezconsulting.es",
            telefono      = "+34 612 111 222",
            direccion     = "Av. Diagonal, 123, 4ºB",
            ciudad        = "Barcelona",
            codigo_postal = "08001",
        ),
        iva_porcentaje = 21.0,
        estado         = "PENDIENTE",
        notas          = (
            "Instalación incluida en el precio. Soporte técnico durante 30 días "
            "desde la puesta en marcha. Formación al personal incluida (hasta 4h)."
        ),
        condiciones    = (
            "Pago: 50% a la firma, 50% a la entrega. "
            "Validez del presupuesto: 30 días. "
            "Los precios no incluyen desplazamientos fuera de la provincia de Barcelona."
        ),
        lineas = [
            LineaPresupuesto(
                descripcion     = "Servidor Dell PowerEdge R350 — Xeon E-2378, 32GB RAM, 2×480GB SSD RAID1",
                cantidad        = 1,
                precio_unitario = 3_499.00,
                descuento       = 10.0,
                unidad          = "ud",
            ),
            LineaPresupuesto(
                descripcion     = "Licencia Windows Server 2022 Standard (16 cores)",
                cantidad        = 1,
                precio_unitario = 1_089.00,
                descuento       = 5.0,
                unidad          = "lic",
            ),
            LineaPresupuesto(
                descripcion     = "Switch Cisco Catalyst 1000-24T — 24 puertos GbE, 4 SFP",
                cantidad        = 2,
                precio_unitario = 549.00,
                descuento       = 0.0,
                unidad          = "ud",
            ),
            LineaPresupuesto(
                descripcion     = "Cableado estructurado Cat6A — instalación completa (hasta 24 puntos)",
                cantidad        = 1,
                precio_unitario = 1_200.00,
                descuento       = 0.0,
                unidad          = "srv",
            ),
            LineaPresupuesto(
                descripcion     = "Configuración y puesta en marcha del servidor",
                cantidad        = 8,
                precio_unitario = 85.00,
                descuento       = 0.0,
                unidad          = "h",
            ),
            LineaPresupuesto(
                descripcion     = "SAI APC Smart-UPS 1500VA LCD",
                cantidad        = 1,
                precio_unitario = 389.00,
                descuento       = 15.0,
                unidad          = "ud",
            ),
        ],
    )
    return servicio.generar(presupuesto)


def generar_presupuesto_2(servicio: PDFService) -> str:
    """Autónomo — presupuesto de servicios de desarrollo sin descuentos."""
    presupuesto = Presupuesto(
        numero        = "PRES-2024-002",
        fecha_emision = "20/11/2024",
        fecha_validez = "20/12/2024",
        emisor        = EMISOR,
        cliente       = ClientePresupuesto(
            nombre        = "Carlos",
            apellidos     = "Martínez López",
            nif           = "12345678Z",
            email         = "carlos.martinez@gmail.com",
            telefono      = "+34 699 333 444",
            ciudad        = "Girona",
            codigo_postal = "17001",
        ),
        iva_porcentaje = 21.0,
        estado         = "PENDIENTE",
        notas          = "Entrega estimada: 3 semanas desde la confirmación del pedido.",
        condiciones    = (
            "Pago a 30 días desde la factura. "
            "Revisiones ilimitadas durante el periodo de desarrollo. "
            "Garantía de 6 meses sobre el software entregado."
        ),
        lineas = [
            LineaPresupuesto(
                descripcion     = "Análisis de requisitos y arquitectura del sistema",
                cantidad        = 12,
                precio_unitario = 90.00,
                unidad          = "h",
            ),
            LineaPresupuesto(
                descripcion     = "Desarrollo backend — API REST Python/FastAPI con base de datos PostgreSQL",
                cantidad        = 40,
                precio_unitario = 85.00,
                unidad          = "h",
            ),
            LineaPresupuesto(
                descripcion     = "Desarrollo frontend — Panel de administración React",
                cantidad        = 30,
                precio_unitario = 80.00,
                unidad          = "h",
            ),
            LineaPresupuesto(
                descripcion     = "Despliegue en VPS con Docker y CI/CD (GitHub Actions)",
                cantidad        = 8,
                precio_unitario = 90.00,
                unidad          = "h",
            ),
            LineaPresupuesto(
                descripcion     = "Documentación técnica y manual de usuario",
                cantidad        = 6,
                precio_unitario = 70.00,
                unidad          = "h",
            ),
        ],
    )
    return servicio.generar(presupuesto)


def generar_presupuesto_3(servicio: PDFService) -> str:
    """Particular — presupuesto de mantenimiento, estado ACEPTADO."""
    presupuesto = Presupuesto(
        numero        = "PRES-2024-003",
        fecha_emision = "25/11/2024",
        fecha_validez = "25/12/2024",
        emisor        = EMISOR,
        cliente       = ClientePresupuesto(
            nombre        = "Sofia",
            apellidos     = "Fernandez Torres",
            email         = "sofia.fernandez@outlook.com",
            telefono      = "+34 655 777 888",
            ciudad        = "Valencia",
            codigo_postal = "46001",
        ),
        iva_porcentaje = 21.0,
        estado         = "ACEPTADO",
        notas          = "Servicio contratado por 12 meses con renovación automática.",
        condiciones    = (
            "Facturación mensual anticipada. Cancelación con 30 días de preaviso. "
            "SLA: resolución de incidencias críticas en menos de 4 horas hábiles."
        ),
        lineas = [
            LineaPresupuesto(
                descripcion     = "Mantenimiento mensual servidor — monitorización, actualizaciones y backups",
                cantidad        = 12,
                precio_unitario = 120.00,
                descuento       = 10.0,
                unidad          = "mes",
            ),
            LineaPresupuesto(
                descripcion     = "Auditoría de seguridad trimestral — informe detallado con recomendaciones",
                cantidad        = 4,
                precio_unitario = 250.00,
                unidad          = "ud",
            ),
            LineaPresupuesto(
                descripcion     = "Soporte técnico prioritario — bolsa de horas mensuales",
                cantidad        = 12,
                precio_unitario = 200.00,
                descuento       = 5.0,
                unidad          = "mes",
            ),
        ],
    )
    # Nombre de archivo personalizado explícito
    return servicio.generar(presupuesto, nombre_archivo="PRES-2024-003_Sofia_ACEPTADO.pdf")


def main():
    init_db()
    servicio = PDFService()

    print(f"\n{'='*60}")
    print("   CRM-ASIR — Generador de Presupuestos PDF")
    print(f"{'='*60}\n")

    escenarios = [
        ("Empresa con descuentos en hardware",  generar_presupuesto_1),
        ("Autonomo — servicios de desarrollo",  generar_presupuesto_2),
        ("Particular — mantenimiento ACEPTADO", generar_presupuesto_3),
    ]

    rutas = []
    for descripcion, fn in escenarios:
        print(f"Generando: {descripcion}...")
        try:
            ruta = fn(servicio)
            rutas.append(ruta)
            nombre  = os.path.basename(ruta)
            tamanio = os.path.getsize(ruta) / 1024
            print(f"  OK  {nombre} ({tamanio:.1f} KB)")
        except Exception as e:
            print(f"  ERROR: {e}")
            raise

    print(f"\n{SEP}")
    print("PDFs generados en: storage/pdfs/")
    print(SEP)
    for archivo in servicio.listar_pdfs():
        print(f"  {archivo['nombre']:<55} {archivo['tamanio']:>8}  {archivo['creado']}")

    print(f"\n{'='*60}")
    print("   Generacion completada")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
