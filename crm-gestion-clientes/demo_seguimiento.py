"""
Demo completo del sistema de seguimiento comercial.
Simula el ciclo de vida real de 4 clientes con distintos escenarios.

Ejecutar: PYTHONIOENCODING=utf-8 python demo_seguimiento.py
"""
import os, sys
os.environ.setdefault("EMAIL_TEST_MODE", "true")
os.environ.setdefault("SMTP_FROM_NAME",  "TechSoluciones S.L.")
os.environ.setdefault("SMTP_USER",       "demo@techsoluciones.es")

from backend.core.database import init_db
from backend.repositories.seguimiento_repository import (
    SeguimientoRepository, init_seguimiento_schema,
)
from backend.services.seguimiento_service import SeguimientoService
from backend.services.cliente_service     import ClienteService
from backend.models.seguimiento           import (
    EstadoCliente, TipoEvento, Prioridad,
)

SEP  = "─" * 64
SEP2 = "═" * 64

repo_seg  = SeguimientoRepository()
svc_seg   = SeguimientoService()
svc_cli   = ClienteService()


# ── Helpers de presentación ───────────────────────────────────────────────────

ICONOS_ESTADO = {
    "nuevo":             "[NUEVO]    ",
    "contactado":        "[CONTACT.] ",
    "interesado":        "[INTERES.] ",
    "propuesta_enviada": "[PROPUEST.]",
    "negociacion":       "[NEGOC.]   ",
    "cerrado_ganado":    "[GANADO]   ",
    "cerrado_perdido":   "[PERDIDO]  ",
    "sin_respuesta":     "[SIN RESP.]",
    "enfriado":          "[ENFRIADO] ",
}

ICONOS_PRIO = {
    "critica": "[!!!]",
    "alta":    "[!! ]",
    "media":   "[!  ]",
    "baja":    "[   ]",
}


def imprimir_transicion(resultado: dict):
    ant = resultado["estado_anterior"]
    nvo = resultado["estado_nuevo"]
    if resultado["hubo_transicion"]:
        print(f"       {ICONOS_ESTADO[ant]} --> {ICONOS_ESTADO[nvo]}  "
              f"score={resultado['score']}")
    else:
        print(f"       {ICONOS_ESTADO[ant]} (sin cambio)  score={resultado['score']}")


def imprimir_analisis(analisis):
    print(f"\n  Cliente : {analisis.nombre_cliente}")
    print(f"  Estado  : {ICONOS_ESTADO[analisis.estado_actual.value]} {analisis.estado_actual.value}")
    print(f"  Score   : {analisis.score_interes}/100  |  "
          f"Dias en estado: {analisis.dias_en_estado}  |  "
          f"Sin contacto: {analisis.dias_sin_contacto}")
    print(f"  Contactos totales: {analisis.total_contactos}")

    if analisis.alerta:
        print(f"\n  *** ALERTA: {analisis.alerta} ***")

    print(f"\n  Acciones sugeridas:")
    for a in analisis.acciones_sugeridas:
        auto = " [AUTO]" if a.automatizable else ""
        print(f"    {ICONOS_PRIO[a.prioridad.value]} {a.titulo}{auto}")
        print(f"           {a.descripcion}")
        if a.plazo_dias == 0:
            print(f"           Plazo: HOY")
        else:
            print(f"           Plazo: {a.plazo_dias} dia(s)")


def crear_clientes_demo() -> dict:
    """Crea 4 clientes con distintos perfiles comerciales."""
    perfiles = [
        {
            "nombre": "Maria", "apellidos": "Gonzalez Ruiz",
            "email": "maria@gonzalezconsulting.es",
            "empresa": "Gonzalez Consulting S.L.",
            "tipo_cliente": "empresa", "ciudad": "Madrid",
        },
        {
            "nombre": "Carlos", "apellidos": "Martinez Lopez",
            "email": "carlos.martinez@gmail.com",
            "tipo_cliente": "autonomo", "ciudad": "Barcelona",
        },
        {
            "nombre": "Sofia", "apellidos": "Fernandez Torres",
            "email": "sofia.fernandez@outlook.com",
            "tipo_cliente": "particular", "ciudad": "Valencia",
        },
        {
            "nombre": "Pedro", "apellidos": "Sanchez Vidal",
            "email": "pedro.sanchez@startups.io",
            "empresa": "StartupTech S.L.",
            "tipo_cliente": "empresa", "ciudad": "Sevilla",
        },
    ]
    ids = {}
    for p in perfiles:
        try:
            c = svc_cli.crear_cliente(p)
            ids[p["nombre"]] = c.id
            # Estado inicial en seguimiento
            repo_seg.actualizar_estado(c.id, EstadoCliente.NUEVO, score=0)
        except Exception:
            # Si ya existe, buscarlo
            c = svc_cli.obtener_por_email(p["email"])
            ids[p["nombre"]] = c.id
    return ids


def main():
    init_db()
    init_seguimiento_schema()

    print(f"\n{SEP2}")
    print("   CRM-ASIR — Demo Sistema de Seguimiento Comercial")
    print(f"{SEP2}\n")

    ids = crear_clientes_demo()
    id_maria  = ids["Maria"]
    id_carlos = ids["Carlos"]
    id_sofia  = ids["Sofia"]
    id_pedro  = ids["Pedro"]

    # ══════════════════════════════════════════════════════════════════════
    # ESCENARIO 1 — MARIA: Ciclo completo exitoso
    # NUEVO -> CONTACTADO -> INTERESADO -> PROPUESTA -> NEGOCIACION -> GANADO
    # ══════════════════════════════════════════════════════════════════════
    print(f"[ESCENARIO 1] Maria Gonzalez — Ciclo completo GANADO\n{SEP}")

    print("\n  Dia 0: Cliente nuevo entra en el CRM")
    analisis = svc_seg.analizar_cliente(id_maria)
    imprimir_analisis(analisis)

    print(f"\n  {SEP}")
    print("  Dia 0: Enviamos email de presentacion")
    r = svc_seg.registrar_evento(id_maria, TipoEvento.EMAIL_ENVIADO,
                                  "Email de presentacion de servicios")
    imprimir_transicion(r)

    print("\n  Dia 2: Maria responde mostrando interes")
    r = svc_seg.registrar_evento(id_maria, TipoEvento.EMAIL_RECIBIDO,
                                  "Maria responde: 'Estamos interesados, mandenos mas info'")
    imprimir_transicion(r)

    print("\n  -> Analizamos que hacer ahora:")
    analisis = svc_seg.analizar_cliente(id_maria)
    imprimir_analisis(analisis)

    print(f"\n  {SEP}")
    print("  Dia 3: Preparamos y enviamos presupuesto")
    r = svc_seg.registrar_evento(id_maria, TipoEvento.PRESUPUESTO_ENVIADO,
                                  "Presupuesto PRES-2024-001 enviado (9.065 EUR + IVA)")
    imprimir_transicion(r)

    print("\n  Dia 6: Sin respuesta al presupuesto — analizamos:")
    analisis = svc_seg.analizar_cliente(id_maria)
    imprimir_analisis(analisis)

    print(f"\n  {SEP}")
    print("  Dia 7: Llamada para resolver dudas")
    r = svc_seg.registrar_evento(id_maria, TipoEvento.REUNION_REALIZADA,
                                  "Llamada: resolvemos dudas sobre el servidor. Quieren negociar precio")
    imprimir_transicion(r)

    print("\n  Dia 8: Aceptan el presupuesto con pequena modificacion")
    r = svc_seg.registrar_evento(id_maria, TipoEvento.PRESUPUESTO_ACEPTADO,
                                  "Presupuesto aceptado con descuento adicional del 2%")
    imprimir_transicion(r)

    print("\n  -> Estado final Maria:")
    analisis = svc_seg.analizar_cliente(id_maria)
    imprimir_analisis(analisis)

    # ══════════════════════════════════════════════════════════════════════
    # ESCENARIO 2 — CARLOS: Sin respuesta -> Reactivacion exitosa
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n\n[ESCENARIO 2] Carlos Martinez — Sin respuesta, luego reactivado\n{SEP}")

    print("\n  Dia 0: Enviamos email inicial")
    r = svc_seg.registrar_evento(id_carlos, TipoEvento.EMAIL_ENVIADO,
                                  "Email de introduccion de servicios")
    imprimir_transicion(r)

    print("\n  Dias 1-7: Sin respuesta. Sistema detecta automaticamente:")
    r = svc_seg.registrar_evento(id_carlos, TipoEvento.SIN_RESPUESTA_DETECTADO,
                                  "Automatico: 7 dias sin respuesta al email inicial")
    imprimir_transicion(r)

    print("\n  -> Motor de reglas analiza a Carlos:")
    analisis = svc_seg.analizar_cliente(id_carlos)
    imprimir_analisis(analisis)

    print(f"\n  {SEP}")
    print("  Dia 8: Enviamos email de reactivacion (automatico)")
    # Simular email automatico de reactivacion
    print("       [AUTO] Email de reactivacion enviado con nueva oferta")

    print("\n  Dia 10: Carlos responde al email de reactivacion")
    r = svc_seg.registrar_evento(id_carlos, TipoEvento.REACTIVACION_EXITOSA,
                                  "Carlos llama: 'Vi vuestro email, ahora si me interesa'")
    imprimir_transicion(r)

    print("\n  -> Nuevo analisis tras reactivacion:")
    analisis = svc_seg.analizar_cliente(id_carlos)
    imprimir_analisis(analisis)

    # ══════════════════════════════════════════════════════════════════════
    # ESCENARIO 3 — SOFIA: Interesada pero se enfria -> Perdida
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n\n[ESCENARIO 3] Sofia Fernandez — Se enfria y se pierde\n{SEP}")

    print("\n  Dia 0: Sofia llama por recomendacion (interes alto)")
    r = svc_seg.registrar_evento(id_sofia, TipoEvento.LLAMADA_RECIBIDA,
                                  "Sofia llama: le recomendaron nuestros servicios")
    imprimir_transicion(r)

    print("\n  -> Analisis inicial (muy interesada):")
    analisis = svc_seg.analizar_cliente(id_sofia)
    imprimir_analisis(analisis)

    print(f"\n  {SEP}")
    print("  Tardamos 5 dias en enviar propuesta (error nuestro)")
    r = svc_seg.registrar_evento(id_sofia, TipoEvento.PRESUPUESTO_ENVIADO,
                                  "Presupuesto enviado con retraso")
    imprimir_transicion(r)

    print("\n  Pasan 15 dias sin respuesta -> sistema detecta enfriamiento:")
    r = svc_seg.registrar_evento(id_sofia, TipoEvento.SIN_RESPUESTA_DETECTADO,
                                  "Automatico: propuesta sin respuesta 15 dias -> enfriada")
    imprimir_transicion(r)

    print("\n  -> Motor de reglas en estado ENFRIADO:")
    analisis = svc_seg.analizar_cliente(id_sofia)
    imprimir_analisis(analisis)

    print(f"\n  {SEP}")
    print("  Intentamos reactivar pero Sofia ya contrató con la competencia")
    r = svc_seg.registrar_evento(id_sofia, TipoEvento.PRESUPUESTO_RECHAZADO,
                                  "Sofia informa: contrato firmado con otra empresa")
    imprimir_transicion(r)

    print("\n  -> Estado final Sofia (leccion aprendida: responder rapido):")
    analisis = svc_seg.analizar_cliente(id_sofia)
    imprimir_analisis(analisis)

    # ══════════════════════════════════════════════════════════════════════
    # ESCENARIO 4 — PEDRO: En negociacion activa
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n\n[ESCENARIO 4] Pedro Sanchez — En negociacion activa\n{SEP}")

    print("\n  Secuencia rapida: contacto -> interes -> propuesta -> negociacion")
    for evento, desc in [
        (TipoEvento.EMAIL_ENVIADO,      "Email inicial"),
        (TipoEvento.REUNION_REALIZADA,  "Reunion presencial, muy interesado"),
        (TipoEvento.PRESUPUESTO_ENVIADO,"Propuesta 15.000 EUR enviada"),
        (TipoEvento.PRESUPUESTO_ACEPTADO,"Quieren negociar condiciones de pago"),
    ]:
        r = svc_seg.registrar_evento(id_pedro, evento, desc)
        print(f"       {evento.value:30} ", end="")
        imprimir_transicion(r)

    print("\n  -> Analisis actual de Pedro (negociacion activa):")
    analisis = svc_seg.analizar_cliente(id_pedro)
    imprimir_analisis(analisis)

    # ══════════════════════════════════════════════════════════════════════
    # PIPELINE GENERAL
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n\n[PIPELINE] Resumen comercial completo\n{SEP}")

    pipeline = svc_seg.pipeline_resumen()
    estados_orden = [
        "nuevo", "contactado", "interesado", "propuesta_enviada",
        "negociacion", "sin_respuesta", "enfriado",
        "cerrado_ganado", "cerrado_perdido",
    ]

    total_activos = 0
    for estado in estados_orden:
        datos = pipeline.get(estado, {"total": 0, "clientes": []})
        if datos["total"] == 0:
            continue
        icono = ICONOS_ESTADO.get(estado, f"[{estado[:8]}]")
        print(f"\n  {icono} ({datos['total']} cliente(s))")
        for c in datos["clientes"]:
            dias = c.get("dias_sin_contacto", 0)
            print(f"    - {c['nombre']:<30} score={c['score']:3d}  "
                  f"sin contacto: {dias} dias")
        if estado not in ("cerrado_ganado", "cerrado_perdido"):
            total_activos += datos["total"]

    print(f"\n  {SEP}")
    print(f"  Pipeline activo: {total_activos} cliente(s)")
    ganados  = pipeline.get("cerrado_ganado",  {"total": 0})["total"]
    perdidos = pipeline.get("cerrado_perdido", {"total": 0})["total"]
    total_cerrados = ganados + perdidos
    tasa = (ganados / total_cerrados * 100) if total_cerrados else 0
    print(f"  Tasa de conversion: {ganados}/{total_cerrados} = {tasa:.0f}%")

    # ══════════════════════════════════════════════════════════════════════
    # HISTORIAL DE EVENTOS
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n\n[HISTORIAL] Eventos de Maria Gonzalez (ciclo completo)\n{SEP}")

    historial = svc_seg.historial(id_maria)
    for h in historial:
        print(f"  {h['fecha']}  {h['tipo_contacto']:<20} "
              f"{h['resultado']:<15} {h['descripcion'][:45]}")

    # ══════════════════════════════════════════════════════════════════════
    # AUTOMATIZACION (simulada)
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n\n[AUTOMATIZACION] Ejecucion del motor automatico\n{SEP}")
    print("  Simulando ejecucion del job automatico (cron diario)...")

    # Crear cliente nuevo para que la automatizacion actue
    try:
        c_auto = svc_cli.crear_cliente({
            "nombre": "Test", "apellidos": "Automatico",
            "email": "test.auto@demo.com", "tipo_cliente": "particular",
        })
        repo_seg.actualizar_estado(c_auto.id, EstadoCliente.NUEVO, score=0)

        resultado = svc_seg.ejecutar_automatizaciones(email_service=None)
        print(f"\n  Resultado del motor:")
        etiquetas = {
            "bienvenidas":   "Emails bienvenida enviados",
            "recordatorios": "Recordatorios presupuesto enviados",
            "sin_respuesta": "Clientes marcados SIN_RESPUESTA",
            "enfriados":     "Clientes marcados ENFRIADOS",
            "cerrados":      "Leads cerrados automaticamente",
            "errores":       "Errores",
        }
        for clave, etiqueta in etiquetas.items():
            valor = resultado.get(clave, 0)
            if valor > 0:
                print(f"    {etiqueta:<40} {valor}")
    except Exception as e:
        print(f"  Error en automatizacion: {e}")

    print(f"\n{SEP2}")
    print("   Demo completada")
    print(f"{SEP2}\n")


if __name__ == "__main__":
    main()
