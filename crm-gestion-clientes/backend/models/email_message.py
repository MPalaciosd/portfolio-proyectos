"""
Modelo de datos para mensajes de email.
Define la estructura de un email antes de enviarlo.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Adjunto:
    ruta:      str              # Ruta absoluta al archivo
    nombre:    Optional[str] = None  # Nombre que verá el destinatario (None = usar el del archivo)


@dataclass
class EmailMessage:
    destinatario:    str               # email@ejemplo.com
    asunto:          str
    cuerpo_html:     str               # Contenido HTML completo
    cuerpo_texto:    str = ""          # Fallback texto plano (accesibilidad)
    adjuntos:        list[Adjunto] = field(default_factory=list)
    cc:              list[str]    = field(default_factory=list)
    bcc:             list[str]    = field(default_factory=list)
    reply_to:        Optional[str] = None


@dataclass
class ResultadoEnvio:
    exito:           bool
    destinatario:    str
    asunto:          str
    intentos:        int  = 1
    error:           Optional[str] = None
    message_id:      Optional[str] = None
