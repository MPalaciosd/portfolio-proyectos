"""
Modelos de datos para presupuestos.
Sin lógica de negocio ni acceso a DB.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LineaPresupuesto:
    descripcion:    str
    cantidad:       float
    precio_unitario: float
    descuento:      float = 0.0   # Porcentaje: 0.0 – 100.0
    unidad:         str   = "ud"

    @property
    def subtotal_bruto(self) -> float:
        return round(self.cantidad * self.precio_unitario, 2)

    @property
    def importe_descuento(self) -> float:
        return round(self.subtotal_bruto * self.descuento / 100, 2)

    @property
    def subtotal(self) -> float:
        return round(self.subtotal_bruto - self.importe_descuento, 2)


@dataclass
class EmpresaEmisora:
    """Datos de la empresa que emite el presupuesto."""
    nombre:         str
    nif:            str
    direccion:      str
    ciudad:         str
    codigo_postal:  str
    pais:           str   = "España"
    telefono:       str   = ""
    email:          str   = ""
    web:            str   = ""
    logo_path:      Optional[str] = None


@dataclass
class ClientePresupuesto:
    """Datos del cliente destinatario (subconjunto de Cliente)."""
    nombre:         str
    apellidos:      str
    email:          str
    empresa:        Optional[str] = None
    nif:            Optional[str] = None
    direccion:      Optional[str] = None
    ciudad:         Optional[str] = None
    codigo_postal:  Optional[str] = None
    telefono:       Optional[str] = None

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellidos}"

    @property
    def display_name(self) -> str:
        return self.empresa if self.empresa else self.nombre_completo


@dataclass
class Presupuesto:
    numero:         str                        # PRES-2024-001
    fecha_emision:  str                        # DD/MM/YYYY
    fecha_validez:  str                        # DD/MM/YYYY
    emisor:         EmpresaEmisora
    cliente:        ClientePresupuesto
    lineas:         list[LineaPresupuesto]     = field(default_factory=list)
    iva_porcentaje: float                      = 21.0
    notas:          str                        = ""
    condiciones:    str                        = "Pago a 30 días. Presupuesto válido hasta la fecha indicada."
    estado:         str                        = "PENDIENTE"   # PENDIENTE | ACEPTADO | RECHAZADO

    # ── Totales calculados ─────────────────────────────────────────────────

    @property
    def base_imponible(self) -> float:
        return round(sum(l.subtotal for l in self.lineas), 2)

    @property
    def importe_iva(self) -> float:
        return round(self.base_imponible * self.iva_porcentaje / 100, 2)

    @property
    def total(self) -> float:
        return round(self.base_imponible + self.importe_iva, 2)

    @property
    def hay_descuentos(self) -> bool:
        return any(l.descuento > 0 for l in self.lineas)
