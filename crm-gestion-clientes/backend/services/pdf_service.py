"""
Servicio de generación de PDFs de presupuesto.
Orquesta el layout visual con los datos del presupuesto.
Responsabilidades:
  - Construir el documento ReportLab
  - Generar el nombre de archivo personalizado
  - Guardar en storage/pdfs/ automáticamente
  - Devolver la ruta del archivo generado
"""
import os
import re
import unicodedata
from datetime import datetime
from functools import partial

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Spacer, HRFlowable

from backend.models.presupuesto import Presupuesto
from backend.core.config import config
from backend.core.logger import get_logger
from storage.templates_pdf.layout import (
    bloque_cabecera,
    bloque_metadatos,
    bloque_cliente,
    bloque_lineas,
    bloque_totales,
    bloque_notas_condiciones,
    pie_pagina,
    GRIS_BORDE,
)

logger   = get_logger(__name__)
PDF_DIR  = os.path.join(os.path.dirname(config.DB_PATH), "..", "..", "storage", "pdfs")


def _normalizar_nombre(texto: str) -> str:
    """
    Convierte texto arbitrario a nombre de archivo seguro.
    'González Consulting S.L.' -> 'Gonzalez_Consulting_SL'
    """
    # Quitar acentos
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    # Solo alfanumérico y espacios
    texto = re.sub(r"[^\w\s]", "", texto)
    # Espacios → guión bajo, colapsar múltiples
    texto = re.sub(r"\s+", "_", texto.strip())
    return texto[:40]  # Limitar longitud


def _generar_nombre_archivo(presupuesto: Presupuesto) -> str:
    """
    Formato: PRES-2024-001_NombreCliente_2024-11-15.pdf
    Ejemplo: PRES-2024-001_Gonzalez_Consulting_SL_2024-11-15.pdf
    """
    numero   = presupuesto.numero.replace("/", "-")
    cliente  = _normalizar_nombre(presupuesto.cliente.display_name)
    fecha    = datetime.now().strftime("%Y-%m-%d")
    return f"{numero}_{cliente}_{fecha}.pdf"


class PDFService:

    def __init__(self, directorio_salida: str = None):
        self.directorio_salida = directorio_salida or os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "storage", "pdfs")
        )
        os.makedirs(self.directorio_salida, exist_ok=True)

    def generar(self, presupuesto: Presupuesto, nombre_archivo: str = None) -> str:
        """
        Genera el PDF y lo guarda automáticamente.

        Args:
            presupuesto:    Objeto Presupuesto con todos los datos.
            nombre_archivo: Nombre personalizado. Si es None, se genera automáticamente.

        Returns:
            Ruta absoluta del PDF generado.
        """
        nombre   = nombre_archivo or _generar_nombre_archivo(presupuesto)
        ruta_pdf = os.path.join(self.directorio_salida, nombre)

        # ── Configurar documento ──────────────────────────────────────────
        margen_h = 15 * mm
        margen_v = 18 * mm

        doc = SimpleDocTemplate(
            ruta_pdf,
            pagesize=A4,
            leftMargin=margen_h,
            rightMargin=margen_h,
            topMargin=margen_v,
            bottomMargin=25 * mm,   # Espacio para el pie de página
            title=f"Presupuesto {presupuesto.numero}",
            author=presupuesto.emisor.nombre,
            subject=f"Presupuesto para {presupuesto.cliente.display_name}",
            creator="CRM-ASIR v1.0",
        )

        ancho = A4[0] - 2 * margen_h

        # ── Construir contenido ───────────────────────────────────────────
        story = []

        # 1. Cabecera: emisor + título
        story.append(bloque_cabecera(presupuesto, ancho))
        story.append(Spacer(1, 5 * mm))

        # 2. Banda de metadatos: fechas, IVA, estado
        story.append(bloque_metadatos(presupuesto, ancho))
        story.append(Spacer(1, 6 * mm))

        # 3. Datos del cliente
        story.append(bloque_cliente(presupuesto, ancho))
        story.append(Spacer(1, 6 * mm))

        # 4. Tabla de líneas
        story.append(bloque_lineas(presupuesto, ancho))
        story.append(Spacer(1, 4 * mm))

        # 5. Totales (alineado a la derecha)
        story.append(bloque_totales(presupuesto, ancho))
        story.append(Spacer(1, 8 * mm))

        # 6. Notas y condiciones
        story.extend(bloque_notas_condiciones(presupuesto, ancho))

        # ── Construir PDF ─────────────────────────────────────────────────
        pie = partial(pie_pagina, presupuesto=presupuesto)
        doc.build(story, onFirstPage=pie, onLaterPages=pie)

        logger.info(
            "PDF generado | numero=%s | cliente=%s | ruta=%s | total=%.2f€",
            presupuesto.numero,
            presupuesto.cliente.display_name,
            ruta_pdf,
            presupuesto.total,
        )
        return ruta_pdf

    def listar_pdfs(self) -> list[dict]:
        """Lista todos los PDFs generados con metadatos básicos."""
        archivos = []
        for f in sorted(os.listdir(self.directorio_salida)):
            if not f.endswith(".pdf"):
                continue
            ruta  = os.path.join(self.directorio_salida, f)
            stat  = os.stat(ruta)
            archivos.append({
                "nombre":   f,
                "ruta":     ruta,
                "tamanio":  f"{stat.st_size / 1024:.1f} KB",
                "creado":   datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M"),
            })
        return archivos
