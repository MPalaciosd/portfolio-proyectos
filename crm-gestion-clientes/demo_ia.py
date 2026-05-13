"""
Demo completo de integración IA con Claude API.

REQUISITO: Tener ANTHROPIC_API_KEY configurada.
  Opción A — variable de entorno:
      set ANTHROPIC_API_KEY=sk-ant-...      (Windows CMD)
      export ANTHROPIC_API_KEY=sk-ant-...   (Linux/Mac)

  Opción B — archivo .env en la raíz del proyecto:
      ANTHROPIC_API_KEY=sk-ant-...

Ejecutar: PYTHONIOENCODING=utf-8 python demo_ia.py
"""
import os
import sys

# ── Cargar .env si existe ─────────────────────────────────────────────────────
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for linea in f:
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, valor = linea.split("=", 1)
                os.environ.setdefault(clave.strip(), valor.strip())

from backend.core.database import init_db
from backend.repositories.seguimiento_repository import init_seguimiento_schema
from backend.services.ia_service import (
    generar_email,
    analizar_cliente,
    mejorar_decision,
    auditar_email,
    generar_asuntos_ab,
)

SEP  = "-" * 64
SEP2 = "=" * 64

EMPRESA = {
    "nombre":    "TechSoluciones S.L.",
    "servicios": "Infraestructura IT, desarrollo de software, ciberseguridad y soporte técnico",
}

NIVELES_RIESGO = {
    "bajo":    "[BAJO    ]",
    "medio":   "[MEDIO   ]",
    "alto":    "[ALTO    ]",
    "critico": "[CRITICO ]",
}


def verificar_api_key() -> bool:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key or not key.startswith("sk-"):
        print(f"\n{'!'*64}")
        print("  ANTHROPIC_API_KEY no configurada o inválida.")
        print("  Crea un archivo .env en crm-asir/ con:")
        print("  ANTHROPIC_API_KEY=sk-ant-api03-...")
        print("  Obtén tu clave en: https://console.anthropic.com/")
        print(f"{'!'*64}\n")
        return False
    print(f"  API Key detectada: {key[:12]}...{key[-4:]}")
    return True


def demo_1_generar_email():
    """Email personalizado para cliente en estado 'sin_respuesta'."""
    print(f"\n[1] GENERACION DE EMAIL CON IA\n{SEP}")
    print("  Contexto: Cliente sin respuesta 12 dias, presupuesto enviado")
    print("  Generando email con Claude...\n")

    email = generar_email(
        nombre_cliente    = "Carlos",
        empresa_cliente   = "Martinez Digital S.L.",
        tipo_cliente      = "empresa",
        estado_comercial  = "sin_respuesta",
        dias_sin_contacto = 12,
        historial_resumen = (
            "Primer contacto hace 20 días por recomendación. "
            "Mostró interés en servidor + instalación. "
            "Enviamos presupuesto de 9.065€ hace 12 días. Sin respuesta."
        ),
        objetivo_email    = "Reactivar conversación sobre el presupuesto PRES-2024-001",
        datos_empresa_emisora = EMPRESA,
        informacion_extra = "Podemos ofrecer financiación a 12 meses sin intereses",
    )

    print(f"  Tono elegido por Claude: {email.tono.upper()}")
    print(f"  Razonamiento: {email.razonamiento}")
    print(f"\n  ASUNTO: {email.asunto}")
    print(f"\n  CUERPO (texto plano):")
    for linea in email.cuerpo_texto.strip().split("\n"):
        print(f"    {linea}")
    print(f"\n  HTML generado: {len(email.cuerpo_html)} caracteres")
    return email


def demo_2_analizar_cliente():
    """Análisis con razonamiento adaptativo de un cliente en negociación."""
    print(f"\n[2] ANALISIS DE CLIENTE CON IA (thinking adaptativo)\n{SEP}")
    print("  Contexto: Cliente en negociacion, presupuesto alto, dudas sobre precio")
    print("  Analizando con Claude (puede tardar unos segundos)...\n")

    historial = [
        {"fecha": "2024-11-01", "tipo_contacto": "llamada",
         "descripcion": "Primera llamada. Muy interesados en el proyecto.",
         "resultado": "positivo"},
        {"fecha": "2024-11-05", "tipo_contacto": "email",
         "descripcion": "Enviamos propuesta detallada de 45.000 EUR.",
         "resultado": "neutro"},
        {"fecha": "2024-11-10", "tipo_contacto": "reunion",
         "descripcion": "Reunion presencial. Les parece caro. Piden descuento del 20%.",
         "resultado": "neutro"},
        {"fecha": "2024-11-15", "tipo_contacto": "email",
         "descripcion": "Enviamos contrapropuesta con descuento del 10% y pago fraccionado.",
         "resultado": "neutro"},
        {"fecha": "2024-11-20", "tipo_contacto": "llamada",
         "descripcion": "Dicen que están comparando con otra empresa. Necesitan 2 semanas.",
         "resultado": "neutro"},
    ]

    analisis = analizar_cliente(
        nombre_cliente    = "Pedro",
        empresa_cliente   = "StartupTech S.L.",
        tipo_cliente      = "empresa",
        estado_comercial  = "negociacion",
        score_actual      = 65,
        dias_en_estado    = 25,
        dias_sin_contacto = 8,
        total_contactos   = 5,
        historial         = historial,
        valor_presupuesto = 45000.0,
    )

    icono = NIVELES_RIESGO.get(analisis.nivel_riesgo, f"[{analisis.nivel_riesgo}]")
    print(f"  Riesgo: {icono}   Probabilidad cierre: {analisis.probabilidad_cierre}%")
    print(f"\n  Resumen ejecutivo:")
    print(f"    {analisis.resumen_ejecutivo}")
    print(f"\n  Factores positivos:")
    for f in analisis.factores_positivos:
        print(f"    + {f}")
    print(f"\n  Factores negativos:")
    for f in analisis.factores_negativos:
        print(f"    - {f}")
    print(f"\n  Estrategia recomendada:")
    print(f"    {analisis.estrategia_recomendada}")
    print(f"\n  Proximos pasos:")
    for i, paso in enumerate(analisis.proximos_pasos, 1):
        print(f"    {i}. {paso}")
    print(f"\n  Tiempo estimado de cierre: {analisis.tiempo_estimado_cierre}")
    return analisis


def demo_3_decision_compleja():
    """Ayuda a decidir si hacer descuento o dejar ir al cliente."""
    print(f"\n[3] MEJORA DE DECISION COMERCIAL COMPLEJA\n{SEP}")
    print("  Dilema: cliente pide 25% descuento o se va con la competencia")
    print("  Consultando a Claude...\n")

    decision = mejorar_decision(
        situacion = (
            "Cliente StartupTech S.L. lleva 25 días en negociación para un contrato "
            "de 45.000 EUR. Piden ahora un descuento del 25% (11.250 EUR menos). "
            "Dicen tener oferta de la competencia al mismo precio con descuento. "
            "El margen mínimo rentable para nosotros es un 15% de descuento. "
            "El cliente tiene potencial de renovaciones anuales de ~20.000 EUR."
        ),
        opciones = [
            "Conceder el 25% de descuento para cerrar el contrato",
            "Mantener el 10% de descuento ofrecido y dejar que decidan",
            "Ofrecer 15% de descuento como límite absoluto con argumentación de valor",
            "Proponer un contrato más pequeño (MVP) a menor precio como punto de entrada",
            "Dejar ir al cliente — el margen no compensa",
        ],
        contexto_extra = (
            "Somos una empresa de 15 personas. Este sería nuestro cliente más grande. "
            "Tenemos capacidad libre ahora mismo. El sector IT está muy competitivo."
        ),
    )

    print(f"  Decision recomendada:")
    print(f"    {decision.decision}")
    print(f"\n  Justificacion:")
    print(f"    {decision.justificacion}")
    print(f"\n  Nivel de confianza: {decision.nivel_confianza}%")
    print(f"\n  Alternativas consideradas:")
    for alt in decision.alternativas:
        print(f"    - {alt}")
    if decision.advertencias:
        print(f"\n  Advertencias:")
        for adv in decision.advertencias:
            print(f"    ! {adv}")
    return decision


def demo_4_auditoria_email():
    """Audita un email malo y lo mejora antes de enviarlo."""
    print(f"\n[4] AUDITORIA DE EMAIL ANTES DE ENVIAR\n{SEP}")

    email_malo = """Hola,

Espero que este email te encuentre bien. Me pongo en contacto contigo para
hacerte saber que todavía tenemos disponible nuestra amplia gama de servicios
tecnológicos que pueden ser de gran utilidad para tu empresa.

Como ya te mencioné en emails anteriores, ofrecemos soluciones integrales
para todas tus necesidades IT. Si tienes cualquier pregunta no dudes en
contactarnos cuando puedas.

Un cordial saludo,
El equipo de TechSoluciones"""

    print("  Email original (con problemas):")
    for linea in email_malo.strip().split("\n"):
        print(f"    {linea}")

    print("\n  Auditando con Claude...\n")

    auditoria = auditar_email(
        asunto   = "Información sobre nuestros servicios",
        cuerpo   = email_malo,
        contexto = "Segundo email a cliente que no respondió el primero hace 10 días",
    )

    print(f"  Puntuacion: {auditoria.puntuacion}/100")
    print(f"\n  Problemas detectados:")
    for p in auditoria.problemas:
        print(f"    - {p}")
    print(f"\n  Mejoras sugeridas:")
    for m in auditoria.mejoras:
        print(f"    + {m}")
    print(f"\n  Version mejorada por Claude:")
    for linea in auditoria.version_mejorada.strip().split("\n"):
        print(f"    {linea}")
    return auditoria


def demo_5_asuntos_ab():
    """Genera variantes de asunto para A/B testing."""
    print(f"\n[5] GENERACION DE ASUNTOS PARA A/B TESTING\n{SEP}")
    print("  Generando 3 variantes de asunto para presupuesto sin respuesta...\n")

    asuntos = generar_asuntos_ab(
        contexto       = "Presupuesto de 9.065 EUR enviado hace 12 días sin respuesta",
        nombre_cliente = "Carlos de Martinez Digital",
        objetivo       = "Reactivar conversación y conseguir una respuesta",
        n_variantes    = 3,
    )

    print("  Variantes generadas (para A/B testing):")
    for i, asunto in enumerate(asuntos, 1):
        print(f"    Variante {i}: {asunto}")

    print("\n  Consejo: Usar la variante 1 para el 33% de los envíos,")
    print("  variante 2 para el 33% y variante 3 para el 34%.")
    print("  Medir tasa de apertura en 48 horas.")
    return asuntos


def main():
    init_db()
    init_seguimiento_schema()

    print(f"\n{SEP2}")
    print("   CRM-ASIR — Integración IA con Claude API")
    print(f"{SEP2}")

    # Verificar API key antes de empezar
    if not verificar_api_key():
        sys.exit(1)

    print(f"\n  Modelo: claude-opus-4-6 (Opus 4.6)")
    print(f"  Thinking: adaptativo (Claude decide cuánto razonar)")
    print(f"  Streaming: activado para respuestas largas")

    demos = [
        ("Generacion de email personalizado",    demo_1_generar_email),
        ("Analisis profundo de cliente",          demo_2_analizar_cliente),
        ("Decision sobre descuento complejo",     demo_3_decision_compleja),
        ("Auditoria de email antes de enviarlo",  demo_4_auditoria_email),
        ("Asuntos A/B para campana",              demo_5_asuntos_ab),
    ]

    resultados = {}
    for nombre, fn in demos:
        try:
            resultado = fn()
            resultados[nombre] = "OK"
        except Exception as e:
            print(f"\n  ERROR en '{nombre}': {e}")
            resultados[nombre] = f"ERROR: {e}"

    # Resumen final
    print(f"\n\n{SEP2}")
    print("   RESUMEN DE LA DEMO")
    print(f"{SEP2}")
    for nombre, estado in resultados.items():
        icono = "OK  " if estado == "OK" else "FAIL"
        print(f"  [{icono}] {nombre}")

    print(f"\n{SEP2}")
    print("   Demo completada")
    print(f"{SEP2}\n")


if __name__ == "__main__":
    main()
