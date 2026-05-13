"""
Motor de seguimiento comercial.

Tres responsabilidades:
  1. MÁQUINA DE ESTADOS   — gestiona transiciones válidas entre estados
  2. MOTOR DE REGLAS      — analiza cada cliente y genera acciones sugeridas
  3. AUTOMATIZACIÓN       — ejecuta acciones simples sin intervención humana

Lógica de negocio central del módulo de seguimiento.
"""
from datetime import datetime
from typing import Optional

from backend.models.seguimiento import (
    EstadoCliente, TipoAccion, TipoEvento, Prioridad,
    AccionSugerida, AnalisisCliente, RegistroSeguimiento, Evento,
)
from backend.repositories.seguimiento_repository import SeguimientoRepository
from backend.core.logger import get_logger

logger = get_logger(__name__)
_repo  = SeguimientoRepository()


# ══════════════════════════════════════════════════════════════════════════════
# 1. MÁQUINA DE ESTADOS
# Define qué transiciones son válidas y qué score asigna cada estado.
# ══════════════════════════════════════════════════════════════════════════════

# { estado_origen: { evento: (estado_destino, score_delta) } }
TRANSICIONES: dict[EstadoCliente, dict[TipoEvento, tuple[EstadoCliente, int]]] = {

    EstadoCliente.NUEVO: {
        TipoEvento.EMAIL_ENVIADO:       (EstadoCliente.CONTACTADO,        +10),
        TipoEvento.LLAMADA_REALIZADA:   (EstadoCliente.CONTACTADO,        +15),
        TipoEvento.LLAMADA_RECIBIDA:    (EstadoCliente.INTERESADO,        +30),  # Llama él primero
        TipoEvento.PRESUPUESTO_ENVIADO: (EstadoCliente.PROPUESTA_ENVIADA, +20),  # Directo a propuesta
        TipoEvento.SIN_RESPUESTA_DETECTADO: (EstadoCliente.SIN_RESPUESTA, -5),
    },
    EstadoCliente.CONTACTADO: {
        TipoEvento.EMAIL_RECIBIDO:      (EstadoCliente.INTERESADO,        +25),
        TipoEvento.LLAMADA_RECIBIDA:    (EstadoCliente.INTERESADO,        +30),
        TipoEvento.REUNION_REALIZADA:   (EstadoCliente.INTERESADO,        +35),
        TipoEvento.SIN_RESPUESTA_DETECTADO: (EstadoCliente.SIN_RESPUESTA, -10),
    },
    EstadoCliente.INTERESADO: {
        TipoEvento.PRESUPUESTO_ENVIADO: (EstadoCliente.PROPUESTA_ENVIADA, +20),
        TipoEvento.SIN_RESPUESTA_DETECTADO: (EstadoCliente.ENFRIADO,      -15),
    },
    EstadoCliente.PROPUESTA_ENVIADA: {
        TipoEvento.PRESUPUESTO_ACEPTADO: (EstadoCliente.NEGOCIACION,      +30),
        TipoEvento.PRESUPUESTO_RECHAZADO:(EstadoCliente.CERRADO_PERDIDO,  -50),
        TipoEvento.REUNION_REALIZADA:    (EstadoCliente.NEGOCIACION,      +20),
        TipoEvento.SIN_RESPUESTA_DETECTADO: (EstadoCliente.ENFRIADO,      -10),
    },
    EstadoCliente.NEGOCIACION: {
        TipoEvento.PRESUPUESTO_ACEPTADO: (EstadoCliente.CERRADO_GANADO,  +40),
        TipoEvento.PRESUPUESTO_RECHAZADO:(EstadoCliente.CERRADO_PERDIDO, -40),
        TipoEvento.PERDIDO:              (EstadoCliente.CERRADO_PERDIDO, -40),
    },
    EstadoCliente.SIN_RESPUESTA: {
        TipoEvento.EMAIL_RECIBIDO:       (EstadoCliente.INTERESADO,       +20),
        TipoEvento.LLAMADA_RECIBIDA:     (EstadoCliente.INTERESADO,       +25),
        TipoEvento.REACTIVACION_EXITOSA: (EstadoCliente.INTERESADO,       +20),
        TipoEvento.PERDIDO:              (EstadoCliente.CERRADO_PERDIDO,  -20),
    },
    EstadoCliente.ENFRIADO: {
        TipoEvento.EMAIL_RECIBIDO:       (EstadoCliente.INTERESADO,       +15),
        TipoEvento.REACTIVACION_EXITOSA: (EstadoCliente.CONTACTADO,       +10),
        TipoEvento.PERDIDO:              (EstadoCliente.CERRADO_PERDIDO,  -20),
    },
    # Estados terminales — sin transiciones salientes
    EstadoCliente.CERRADO_GANADO:  {},
    EstadoCliente.CERRADO_PERDIDO: {},
}


# ══════════════════════════════════════════════════════════════════════════════
# 2. MOTOR DE REGLAS
# Reglas en formato: (condición_fn, AccionSugerida)
# Se evalúan en orden; se devuelven todas las que se cumplan.
# ══════════════════════════════════════════════════════════════════════════════

def _reglas(estado: EstadoCliente, dias_estado: int, dias_contacto: int,
            n_contactos: int) -> list[AccionSugerida]:
    """
    Evalúa el contexto del cliente y devuelve las acciones recomendadas.
    Las reglas están ordenadas de mayor a menor prioridad.
    """
    acciones: list[AccionSugerida] = []

    # ── NUEVO ─────────────────────────────────────────────────────────────────
    if estado == EstadoCliente.NUEVO and dias_estado == 0:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.EMAIL, prioridad=Prioridad.ALTA,
            titulo="Enviar email de bienvenida",
            descripcion="El cliente acaba de entrar. Envía un email de presentación "
                        "personalizado en las próximas 2 horas.",
            plazo_dias=0, automatizable=True,
        ))

    if estado == EstadoCliente.NUEVO and dias_estado >= 1:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.LLAMADA, prioridad=Prioridad.CRITICA,
            titulo="Primer contacto telefónico urgente",
            descripcion=f"Llevas {dias_estado} día(s) sin contactar a este cliente nuevo. "
                        "Llama hoy para no perder la oportunidad inicial.",
            plazo_dias=0, automatizable=False,
        ))

    # ── CONTACTADO ────────────────────────────────────────────────────────────
    if estado == EstadoCliente.CONTACTADO and 3 <= dias_contacto <= 5:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.EMAIL, prioridad=Prioridad.ALTA,
            titulo="Seguimiento tras primer contacto",
            descripcion="Han pasado varios días desde el primer contacto sin respuesta. "
                        "Envía un email breve preguntando si recibió tu mensaje.",
            plazo_dias=1, automatizable=True,
        ))

    if estado == EstadoCliente.CONTACTADO and dias_contacto > 5:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.LLAMADA, prioridad=Prioridad.ALTA,
            titulo="Llamada de seguimiento — riesgo de pérdida",
            descripcion=f"{dias_contacto} días sin respuesta. El email no funcionó. "
                        "Intenta contacto telefónico directo.",
            plazo_dias=0, automatizable=False,
        ))

    # ── INTERESADO ────────────────────────────────────────────────────────────
    if estado == EstadoCliente.INTERESADO and n_contactos >= 1 and dias_contacto <= 2:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.PROPUESTA, prioridad=Prioridad.ALTA,
            titulo="Preparar y enviar propuesta/presupuesto",
            descripcion="El cliente está interesado. Es el momento de enviar una propuesta "
                        "concreta antes de que el interés disminuya.",
            plazo_dias=2, automatizable=False,
        ))

    if estado == EstadoCliente.INTERESADO and dias_contacto > 7:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.LLAMADA, prioridad=Prioridad.CRITICA,
            titulo="Reactivar cliente interesado — URGENTE",
            descripcion=f"{dias_contacto} días sin contacto en estado 'Interesado'. "
                        "Alto riesgo de enfriamiento. Llama hoy.",
            plazo_dias=0, automatizable=False,
        ))

    # ── PROPUESTA ENVIADA ─────────────────────────────────────────────────────
    if estado == EstadoCliente.PROPUESTA_ENVIADA and dias_contacto == 3:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.EMAIL_AUTOMATICO, prioridad=Prioridad.MEDIA,
            titulo="Recordatorio automático del presupuesto",
            descripcion="Han pasado 3 días desde el envío del presupuesto. "
                        "Envía recordatorio automático con el PDF adjunto.",
            plazo_dias=0, automatizable=True,
        ))

    if estado == EstadoCliente.PROPUESTA_ENVIADA and 7 <= dias_contacto <= 14:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.LLAMADA, prioridad=Prioridad.ALTA,
            titulo="Llamada para resolver dudas del presupuesto",
            descripcion=f"El presupuesto lleva {dias_contacto} días sin respuesta. "
                        "Una llamada puede resolver objeciones y desbloquear la decisión.",
            plazo_dias=1, automatizable=False,
        ))

    if estado == EstadoCliente.PROPUESTA_ENVIADA and dias_contacto > 14:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.REUNION, prioridad=Prioridad.CRITICA,
            titulo="Proponer reunión de cierre",
            descripcion=f"{dias_contacto} días esperando respuesta al presupuesto. "
                        "Propón una reunión presencial o videollamada para cerrar.",
            plazo_dias=0, automatizable=False,
        ))

    # ── NEGOCIACIÓN ───────────────────────────────────────────────────────────
    if estado == EstadoCliente.NEGOCIACION:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.CIERRE, prioridad=Prioridad.CRITICA,
            titulo="Gestionar cierre activamente",
            descripcion="Cliente en negociación. Acuerda condiciones finales, plazos y forma "
                        "de pago. Prepara contrato o pedido.",
            plazo_dias=3, automatizable=False,
        ))
        if dias_contacto > 5:
            acciones.append(AccionSugerida(
                tipo=TipoAccion.LLAMADA, prioridad=Prioridad.CRITICA,
                titulo="Llamada urgente de cierre",
                descripcion=f"{dias_contacto} días en negociación sin contacto. "
                            "Una negociación paralizada suele perderse.",
                plazo_dias=0, automatizable=False,
            ))

    # ── SIN RESPUESTA ─────────────────────────────────────────────────────────
    if estado == EstadoCliente.SIN_RESPUESTA and dias_estado <= 7:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.EMAIL_AUTOMATICO, prioridad=Prioridad.MEDIA,
            titulo="Email de reactivación automático",
            descripcion="El cliente no ha respondido. Envía un email de reactivación "
                        "con tono diferente al anterior (más directo o con oferta).",
            plazo_dias=1, automatizable=True,
        ))

    if estado == EstadoCliente.SIN_RESPUESTA and dias_estado > 7:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.LLAMADA, prioridad=Prioridad.ALTA,
            titulo="Último intento — llamada directa",
            descripcion=f"{dias_estado} días sin respuesta. Intenta llamar. "
                        "Si no responde, considera marcarlo como perdido.",
            plazo_dias=0, automatizable=False,
        ))

    if estado == EstadoCliente.SIN_RESPUESTA and dias_estado > 30:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.NINGUNA, prioridad=Prioridad.BAJA,
            titulo="Considerar cierre como perdido",
            descripcion=f"Más de 30 días sin respuesta ({dias_estado} días). "
                        "Libera tiempo cerrando este lead como perdido.",
            plazo_dias=7, automatizable=True,
        ))

    # ── ENFRIADO ──────────────────────────────────────────────────────────────
    if estado == EstadoCliente.ENFRIADO and dias_estado <= 30:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.REACTIVACION, prioridad=Prioridad.MEDIA,
            titulo="Campaña de reactivación",
            descripcion="El cliente perdió interés. Envía contenido de valor: "
                        "caso de éxito similar, nueva oferta o descuento temporal.",
            plazo_dias=3, automatizable=True,
        ))

    if estado == EstadoCliente.ENFRIADO and dias_estado > 60:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.NINGUNA, prioridad=Prioridad.BAJA,
            titulo="Archivar — sin actividad prolongada",
            descripcion=f"{dias_estado} días enfriado. Archiva el lead para limpiar el pipeline.",
            plazo_dias=14, automatizable=True,
        ))

    # Si no hay reglas aplicables
    if not acciones:
        acciones.append(AccionSugerida(
            tipo=TipoAccion.SEGUIMIENTO, prioridad=Prioridad.BAJA,
            titulo="Revisión periódica",
            descripcion="No hay acciones urgentes. Revisa el estado del cliente "
                        "en la próxima ronda de seguimiento.",
            plazo_dias=7, automatizable=False,
        ))

    return acciones


# ══════════════════════════════════════════════════════════════════════════════
# 3. SERVICIO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class SeguimientoService:

    # ── Registrar evento y aplicar transición ─────────────────────────────────

    def registrar_evento(
        self,
        cliente_id:  int,
        evento_tipo: TipoEvento,
        descripcion: str = "",
        usuario:     str = "sistema",
    ) -> dict:
        """
        Procesa un evento sobre un cliente:
          1. Obtiene estado actual
          2. Busca transición válida
          3. Aplica la transición y actualiza score
          4. Registra el evento en seguimientos
          5. Devuelve resumen del cambio
        """
        info = _repo.estado_cliente(cliente_id)
        if not info:
            raise ValueError(f"Cliente {cliente_id} no encontrado")

        estado_actual = EstadoCliente(info["estado_comercial"] or "nuevo")
        score_actual  = info["score_interes"] or 0

        transicion = TRANSICIONES.get(estado_actual, {}).get(evento_tipo)

        if transicion:
            nuevo_estado, delta_score = transicion
            nuevo_score = max(0, min(100, score_actual + delta_score))
            _repo.actualizar_estado(cliente_id, nuevo_estado, nuevo_score)
            estado_resultado = nuevo_estado
            hubo_transicion  = True
        else:
            # Evento sin transición definida — solo registrar
            estado_resultado = estado_actual
            hubo_transicion  = False

        # Registrar en historial
        _repo.registrar(RegistroSeguimiento(
            cliente_id    = cliente_id,
            estado        = estado_resultado,
            tipo_contacto = _evento_a_accion(evento_tipo),
            descripcion   = descripcion or f"Evento: {evento_tipo.value}",
            resultado     = _evento_a_resultado(evento_tipo),
            usuario       = usuario,
        ))

        logger.info(
            "Evento registrado | cliente=%d | evento=%s | %s->%s | score=%d",
            cliente_id, evento_tipo.value,
            estado_actual.value, estado_resultado.value, nuevo_score if transicion else score_actual,
        )

        return {
            "cliente_id":       cliente_id,
            "evento":           evento_tipo.value,
            "estado_anterior":  estado_actual.value,
            "estado_nuevo":     estado_resultado.value,
            "hubo_transicion":  hubo_transicion,
            "score":            nuevo_score if transicion else score_actual,
        }

    # ── Analizar un cliente ───────────────────────────────────────────────────

    def analizar_cliente(self, cliente_id: int) -> AnalisisCliente:
        """
        Devuelve el análisis completo de un cliente:
        estado, días sin contacto, acciones sugeridas y score.
        """
        info = _repo.estado_cliente(cliente_id)
        if not info:
            raise ValueError(f"Cliente {cliente_id} no encontrado")

        estado         = EstadoCliente(info["estado_comercial"] or "nuevo")
        dias_estado    = _repo.dias_en_estado(cliente_id)
        dias_contacto  = _repo.dias_sin_contacto(cliente_id)
        n_contactos    = _repo.total_contactos(cliente_id)
        score          = info["score_interes"] or 0

        acciones = _reglas(estado, dias_estado, dias_contacto, n_contactos)

        # Alerta si hay acción crítica
        criticas = [a for a in acciones if a.prioridad == Prioridad.CRITICA]
        alerta = criticas[0].titulo if criticas else None

        nombre = info.get("empresa") or f"{info['nombre']} {info['apellidos']}"

        return AnalisisCliente(
            cliente_id         = cliente_id,
            nombre_cliente     = nombre,
            estado_actual      = estado,
            estado_anterior    = None,
            dias_en_estado     = dias_estado,
            dias_sin_contacto  = dias_contacto,
            total_contactos    = n_contactos,
            acciones_sugeridas = acciones,
            alerta             = alerta,
            score_interes      = score,
        )

    # ── Ejecutar automatizaciones ─────────────────────────────────────────────

    def ejecutar_automatizaciones(self, email_service=None) -> dict:
        """
        Recorre todos los clientes activos y ejecuta acciones automatizables:
          - Envía emails de bienvenida a clientes NUEVO
          - Envía recordatorios a PROPUESTA_ENVIADA con 3 días sin respuesta
          - Marca como SIN_RESPUESTA a CONTACTADO con > 7 días sin contacto
          - Marca como ENFRIADO a INTERESADO con > 14 días sin contacto
          - Cierra como PERDIDO clientes SIN_RESPUESTA con > 30 días
        """
        resultados = {
            "bienvenidas":    0,
            "recordatorios":  0,
            "sin_respuesta":  0,
            "enfriados":      0,
            "cerrados":       0,
            "errores":        0,
        }

        # Regla 1 — Nuevos sin contactar: enviar bienvenida
        for c in _repo.clientes_por_estado(EstadoCliente.NUEVO):
            try:
                if email_service:
                    email_service.enviar_bienvenida(
                        cliente_email  = c["email"],
                        nombre_cliente = c["nombre"],
                        empresa_cliente= c.get("empresa", ""),
                    )
                self.registrar_evento(
                    c["id"], TipoEvento.EMAIL_ENVIADO,
                    "Email de bienvenida automático enviado",
                )
                resultados["bienvenidas"] += 1
                logger.info("Bienvenida enviada | cliente=%d | email=%s", c["id"], c["email"])
            except Exception as e:
                resultados["errores"] += 1
                logger.error("Error bienvenida | cliente=%d | %s", c["id"], e)

        # Regla 2 — Propuesta enviada hace 3 días: recordatorio automático
        for c in _repo.clientes_por_estado(EstadoCliente.PROPUESTA_ENVIADA):
            dias = _repo.dias_sin_contacto(c["id"])
            if dias == 3:
                try:
                    if email_service:
                        email_service.enviar_recordatorio(
                            cliente_email      = c["email"],
                            nombre_cliente     = c["nombre"],
                            numero_presupuesto = "PRES-PENDIENTE",
                            total              = "—",
                            fecha_validez      = "—",
                            dias_pendiente     = dias,
                        )
                    resultados["recordatorios"] += 1
                    logger.info("Recordatorio enviado | cliente=%d", c["id"])
                except Exception as e:
                    resultados["errores"] += 1
                    logger.error("Error recordatorio | cliente=%d | %s", c["id"], e)

        # Regla 3 — Contactado sin respuesta > 7 días → SIN_RESPUESTA
        for c in _repo.clientes_por_estado(EstadoCliente.CONTACTADO):
            if _repo.dias_sin_contacto(c["id"]) > 7:
                self.registrar_evento(
                    c["id"], TipoEvento.SIN_RESPUESTA_DETECTADO,
                    "Marcado automáticamente: sin respuesta > 7 días",
                )
                resultados["sin_respuesta"] += 1

        # Regla 4 — Interesado sin contacto > 14 días → ENFRIADO
        for c in _repo.clientes_por_estado(EstadoCliente.INTERESADO):
            if _repo.dias_sin_contacto(c["id"]) > 14:
                self.registrar_evento(
                    c["id"], TipoEvento.SIN_RESPUESTA_DETECTADO,
                    "Marcado automáticamente: interesado enfriado > 14 días",
                )
                resultados["enfriados"] += 1

        # Regla 5 — Sin respuesta > 30 días → CERRADO_PERDIDO
        for c in _repo.clientes_por_estado(EstadoCliente.SIN_RESPUESTA):
            if _repo.dias_en_estado(c["id"]) > 30:
                self.registrar_evento(
                    c["id"], TipoEvento.PERDIDO,
                    "Cierre automático: sin respuesta durante más de 30 días",
                )
                resultados["cerrados"] += 1

        logger.info("Automatizacion completada | %s", resultados)
        return resultados

    # ── Dashboard del pipeline ────────────────────────────────────────────────

    def pipeline_resumen(self) -> dict:
        """Resumen de todos los estados del pipeline comercial."""
        resumen = {}
        for estado in EstadoCliente:
            clientes = _repo.clientes_por_estado(estado)
            resumen[estado.value] = {
                "total":    len(clientes),
                "clientes": [
                    {
                        "id":     c["id"],
                        "nombre": c.get("empresa") or f"{c['nombre']} {c['apellidos']}",
                        "score":  c.get("score_interes", 0),
                        "dias_sin_contacto": _repo.dias_sin_contacto(c["id"]),
                    }
                    for c in clientes
                ],
            }
        return resumen

    # ── Historial ─────────────────────────────────────────────────────────────

    def historial(self, cliente_id: int) -> list[dict]:
        return _repo.historial_cliente(cliente_id)


# ── Helpers privados ──────────────────────────────────────────────────────────

def _evento_a_accion(evento: TipoEvento) -> TipoAccion:
    mapa = {
        TipoEvento.EMAIL_ENVIADO:       TipoAccion.EMAIL,
        TipoEvento.EMAIL_RECIBIDO:      TipoAccion.EMAIL,
        TipoEvento.LLAMADA_REALIZADA:   TipoAccion.LLAMADA,
        TipoEvento.LLAMADA_RECIBIDA:    TipoAccion.LLAMADA,
        TipoEvento.REUNION_REALIZADA:   TipoAccion.REUNION,
        TipoEvento.PRESUPUESTO_ENVIADO: TipoAccion.PROPUESTA,
        TipoEvento.PRESUPUESTO_ACEPTADO:TipoAccion.CIERRE,
        TipoEvento.PRESUPUESTO_RECHAZADO:TipoAccion.NINGUNA,
        TipoEvento.SIN_RESPUESTA_DETECTADO: TipoAccion.SEGUIMIENTO,
        TipoEvento.REACTIVACION_EXITOSA: TipoAccion.REACTIVACION,
        TipoEvento.PERDIDO:             TipoAccion.NINGUNA,
    }
    return mapa.get(evento, TipoAccion.SEGUIMIENTO)


def _evento_a_resultado(evento: TipoEvento) -> str:
    positivos = {
        TipoEvento.EMAIL_RECIBIDO, TipoEvento.LLAMADA_RECIBIDA,
        TipoEvento.REUNION_REALIZADA, TipoEvento.PRESUPUESTO_ACEPTADO,
        TipoEvento.REACTIVACION_EXITOSA,
    }
    negativos = {
        TipoEvento.PRESUPUESTO_RECHAZADO, TipoEvento.PERDIDO,
    }
    sin_resp  = {TipoEvento.SIN_RESPUESTA_DETECTADO}
    if evento in positivos: return "positivo"
    if evento in negativos: return "negativo"
    if evento in sin_resp:  return "sin_respuesta"
    return "neutro"
