"""
Servicio de Inteligencia Artificial — integración con Claude API.

Capacidades:
  1. generar_email()         — Email 100% personalizado según contexto del cliente
  2. analizar_cliente()      — Análisis profundo con razonamiento adaptativo
  3. mejorar_decision()      — Razonamiento sobre casos comerciales complejos
  4. auditar_email()         — Revisa y mejora un email antes de enviarlo
  5. generar_asunto_email()  — Genera líneas de asunto optimizadas (A/B testing)

Modelo: claude-opus-4-6 con thinking adaptativo para análisis complejos.
Credenciales: ANTHROPIC_API_KEY en .env (nunca en código).
"""
import os
import json
from typing import Optional

import anthropic
from pydantic import ValidationError

from backend.models.ia_models import (
    EmailGenerado, AnalisisIA, DecisionIA, AuditoriaEmailIA
)
from backend.core.logger import get_logger

logger = get_logger(__name__)

# ── Cliente Anthropic (singleton por módulo) ──────────────────────────────────
# La API key se lee de ANTHROPIC_API_KEY automáticamente
_client: Optional[anthropic.Anthropic] = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY no está configurada.\n"
                "Añade ANTHROPIC_API_KEY=sk-ant-... a tu archivo .env"
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ── Prompts del sistema ───────────────────────────────────────────────────────
# Se mantienen estables (sin fechas ni UUIDs) para aprovechar el caché de prompts.

SYSTEM_EMAIL = """Eres un experto en comunicación comercial B2B con 15 años de experiencia.
Tu especialidad es redactar emails que generan respuesta: directos, personalizados y con
propuesta de valor clara.

Reglas invariables:
- Nunca uses frases genéricas ("Espero que este email te encuentre bien")
- El asunto debe ser específico y crear curiosidad o urgencia real
- El cuerpo: máximo 3 párrafos cortos, un solo call-to-action
- Tono adaptado al tipo de cliente (empresa grande = formal, autónomo = cercano)
- Si el cliente lleva días sin responder, cambia el ángulo completamente
- Siempre responde en español"""

SYSTEM_ANALISIS = """Eres un director comercial senior con experiencia en análisis de pipelines
de ventas. Tu objetivo es dar análisis accionables, no teoría.

Evalúas clientes basándote en:
- Señales de comportamiento (cuándo responde, cómo responde, qué pregunta)
- Posición en el ciclo de venta y tiempo transcurrido
- Historial de contactos y resultados
- Factores de riesgo objetivos (sin especulación)

Siempre priorizas la honestidad sobre el optimismo. Si un lead está perdido, lo dices.
Siempre responde en español."""

SYSTEM_DECISION = """Eres un consultor estratégico comercial. Cuando alguien te presenta
un caso, analizas todas las variables y das UNA decisión clara con justificación sólida.

No das respuestas ambiguas. Si hay riesgo, lo cuantificas. Si hay alternativas mejores,
las presentas con pros y contras concretos.
Siempre responde en español."""


# ══════════════════════════════════════════════════════════════════════════════
# 1. GENERACIÓN DE EMAILS PERSONALIZADOS
# ══════════════════════════════════════════════════════════════════════════════

def generar_email(
    nombre_cliente:     str,
    empresa_cliente:    str,
    tipo_cliente:       str,           # particular | empresa | autonomo
    estado_comercial:   str,           # nuevo | interesado | sin_respuesta | etc.
    dias_sin_contacto:  int,
    historial_resumen:  str,           # Resumen de interacciones previas
    objetivo_email:     str,           # "primer contacto" | "recordatorio presupuesto" | etc.
    datos_empresa_emisora: dict,
    informacion_extra:  str = "",
) -> EmailGenerado:
    """
    Genera un email 100% personalizado usando Claude.
    Usa streaming para respuestas largas y structured outputs para garantizar
    que el JSON devuelto siempre tiene la estructura correcta.
    """
    cliente = _get_client()

    prompt_usuario = f"""
Genera un email comercial con estos datos:

DESTINATARIO:
- Nombre: {nombre_cliente}
- Empresa: {empresa_cliente or 'particular'}
- Tipo: {tipo_cliente}
- Estado actual: {estado_comercial}
- Días sin contacto: {dias_sin_contacto}

HISTORIAL:
{historial_resumen}

OBJETIVO DEL EMAIL:
{objetivo_email}

EMPRESA EMISORA:
- Nombre: {datos_empresa_emisora.get('nombre', '')}
- Servicios: {datos_empresa_emisora.get('servicios', 'Servicios tecnológicos')}

INFORMACIÓN ADICIONAL:
{informacion_extra or 'Ninguna'}

Devuelve ÚNICAMENTE un objeto JSON con esta estructura exacta:
{{
  "asunto": "línea de asunto del email",
  "cuerpo_html": "cuerpo completo en HTML con párrafos <p>, negritas <strong>, etc.",
  "cuerpo_texto": "versión texto plano sin HTML",
  "tono": "formal|amigable|urgente|reactivacion",
  "razonamiento": "explicación breve de por qué elegiste este enfoque"
}}
"""
    logger.info("Generando email con IA | cliente=%s | objetivo=%s",
                nombre_cliente, objetivo_email)

    # Streaming para respuestas largas
    with cliente.messages.stream(
        model            = "claude-opus-4-6",
        max_tokens       = 2048,
        system           = SYSTEM_EMAIL,
        messages         = [{"role": "user", "content": prompt_usuario}],
        thinking         = {"type": "adaptive"},
    ) as stream:
        respuesta = stream.get_final_message()

    # Extraer el texto JSON de la respuesta
    texto = next(
        (b.text for b in respuesta.content if b.type == "text"), ""
    )

    # Limpiar posibles bloques markdown ```json ... ```
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
        texto = texto.strip()

    datos = json.loads(texto)
    email = EmailGenerado(**datos)

    logger.info(
        "Email generado | tono=%s | tokens_entrada=%d | tokens_salida=%d",
        email.tono,
        respuesta.usage.input_tokens,
        respuesta.usage.output_tokens,
    )
    return email


# ══════════════════════════════════════════════════════════════════════════════
# 2. ANÁLISIS PROFUNDO DE CLIENTE
# ══════════════════════════════════════════════════════════════════════════════

def analizar_cliente(
    nombre_cliente:     str,
    empresa_cliente:    str,
    tipo_cliente:       str,
    estado_comercial:   str,
    score_actual:       int,
    dias_en_estado:     int,
    dias_sin_contacto:  int,
    total_contactos:    int,
    historial:          list[dict],    # Lista de eventos del seguimiento
    valor_presupuesto:  float = 0.0,
) -> AnalisisIA:
    """
    Análisis completo del cliente con razonamiento adaptativo.
    Claude usa thinking para evaluar todos los factores antes de responder.
    """
    cliente = _get_client()

    # Formatear historial para el prompt
    historial_texto = "\n".join([
        f"  - [{h.get('fecha', '?')}] {h.get('tipo_contacto', '?')}: "
        f"{h.get('descripcion', '')[:80]} → {h.get('resultado', '?')}"
        for h in (historial[-10:] if len(historial) > 10 else historial)
    ]) or "  Sin historial de contactos"

    prompt = f"""
Analiza este cliente del pipeline comercial:

DATOS DEL CLIENTE:
- Nombre/Empresa: {empresa_cliente or nombre_cliente}
- Tipo: {tipo_cliente}
- Estado: {estado_comercial}
- Score actual: {score_actual}/100
- Días en estado actual: {dias_en_estado}
- Días sin contacto: {dias_sin_contacto}
- Total contactos realizados: {total_contactos}
- Valor del presupuesto: {f"{valor_presupuesto:,.2f} €" if valor_presupuesto else "No definido"}

HISTORIAL DE INTERACCIONES (últimas 10):
{historial_texto}

Proporciona un análisis comercial completo. Devuelve ÚNICAMENTE este JSON:
{{
  "resumen_ejecutivo": "2-3 frases que resumen la situación real",
  "nivel_riesgo": "bajo|medio|alto|critico",
  "probabilidad_cierre": 0-100,
  "factores_positivos": ["factor1", "factor2", ...],
  "factores_negativos": ["factor1", "factor2", ...],
  "estrategia_recomendada": "descripción clara de la estrategia óptima",
  "proximos_pasos": ["paso concreto 1", "paso concreto 2", "paso concreto 3"],
  "tiempo_estimado_cierre": "estimación realista"
}}
"""

    logger.info("Analizando cliente con IA | cliente=%s | estado=%s",
                nombre_cliente, estado_comercial)

    # Thinking adaptativo para análisis complejos — Claude decide cuánto razonar
    with cliente.messages.stream(
        model    = "claude-opus-4-6",
        max_tokens = 4096,
        thinking = {"type": "adaptive"},
        system   = SYSTEM_ANALISIS,
        messages = [{"role": "user", "content": prompt}],
    ) as stream:
        respuesta = stream.get_final_message()

    texto = next((b.text for b in respuesta.content if b.type == "text"), "")
    texto = texto.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

    datos   = json.loads(texto)
    analisis = AnalisisIA(**datos)

    logger.info(
        "Analisis completado | riesgo=%s | prob_cierre=%d%% | thinking_tokens=%s",
        analisis.nivel_riesgo,
        analisis.probabilidad_cierre,
        next((b.thinking[:50] for b in respuesta.content
              if b.type == "thinking"), "sin thinking"),
    )
    return analisis


# ══════════════════════════════════════════════════════════════════════════════
# 3. MEJORA DE DECISIONES COMERCIALES
# ══════════════════════════════════════════════════════════════════════════════

def mejorar_decision(
    situacion:      str,
    opciones:       list[str],
    contexto_extra: str = "",
) -> DecisionIA:
    """
    Claude razona sobre una decisión comercial compleja y recomienda la mejor opción.
    Usa thinking adaptativo para explorar alternativas antes de decidir.
    """
    cliente = _get_client()

    opciones_texto = "\n".join(f"  {i+1}. {op}" for i, op in enumerate(opciones))

    prompt = f"""
SITUACIÓN COMERCIAL:
{situacion}

OPCIONES CONSIDERADAS:
{opciones_texto}

CONTEXTO ADICIONAL:
{contexto_extra or 'Sin contexto adicional'}

Analiza la situación y da una recomendación clara. Devuelve ÚNICAMENTE este JSON:
{{
  "decision": "la opción recomendada de forma concreta y accionable",
  "justificacion": "por qué esta es la mejor opción dado el contexto",
  "alternativas": ["alternativa viable 1", "alternativa viable 2"],
  "nivel_confianza": 0-100,
  "advertencias": ["riesgo o advertencia 1", "riesgo o advertencia 2"]
}}
"""

    logger.info("Consultando IA para decision | situacion=%.50s...", situacion)

    with cliente.messages.stream(
        model      = "claude-opus-4-6",
        max_tokens = 2048,
        thinking   = {"type": "adaptive"},
        system     = SYSTEM_DECISION,
        messages   = [{"role": "user", "content": prompt}],
    ) as stream:
        respuesta = stream.get_final_message()

    texto = next((b.text for b in respuesta.content if b.type == "text"), "")
    texto = texto.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

    datos    = json.loads(texto)
    decision = DecisionIA(**datos)

    logger.info("Decision IA | confianza=%d%% | decision=%.60s",
                decision.nivel_confianza, decision.decision)
    return decision


# ══════════════════════════════════════════════════════════════════════════════
# 4. AUDITORÍA DE EMAIL ANTES DE ENVIAR
# ══════════════════════════════════════════════════════════════════════════════

def auditar_email(
    asunto:       str,
    cuerpo:       str,
    contexto:     str = "",
) -> AuditoriaEmailIA:
    """
    Revisa un email antes de enviarlo.
    Detecta problemas, da puntuación y ofrece versión mejorada.
    """
    cliente = _get_client()

    prompt = f"""
Audita este email comercial y dame feedback accionable:

ASUNTO: {asunto}

CUERPO:
{cuerpo}

CONTEXTO: {contexto or 'Email comercial estándar'}

Evalúa: claridad, persuasión, longitud, CTA, tono, personalización.
Devuelve ÚNICAMENTE este JSON:
{{
  "puntuacion": 0-100,
  "problemas": ["problema concreto 1", "problema concreto 2"],
  "mejoras": ["mejora específica 1", "mejora específica 2"],
  "version_mejorada": "versión completa mejorada del cuerpo del email"
}}
"""

    respuesta = cliente.messages.create(
        model      = "claude-opus-4-6",
        max_tokens = 2048,
        system     = SYSTEM_EMAIL,
        messages   = [{"role": "user", "content": prompt}],
    )

    texto = next((b.text for b in respuesta.content if b.type == "text"), "")
    texto = texto.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

    datos = json.loads(texto)
    return AuditoriaEmailIA(**datos)


# ══════════════════════════════════════════════════════════════════════════════
# 5. GENERACIÓN DE ASUNTOS (A/B TESTING)
# ══════════════════════════════════════════════════════════════════════════════

def generar_asuntos_ab(
    contexto:       str,
    nombre_cliente: str,
    objetivo:       str,
    n_variantes:    int = 3,
) -> list[str]:
    """
    Genera N variantes de asunto para A/B testing.
    Útil para campañas masivas donde el asunto es crítico.
    """
    cliente = _get_client()

    prompt = f"""
Genera {n_variantes} variantes de asunto para un email a {nombre_cliente}.
Objetivo: {objetivo}
Contexto: {contexto}

Cada variante debe usar un enfoque distinto:
- Urgencia / escasez
- Curiosidad / pregunta
- Beneficio directo / valor

Devuelve ÚNICAMENTE un JSON array de strings:
["asunto variante 1", "asunto variante 2", "asunto variante 3"]
"""

    respuesta = cliente.messages.create(
        model      = "claude-opus-4-6",
        max_tokens = 512,
        messages   = [{"role": "user", "content": prompt}],
    )

    texto = next((b.text for b in respuesta.content if b.type == "text"), "[]")
    texto = texto.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(texto)
