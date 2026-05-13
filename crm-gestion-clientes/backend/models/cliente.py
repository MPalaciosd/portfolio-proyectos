"""
Modelo de datos Cliente.
Representa una fila de la tabla 'clientes' como objeto Python.
No contiene lógica de negocio ni acceso a DB.
"""
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Cliente:
    nombre:             str
    apellidos:          str
    email:              str
    id:                 Optional[int]  = None
    empresa:            Optional[str]  = None
    telefono:           Optional[str]  = None
    direccion:          Optional[str]  = None
    ciudad:             Optional[str]  = None
    codigo_postal:      Optional[str]  = None
    pais:               str            = "España"
    nif:                Optional[str]  = None
    tipo_cliente:       str            = "particular"
    activo:             bool           = True
    notas:              Optional[str]  = None
    fecha_alta:         Optional[str]  = None
    fecha_modificacion: Optional[str]  = None

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellidos}"

    @property
    def display_name(self) -> str:
        """Nombre para mostrar: empresa si existe, si no nombre completo."""
        return self.empresa if self.empresa else self.nombre_completo

    def to_dict(self) -> dict:
        return {
            "id":                 self.id,
            "nombre":             self.nombre,
            "apellidos":          self.apellidos,
            "empresa":            self.empresa,
            "email":              self.email,
            "telefono":           self.telefono,
            "direccion":          self.direccion,
            "ciudad":             self.ciudad,
            "codigo_postal":      self.codigo_postal,
            "pais":               self.pais,
            "nif":                self.nif,
            "tipo_cliente":       self.tipo_cliente,
            "activo":             self.activo,
            "notas":              self.notas,
            "fecha_alta":         self.fecha_alta,
            "fecha_modificacion": self.fecha_modificacion,
        }

    @classmethod
    def from_row(cls, row) -> "Cliente":
        """Construye un Cliente desde una fila sqlite3.Row."""
        return cls(
            id=                 row["id"],
            nombre=             row["nombre"],
            apellidos=          row["apellidos"],
            empresa=            row["empresa"],
            email=              row["email"],
            telefono=           row["telefono"],
            direccion=          row["direccion"],
            ciudad=             row["ciudad"],
            codigo_postal=      row["codigo_postal"],
            pais=               row["pais"],
            nif=                row["nif"],
            tipo_cliente=       row["tipo_cliente"],
            activo=             bool(row["activo"]),
            notas=              row["notas"],
            fecha_alta=         row["fecha_alta"],
            fecha_modificacion= row["fecha_modificacion"],
        )
