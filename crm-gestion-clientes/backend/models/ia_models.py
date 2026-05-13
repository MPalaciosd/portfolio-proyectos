"""
Modelos de datos para las respuestas de IA.
Pydantic garantiza que Claude devuelva siempre la estructura esperada.
"""
from pydantic import BaseModel
from typing import Optional


class EmailGenerado(BaseModel):
    asunto:        str
    cuerpo_html:   str
    cuerpo_texto:  str
    tono:          str   # formal | amigable | urgente | reactivacion
    razonamiento:  str   # Por qué Claude eligió este enfoque


class AnalisisIA(BaseModel):
    resumen_ejecutivo:    str
    nivel_riesgo:         str        # bajo | medio | alto | critico
    probabilidad_cierre:  int        # 0-100
    factores_positivos:   list[str]
    factores_negativos:   list[str]
    estrategia_recomendada: str
    proximos_pasos:       list[str]
    tiempo_estimado_cierre: str      # "1-2 semanas", "1 mes", etc.


class DecisionIA(BaseModel):
    decision:         str            # acción concreta a tomar
    justificacion:    str
    alternativas:     list[str]      # otras opciones consideradas
    nivel_confianza:  int            # 0-100
    advertencias:     list[str]      # riesgos a tener en cuenta


class AuditoriaEmailIA(BaseModel):
    puntuacion:       int            # 0-100
    problemas:        list[str]
    mejoras:          list[str]
    version_mejorada: str
