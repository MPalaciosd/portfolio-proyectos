"""
Excepciones personalizadas del dominio.
Permiten distinguir errores de negocio de errores técnicos.
"""

class CRMException(Exception):
    """Base de todas las excepciones del sistema."""
    pass

class ClienteNoEncontrado(CRMException):
    def __init__(self, identificador):
        super().__init__(f"Cliente no encontrado: {identificador}")

class ClienteDuplicado(CRMException):
    def __init__(self, email: str):
        super().__init__(f"Ya existe un cliente con el email: {email}")

class ValidacionError(CRMException):
    def __init__(self, campo: str, mensaje: str):
        super().__init__(f"Error en '{campo}': {mensaje}")
        self.campo = campo
