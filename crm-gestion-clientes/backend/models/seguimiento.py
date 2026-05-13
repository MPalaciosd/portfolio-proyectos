"""
Modelos del sistema de seguimiento comercial.
Define estados, eventos, acciones sugeridas y reglas de transición.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Estados del ciclo de vida comercial ──────────────────────────────────────

class EstadoCliente(str, Enum):
    """
    Máquina de estados del cliente en el proceso comercial.

    NUEVO ──► CONTACTADO ──► INTERESADO ──► PROPUESTA_ENVIADA
                │                │                  │
                ▼                ▼                  ▼
          SIN_RESPUESTA      ENFRIADO        NEGOCIACION
                                                    │
                                        ┌───────────┴───────────┐
                                        ▼                       ▼
                                  CERRADO_GANADO        CERRADO_PERDIDO
    """
    NUEVO             = "nuevo"             # Acaba de entrar en el CRM
    CONTACTADO        = "contactado"        # Se le ha enviado un primer contacto
    INTERESADO        = "interesado"        # Ha respondido positivamente
    PROPUESTA_ENVIADA = "propuesta_enviada" # Se le envió presupuesto/propuesta
    NEGOCIACION       = "negociacion"       # Está negociando condiciones
    CERRADO_GANADO    = "cerrado_ganado"    # Aceptó — cliente activo
    CERRADO_PERDIDO   = "cerrado_perdido"   # Rechazó o se fue
    SIN_RESPUESTA     = "sin_respuesta"     # No ha respondido tras N días
    ENFRIADO          = "enfriado"          # Perdió interés sin cerrar


class TipoAccion(str, Enum):
    LLAMADA         = "llamada"
    EMAIL           = "email"
    EMAIL_AUTOMATICO = "email_automatico"
    REUNION         = "reunion"
    PROPUESTA       = "propuesta"
    SEGUIMIENTO     = "seguimiento"
    CIERRE          = "cierre"
    REACTIVACION    = "reactivacion"
    NINGUNA         = "ninguna"


class Prioridad(str, Enum):
    CRITICA = "critica"   # Actuar hoy
    ALTA    = "alta"      # Actuar esta semana
    MEDIA   = "media"     # Planificar próxima semana
    BAJA    = "baja"      # Cuando haya tiempo


# ── Eventos que provocan transiciones ────────────────────────────────────────

class TipoEvento(str, Enum):
    CLIENTE_CREADO        = "cliente_creado"
    EMAIL_ENVIADO         = "email_enviado"
    EMAIL_RECIBIDO        = "email_recibido"
    LLAMADA_REALIZADA     = "llamada_realizada"
    LLAMADA_RECIBIDA      = "llamada_recibida"
    REUNION_REALIZADA     = "reunion_realizada"
    PRESUPUESTO_ENVIADO   = "presupuesto_enviado"
    PRESUPUESTO_ACEPTADO  = "presupuesto_aceptado"
    PRESUPUESTO_RECHAZADO = "presupuesto_rechazado"
    SIN_RESPUESTA_DETECTADO = "sin_respuesta_detectado"
    REACTIVACION_EXITOSA  = "reactivacion_exitosa"
    PERDIDO               = "perdido"


# ── Modelos de datos ─────────────────────────────────────────────────────────

@dataclass
class Evento:
    tipo:        TipoEvento
    cliente_id:  int
    fecha:       str          # ISO: "2024-11-15 10:30:00"
    descripcion: str = ""
    usuario:     str = "sistema"
    datos_extra: dict = field(default_factory=dict)


@dataclass
class AccionSugerida:
    tipo:        TipoAccion
    prioridad:   Prioridad
    titulo:      str
    descripcion: str
    plazo_dias:  int          # En cuántos días realizarla
    automatizable: bool = False   # Si el sistema puede ejecutarla solo


@dataclass
class AnalisisCliente:
    cliente_id:          int
    nombre_cliente:      str
    estado_actual:       EstadoCliente
    estado_anterior:     Optional[EstadoCliente]
    dias_en_estado:      int
    dias_sin_contacto:   int
    total_contactos:     int
    acciones_sugeridas:  list[AccionSugerida]
    alerta:              Optional[str]        # Mensaje de alerta si es urgente
    score_interes:       int                  # 0-100: probabilidad de cierre


@dataclass
class RegistroSeguimiento:
    """Fila de la tabla seguimientos en la DB."""
    cliente_id:    int
    estado:        EstadoCliente
    tipo_contacto: TipoAccion
    descripcion:   str
    resultado:     str          # positivo | negativo | neutro | sin_respuesta
    fecha:         Optional[str] = None
    id:            Optional[int] = None
    usuario:       str          = "sistema"
    proximo_contacto: Optional[str] = None
