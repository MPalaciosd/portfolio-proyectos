"""
Validación de datos de entrada para Cliente.
Se ejecuta ANTES de llegar a la base de datos.
Lanza ValidacionError con el campo y motivo específico.
"""
import re
from backend.core.exceptions import ValidacionError

TIPOS_VALIDOS   = {"particular", "empresa", "autonomo"}
EMAIL_REGEX     = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
TELEFONO_REGEX  = re.compile(r"^[+]?[\d\s\-().]{7,20}$")
CP_REGEX        = re.compile(r"^\d{4,10}$")
NIF_REGEX       = re.compile(r"^[0-9XYZ]\d{7}[A-Z]$|^[A-Z]\d{7}[0-9A-J]$")  # DNI/NIE/CIF


def validar_cliente(datos: dict, es_actualizacion: bool = False) -> None:
    """
    Valida un diccionario de datos de cliente.
    es_actualizacion=True relaja campos obligatorios (solo valida los presentes).
    """
    # ── Campos obligatorios (solo en creación) ──────────────────────────────
    if not es_actualizacion:
        for campo in ("nombre", "apellidos", "email"):
            if not datos.get(campo, "").strip():
                raise ValidacionError(campo, "Campo obligatorio")

    # ── Nombre / Apellidos ──────────────────────────────────────────────────
    for campo in ("nombre", "apellidos"):
        valor = datos.get(campo)
        if valor is not None:
            valor = valor.strip()
            if not valor:
                raise ValidacionError(campo, "No puede estar vacío")
            if len(valor) > 100:
                raise ValidacionError(campo, "Máximo 100 caracteres")
            if re.search(r"[0-9!@#$%^&*()+=\[\]{}<>]", valor):
                raise ValidacionError(campo, "No puede contener números ni caracteres especiales")

    # ── Email ───────────────────────────────────────────────────────────────
    email = datos.get("email")
    if email is not None:
        email = email.strip().lower()
        if not EMAIL_REGEX.match(email):
            raise ValidacionError("email", f"Formato inválido: {email}")
        datos["email"] = email  # Normalizar a minúsculas

    # ── Teléfono ────────────────────────────────────────────────────────────
    telefono = datos.get("telefono")
    if telefono is not None and telefono.strip():
        if not TELEFONO_REGEX.match(telefono.strip()):
            raise ValidacionError("telefono", "Formato inválido (ej: +34 612 345 678)")

    # ── Código postal ───────────────────────────────────────────────────────
    cp = datos.get("codigo_postal")
    if cp is not None and cp.strip():
        if not CP_REGEX.match(cp.strip()):
            raise ValidacionError("codigo_postal", "Debe contener entre 4 y 10 dígitos")

    # ── NIF ─────────────────────────────────────────────────────────────────
    nif = datos.get("nif")
    if nif is not None and nif.strip():
        nif_upper = nif.strip().upper()
        if not NIF_REGEX.match(nif_upper):
            raise ValidacionError("nif", "Formato inválido (DNI, NIE o CIF)")
        datos["nif"] = nif_upper  # Normalizar a mayúsculas

    # ── Tipo de cliente ─────────────────────────────────────────────────────
    tipo = datos.get("tipo_cliente")
    if tipo is not None and tipo not in TIPOS_VALIDOS:
        raise ValidacionError(
            "tipo_cliente",
            f"Debe ser uno de: {', '.join(TIPOS_VALIDOS)}"
        )

    # ── Empresa obligatoria si tipo=empresa ─────────────────────────────────
    if datos.get("tipo_cliente") == "empresa" and not datos.get("empresa", "").strip():
        raise ValidacionError("empresa", "Obligatoria cuando tipo_cliente es 'empresa'")
