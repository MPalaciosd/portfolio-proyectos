"""
Demo del sistema de emails.
Ejecuta en modo TEST (sin enviar nada real) por defecto.

Para enviar emails reales:
  1. Copia .env.example a .env
  2. Rellena tus credenciales SMTP
  3. Cambia EMAIL_TEST_MODE=false en .env

Ejecutar: PYTHONIOENCODING=utf-8 python demo_emails.py
"""
import os
import sys

# ── Activar modo test por defecto en la demo ──────────────────────────────────
os.environ.setdefault("EMAIL_TEST_MODE",      "true")
os.environ.setdefault("SMTP_FROM_NAME",       "TechSoluciones S.L.")
os.environ.setdefault("SMTP_USER",            "demo@techsoluciones.es")
os.environ.setdefault("EMPRESA_TEL",          "+34 91 123 45 67")
os.environ.setdefault("EMPRESA_NIF",          "B12345678")
os.environ.setdefault("EMPRESA_DIR",          "Calle Mayor, 42")
os.environ.setdefault("EMPRESA_CIUDAD",       "Madrid")
os.environ.setdefault("EMPRESA_WEB",          "www.techsoluciones.es")

from backend.core.database          import init_db
from backend.services.email_service import EmailService
from backend.services.pdf_service   import PDFService
from backend.models.presupuesto     import (
    Presupuesto, LineaPresupuesto, EmpresaEmisora, ClientePresupuesto
)

SEP = "-" * 62


def imprimir_resultado(resultado, descripcion: str):
    estado = "OK " if resultado.exito else "FAIL"
    print(f"  [{estado}] {descripcion}")
    print(f"        Para:    {resultado.destinatario}")
    if resultado.exito:
        print(f"        Msg-ID:  {resultado.message_id}")
    else:
        print(f"        Error:   {resultado.error}")


def main():
    init_db()
    servicio_email = EmailService()

    print(f"\n{'='*62}")
    print("   CRM-ASIR — Demo Sistema de Emails (MODO TEST)")
    print(f"{'='*62}")
    print("   Los emails se loguean pero NO se envian realmente.")
    print(f"{'='*62}\n")

    # ── 1. Email de bienvenida ─────────────────────────────────────────────
    print(f"[1] EMAIL DE BIENVENIDA\n{SEP}")
    r = servicio_email.enviar_bienvenida(
        cliente_email    = "maria.gonzalez@empresa.es",
        nombre_cliente   = "Maria",
        empresa_cliente  = "Gonzalez Consulting S.L.",
        nombre_comercial = "Carlos Ruiz",
        telefono_comercial = "+34 91 999 88 77",
    )
    imprimir_resultado(r, "Bienvenida a cliente empresa")

    # ── 2. Generar PDF y enviar presupuesto ────────────────────────────────
    print(f"\n[2] PRESUPUESTO CON PDF ADJUNTO\n{SEP}")

    # Generar el PDF primero
    pdf_service = PDFService()
    presupuesto = Presupuesto(
        numero        = "PRES-2024-004",
        fecha_emision = "28/04/2024",
        fecha_validez = "28/05/2024",
        emisor = EmpresaEmisora(
            nombre="TechSoluciones S.L.", nif="B12345678",
            direccion="Calle Mayor, 42", ciudad="Madrid",
            codigo_postal="28001", telefono="+34 91 123 45 67",
            email="info@techsoluciones.es", web="www.techsoluciones.es",
        ),
        cliente = ClientePresupuesto(
            nombre="Carlos", apellidos="Martinez Lopez",
            empresa="Startup Digital S.L.", nif="B99887766",
            email="carlos@startupdigital.es",
            telefono="+34 699 333 444",
            ciudad="Barcelona", codigo_postal="08001",
        ),
        iva_porcentaje = 21.0,
        lineas = [
            LineaPresupuesto(
                descripcion="Desarrollo aplicacion web CRM a medida",
                cantidad=80, precio_unitario=90.0, unidad="h",
            ),
            LineaPresupuesto(
                descripcion="Hosting VPS 12 meses + dominio",
                cantidad=1, precio_unitario=360.0, unidad="ud",
            ),
            LineaPresupuesto(
                descripcion="Soporte tecnico primer ano",
                cantidad=12, precio_unitario=150.0, descuento=10.0, unidad="mes",
            ),
        ],
        condiciones="50% a la firma, 50% en la entrega.",
        notas="Incluye 2 revisiones de diseno sin coste adicional.",
    )
    ruta_pdf = pdf_service.generar(presupuesto)
    print(f"  PDF generado: {os.path.basename(ruta_pdf)}")

    r = servicio_email.enviar_presupuesto(
        cliente_email      = "carlos@startupdigital.es",
        nombre_cliente     = "Carlos",
        numero_presupuesto = "PRES-2024-004",
        total              = f"{presupuesto.total:,.2f}",
        fecha_validez      = "28/05/2024",
        ruta_pdf           = ruta_pdf,
        condiciones_pago   = "50% a la firma, 50% en la entrega",
        notas_extra        = "Incluye 2 revisiones de diseno sin coste adicional.",
        nombre_comercial   = "Ana Garcia",
    )
    imprimir_resultado(r, "Presupuesto PRES-2024-004 con PDF adjunto")

    # ── 3. Recordatorio de presupuesto pendiente ───────────────────────────
    print(f"\n[3] RECORDATORIO DE PRESUPUESTO PENDIENTE\n{SEP}")
    r = servicio_email.enviar_recordatorio(
        cliente_email      = "sofia.fernandez@outlook.com",
        nombre_cliente     = "Sofia",
        numero_presupuesto = "PRES-2024-002",
        total              = "9.704,20",
        fecha_validez      = "20/12/2024",
        dias_pendiente     = 14,
        nombre_comercial   = "Ana Garcia",
    )
    imprimir_resultado(r, "Recordatorio PRES-2024-002 (14 dias sin respuesta)")

    # ── 4. Email personalizado con plantilla propia ────────────────────────
    print(f"\n[4] EMAIL PERSONALIZADO (plantilla bienvenida reutilizada)\n{SEP}")
    r = servicio_email.enviar_personalizado(
        destinatario   = "pedro.sanchez@empresa.com",
        asunto         = "Confirmacion de reunion — TechSoluciones",
        tipo_plantilla = "bienvenida",
        variables = {
            "nombre_cliente":     "Pedro",
            "empresa_cliente":    "Empresa Demo S.A.",
            "nombre_comercial":   "Luis Gomez",
            "telefono_comercial": "+34 91 555 12 34",
        },
    )
    imprimir_resultado(r, "Email personalizado")

    # ── 5. Envío múltiple (lista de clientes) ──────────────────────────────
    print(f"\n[5] ENVIO MULTIPLE — CAMPANA DE BIENVENIDA\n{SEP}")
    nuevos_clientes = [
        {"email": "cliente1@test.com", "nombre": "Ana",   "empresa": "Empresa A"},
        {"email": "cliente2@test.com", "nombre": "Luis",  "empresa": "Empresa B"},
        {"email": "cliente3@test.com", "nombre": "Marta", "empresa": ""},
    ]

    enviados = 0
    errores  = 0
    for cliente in nuevos_clientes:
        r = servicio_email.enviar_bienvenida(
            cliente_email    = cliente["email"],
            nombre_cliente   = cliente["nombre"],
            empresa_cliente  = cliente["empresa"],
            nombre_comercial = "Equipo TechSoluciones",
        )
        if r.exito:
            enviados += 1
        else:
            errores += 1
        imprimir_resultado(r, f"Bienvenida a {cliente['nombre']}")

    print(f"\n  Resumen campana: {enviados} OK | {errores} errores")

    # ── 6. Verificar HTMLs generados ───────────────────────────────────────
    print(f"\n[6] VERIFICACION DE PLANTILLAS HTML\n{SEP}")
    from backend.services.template_service import TemplateService
    from backend.services.email_service    import DATOS_EMPRESA

    ts = TemplateService()
    plantillas = [
        ("presupuesto_nuevo", {
            "nombre_cliente": "Test Cliente",
            "numero_presupuesto": "PRES-TEST-001",
            "total": "1.000,00",
            "fecha_validez": "31/12/2024",
            "condiciones_pago": "30 dias",
            "notas_extra": "Nota de prueba",
            "nombre_comercial": "Test Comercial",
            "nombre_archivo_pdf": "test.pdf",
        }),
        ("presupuesto_recordatorio", {
            "nombre_cliente": "Test Cliente",
            "numero_presupuesto": "PRES-TEST-001",
            "total": "1.000,00",
            "fecha_validez": "31/12/2024",
            "dias_pendiente": "7",
            "nombre_comercial": "Test Comercial",
        }),
        ("bienvenida", {
            "nombre_cliente": "Test Cliente",
            "empresa_cliente": "Test Empresa",
            "nombre_comercial": "Test Comercial",
            "telefono_comercial": "+34 600 000 000",
        }),
    ]

    for tipo, vars_test in plantillas:
        try:
            html, texto = ts.renderizar(tipo, vars_test, DATOS_EMPRESA)
            tiene_vars  = "{{" in html  # Quedan variables sin sustituir?
            estado = "WARN (variables sin sustituir)" if tiene_vars else "OK "
            print(f"  [{estado}] Plantilla '{tipo}' ({len(html):,} bytes HTML, {len(texto):,} bytes texto)")
        except Exception as e:
            print(f"  [FAIL] Plantilla '{tipo}': {e}")

    print(f"\n{'='*62}")
    print("   Demo completada")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    main()
