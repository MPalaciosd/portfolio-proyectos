"""
Motor de plantillas de email.
Carga archivos HTML, sustituye variables y genera el HTML final
incrustándolo en la plantilla base.

Sintaxis de variables en las plantillas:
  {{variable}}              → Sustitución simple
  {{#variable}}...{{/variable}} → Bloque condicional (se muestra si variable tiene valor)
"""
import os
import re
from backend.core.logger import get_logger

logger = get_logger(__name__)

TEMPLATES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "storage", "templates_email"
)

# Color de banda superior según tipo de email
COLORES_TIPO = {
    "presupuesto_nuevo":        "#2c5282",   # Azul
    "presupuesto_recordatorio": "#c05621",   # Naranja
    "bienvenida":               "#276749",   # Verde
    "default":                  "#1a2e4a",   # Azul oscuro
}


class TemplateService:

    def _cargar_archivo(self, nombre: str) -> str:
        """Lee un archivo HTML de la carpeta de plantillas."""
        ruta = os.path.normpath(os.path.join(TEMPLATES_DIR, nombre))
        if not ruta.startswith(os.path.normpath(TEMPLATES_DIR)):
            raise ValueError(f"Ruta de plantilla fuera del directorio permitido: {nombre}")
        if not os.path.exists(ruta):
            raise FileNotFoundError(f"Plantilla no encontrada: {ruta}")
        with open(ruta, encoding="utf-8") as f:
            return f.read()

    def _sustituir_variables(self, html: str, variables: dict) -> str:
        """
        1. Bloques condicionales: {{#clave}}contenido{{/clave}}
           → Se muestran si la variable existe y no está vacía.
           → Se eliminan (junto con su contenido) si la variable está vacía/ausente.
        2. Variables simples: {{clave}} → valor
        3. Variables sin definir → string vacío (nunca rompe el render)
        """
        # Paso 1: bloques condicionales
        def resolver_bloque(m):
            clave     = m.group(1)
            contenido = m.group(2)
            valor     = variables.get(clave, "")
            if valor:
                # Sustituir la variable dentro del bloque
                return contenido.replace(f"{{{{{clave}}}}}", str(valor))
            return ""

        html = re.sub(
            r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}",
            resolver_bloque,
            html,
            flags=re.DOTALL,
        )

        # Paso 2: variables simples
        for clave, valor in variables.items():
            html = html.replace(f"{{{{{clave}}}}}", str(valor) if valor else "")

        # Paso 3: limpiar variables no definidas
        html = re.sub(r"\{\{\w+\}\}", "", html)
        return html

    def renderizar(
        self,
        tipo: str,
        variables: dict,
        datos_empresa: dict,
    ) -> tuple[str, str]:
        """
        Carga la plantilla del tipo indicado, sustituye variables y
        la incrusta en la plantilla base.

        Returns:
            (html_final, texto_plano)
        """
        # Cargar plantillas
        base     = self._cargar_archivo("base.html")
        contenido = self._cargar_archivo(f"{tipo}.html")

        # Variables globales de empresa + color de banda
        vars_completas = {
            "color_banda":      COLORES_TIPO.get(tipo, COLORES_TIPO["default"]),
            **datos_empresa,
            **variables,
        }

        # Renderizar contenido interno
        contenido_render = self._sustituir_variables(contenido, vars_completas)

        # Incrustar en la base
        vars_completas["contenido"] = contenido_render
        html_final = self._sustituir_variables(base, vars_completas)

        # Generar texto plano como fallback
        texto_plano = re.sub(r"<[^>]+>", "", contenido_render)
        texto_plano = re.sub(r"\n{3,}", "\n\n", texto_plano).strip()

        logger.debug("Plantilla renderizada: tipo=%s destinatario=%s",
                     tipo, variables.get("nombre_cliente", "?"))
        return html_final, texto_plano
