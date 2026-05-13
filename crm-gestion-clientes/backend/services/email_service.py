"""
Servicio de envío de emails vía SMTP.

Características:
  - Conexión STARTTLS (puerto 587) o SSL (puerto 465)
  - Multipart: HTML + texto plano (fallback para clientes que no soporten HTML)
  - Adjuntos de cualquier tipo MIME detectado automáticamente
  - Reintentos automáticos configurables
  - Modo test: loguea sin enviar (útil en desarrollo)
  - Credenciales SIEMPRE desde variables de entorno
"""
import os
import re
import time
import uuid
import mimetypes
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.base      import MIMEBase
from email.mime.image     import MIMEImage
from email                import encoders
from email.utils          import formataddr, formatdate, make_msgid
from typing               import Optional

from backend.models.email_message   import EmailMessage, Adjunto, ResultadoEnvio
from backend.services.template_service import TemplateService
from backend.core.logger            import get_logger

logger = get_logger(__name__)

# ── Configuración desde entorno ───────────────────────────────────────────────

def _env(clave: str, defecto: str = "") -> str:
    return os.environ.get(clave, defecto).strip()

class SMTPConfig:
    host:            str   = _env("SMTP_HOST",      "smtp.gmail.com")
    port:            int   = int(_env("SMTP_PORT",  "587"))
    user:            str   = _env("SMTP_USER",      "")
    password:        str   = _env("SMTP_PASSWORD",  "")
    from_name:       str   = _env("SMTP_FROM_NAME", "CRM-ASIR")
    reply_to:        str   = _env("SMTP_REPLY_TO",  "")
    test_mode:       bool  = _env("EMAIL_TEST_MODE", "false").lower() == "true"
    retry_attempts:  int   = int(_env("EMAIL_RETRY_ATTEMPTS", "3"))
    retry_delay:     int   = int(_env("EMAIL_RETRY_DELAY",    "5"))


# ── Datos de la empresa emisora (para las plantillas) ─────────────────────────

DATOS_EMPRESA = {
    "empresa_nombre":    _env("SMTP_FROM_NAME",  "TechSoluciones S.L."),
    "empresa_email":     _env("SMTP_USER",       "info@techsoluciones.es"),
    "empresa_telefono":  _env("EMPRESA_TEL",     "+34 91 123 45 67"),
    "empresa_nif":       _env("EMPRESA_NIF",     "B12345678"),
    "empresa_direccion": _env("EMPRESA_DIR",     "Calle Mayor, 42"),
    "empresa_ciudad":    _env("EMPRESA_CIUDAD",  "Madrid"),
    "empresa_web":       _env("EMPRESA_WEB",     "www.techsoluciones.es"),
}


class EmailService:

    def __init__(self, config: SMTPConfig = None):
        self.config   = config or SMTPConfig()
        self.plantillas = TemplateService()

    # ── Conexión SMTP ─────────────────────────────────────────────────────────

    def _conectar(self) -> smtplib.SMTP:
        """
        Establece conexión segura SMTP.
        Puerto 587 → STARTTLS (más compatible).
        Puerto 465 → SSL desde el inicio.
        """
        cfg = self.config

        if cfg.port == 465:
            # SSL directo
            conn = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=15)
            logger.debug("Conexión SMTP SSL establecida: %s:%s", cfg.host, cfg.port)
        else:
            # STARTTLS (587 o 25)
            conn = smtplib.SMTP(cfg.host, cfg.port, timeout=15)
            conn.ehlo()          # Identificarse con el servidor
            conn.starttls()      # Elevar a TLS — TODA la sesión queda cifrada
            conn.ehlo()          # Volver a identificarse tras TLS
            logger.debug("Conexión SMTP STARTTLS establecida: %s:%s", cfg.host, cfg.port)

        conn.login(cfg.user, cfg.password)
        return conn

    # ── Construcción del mensaje ──────────────────────────────────────────────

    def _construir_mime(self, mensaje: EmailMessage) -> MIMEMultipart:
        """Construye el objeto MIME completo listo para enviar."""
        cfg  = self.config
        mime = MIMEMultipart("mixed")

        # Cabeceras estándar
        mime["From"]       = formataddr((cfg.from_name, cfg.user))
        mime["To"]         = mensaje.destinatario
        mime["Subject"]    = mensaje.asunto
        mime["Date"]       = formatdate(localtime=True)
        mime["Message-ID"] = make_msgid(domain=cfg.user.split("@")[-1])

        if mensaje.reply_to or cfg.reply_to:
            mime["Reply-To"] = mensaje.reply_to or cfg.reply_to

        if mensaje.cc:
            mime["Cc"] = ", ".join(mensaje.cc)

        # Cabeceras anti-spam
        mime["X-Mailer"]   = "CRM-ASIR/1.0 Python"
        mime["Precedence"] = "bulk"

        # Parte alternativa: texto plano + HTML
        alternativa = MIMEMultipart("alternative")
        if mensaje.cuerpo_texto:
            alternativa.attach(MIMEText(mensaje.cuerpo_texto, "plain", "utf-8"))
        alternativa.attach(MIMEText(mensaje.cuerpo_html, "html", "utf-8"))
        mime.attach(alternativa)

        # Adjuntos
        for adjunto in mensaje.adjuntos:
            self._adjuntar_archivo(mime, adjunto)

        return mime

    def _adjuntar_archivo(self, mime: MIMEMultipart, adjunto: Adjunto) -> None:
        """
        Adjunta un archivo al mensaje.
        Detecta el tipo MIME automáticamente.
        PDFs e imágenes reciben tratamiento especial para mejor compatibilidad.
        """
        if not os.path.exists(adjunto.ruta):
            logger.warning("Adjunto no encontrado, omitido: %s", adjunto.ruta)
            return

        nombre_mostrar = adjunto.nombre or os.path.basename(adjunto.ruta)
        tipo_mime, _   = mimetypes.guess_type(adjunto.ruta)
        tipo_mime      = tipo_mime or "application/octet-stream"

        with open(adjunto.ruta, "rb") as f:
            datos = f.read()

        tipo_principal, subtipo = tipo_mime.split("/", 1)

        if tipo_principal == "image":
            parte = MIMEImage(datos, _subtype=subtipo)
        else:
            parte = MIMEBase(tipo_principal, subtipo)
            parte.set_payload(datos)
            encoders.encode_base64(parte)

        parte.add_header(
            "Content-Disposition", "attachment",
            filename=nombre_mostrar,
        )
        mime.attach(parte)
        logger.debug("Adjunto añadido: %s (%s, %.1f KB)",
                     nombre_mostrar, tipo_mime, len(datos)/1024)

    # ── Envío con reintentos ──────────────────────────────────────────────────

    def enviar(self, mensaje: EmailMessage) -> ResultadoEnvio:
        """
        Envía un email con reintentos automáticos.
        En modo test, loguea el mensaje sin enviarlo.
        """
        cfg = self.config

        # ── Modo test ──────────────────────────────────────────────────────
        if cfg.test_mode:
            logger.info(
                "[TEST MODE] Email NO enviado | para=%s | asunto=%s | adjuntos=%d",
                mensaje.destinatario, mensaje.asunto, len(mensaje.adjuntos)
            )
            return ResultadoEnvio(
                exito=True, destinatario=mensaje.destinatario,
                asunto=mensaje.asunto, message_id="test-mode",
            )

        # ── Validación mínima ──────────────────────────────────────────────
        if not cfg.user or not cfg.password:
            error = "SMTP_USER y SMTP_PASSWORD no configurados en .env"
            logger.error(error)
            return ResultadoEnvio(
                exito=False, destinatario=mensaje.destinatario,
                asunto=mensaje.asunto, error=error,
            )

        mime = self._construir_mime(mensaje)

        # Todos los destinatarios (To + CC + BCC)
        todos_destinos = [mensaje.destinatario] + mensaje.cc + mensaje.bcc

        # ── Reintentos ─────────────────────────────────────────────────────
        ultimo_error = None
        for intento in range(1, cfg.retry_attempts + 1):
            try:
                with self._conectar() as conn:
                    conn.sendmail(cfg.user, todos_destinos, mime.as_bytes())

                msg_id = mime["Message-ID"]
                logger.info(
                    "Email enviado OK | intento=%d | para=%s | asunto=%s | msg_id=%s",
                    intento, mensaje.destinatario, mensaje.asunto, msg_id,
                )
                return ResultadoEnvio(
                    exito=True, destinatario=mensaje.destinatario,
                    asunto=mensaje.asunto, intentos=intento, message_id=msg_id,
                )

            except smtplib.SMTPAuthenticationError:
                # Error de credenciales — no tiene sentido reintentar
                error = "Autenticación SMTP fallida. Revise SMTP_USER y SMTP_PASSWORD en .env"
                logger.error(error)
                return ResultadoEnvio(
                    exito=False, destinatario=mensaje.destinatario,
                    asunto=mensaje.asunto, intentos=intento, error=error,
                )

            except (smtplib.SMTPException, OSError) as e:
                ultimo_error = str(e)
                logger.warning(
                    "Intento %d/%d fallido | para=%s | error=%s",
                    intento, cfg.retry_attempts, mensaje.destinatario, ultimo_error,
                )
                if intento < cfg.retry_attempts:
                    time.sleep(cfg.retry_delay)

        return ResultadoEnvio(
            exito=False, destinatario=mensaje.destinatario,
            asunto=mensaje.asunto, intentos=cfg.retry_attempts,
            error=f"Fallido tras {cfg.retry_attempts} intentos: {ultimo_error}",
        )

    # ── Métodos de alto nivel (usan plantillas) ───────────────────────────────

    def enviar_presupuesto(
        self,
        cliente_email:     str,
        nombre_cliente:    str,
        numero_presupuesto: str,
        total:             str,
        fecha_validez:     str,
        ruta_pdf:          str,
        condiciones_pago:  str = "Pago a 30 días",
        notas_extra:       str = "",
        nombre_comercial:  str = "Nuestro equipo",
    ) -> ResultadoEnvio:
        """Envía presupuesto con PDF adjunto usando la plantilla 'presupuesto_nuevo'."""

        variables = {
            "nombre_cliente":      nombre_cliente,
            "numero_presupuesto":  numero_presupuesto,
            "total":               total,
            "fecha_validez":       fecha_validez,
            "condiciones_pago":    condiciones_pago,
            "notas_extra":         notas_extra,
            "nombre_comercial":    nombre_comercial,
            "nombre_archivo_pdf":  os.path.basename(ruta_pdf),
            "asunto":              f"Presupuesto {numero_presupuesto} — {DATOS_EMPRESA['empresa_nombre']}",
        }

        html, texto = self.plantillas.renderizar(
            "presupuesto_nuevo", variables, DATOS_EMPRESA
        )

        mensaje = EmailMessage(
            destinatario = cliente_email,
            asunto       = variables["asunto"],
            cuerpo_html  = html,
            cuerpo_texto = texto,
            adjuntos     = [Adjunto(ruta=ruta_pdf)],
        )
        return self.enviar(mensaje)

    def enviar_recordatorio(
        self,
        cliente_email:      str,
        nombre_cliente:     str,
        numero_presupuesto: str,
        total:              str,
        fecha_validez:      str,
        dias_pendiente:     int,
        nombre_comercial:   str = "Nuestro equipo",
    ) -> ResultadoEnvio:
        """Recordatorio de presupuesto sin respuesta."""

        variables = {
            "nombre_cliente":      nombre_cliente,
            "numero_presupuesto":  numero_presupuesto,
            "total":               total,
            "fecha_validez":       fecha_validez,
            "dias_pendiente":      str(dias_pendiente),
            "nombre_comercial":    nombre_comercial,
            "asunto":              f"Recordatorio: Presupuesto {numero_presupuesto} pendiente de respuesta",
        }

        html, texto = self.plantillas.renderizar(
            "presupuesto_recordatorio", variables, DATOS_EMPRESA
        )

        return self.enviar(EmailMessage(
            destinatario = cliente_email,
            asunto       = variables["asunto"],
            cuerpo_html  = html,
            cuerpo_texto = texto,
        ))

    def enviar_bienvenida(
        self,
        cliente_email:    str,
        nombre_cliente:   str,
        empresa_cliente:  str = "",
        nombre_comercial: str = "Nuestro equipo",
        telefono_comercial: str = "",
    ) -> ResultadoEnvio:
        """Email de bienvenida a nuevo cliente."""

        variables = {
            "nombre_cliente":     nombre_cliente,
            "empresa_cliente":    empresa_cliente,
            "nombre_comercial":   nombre_comercial,
            "telefono_comercial": telefono_comercial or DATOS_EMPRESA["empresa_telefono"],
            "asunto":             f"Bienvenido/a a {DATOS_EMPRESA['empresa_nombre']}",
        }

        html, texto = self.plantillas.renderizar(
            "bienvenida", variables, DATOS_EMPRESA
        )

        return self.enviar(EmailMessage(
            destinatario = cliente_email,
            asunto       = variables["asunto"],
            cuerpo_html  = html,
            cuerpo_texto = texto,
        ))

    def enviar_personalizado(
        self,
        destinatario:   str,
        asunto:         str,
        tipo_plantilla: str,
        variables:      dict,
        adjuntos:       list[str] = None,
    ) -> ResultadoEnvio:
        """
        Envío genérico con cualquier plantilla disponible.
        Útil para extender el sistema con nuevos tipos de email.
        """
        variables["asunto"] = asunto
        html, texto = self.plantillas.renderizar(tipo_plantilla, variables, DATOS_EMPRESA)

        adjuntos_obj = [Adjunto(ruta=r) for r in (adjuntos or [])]

        return self.enviar(EmailMessage(
            destinatario = destinatario,
            asunto       = asunto,
            cuerpo_html  = html,
            cuerpo_texto = texto,
            adjuntos     = adjuntos_obj,
        ))
