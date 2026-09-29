# policy.py — Política de aula por defecto, basada en políticas
#
# Cubre: seguro, gobernable, cumplible, centrado en el usuario,
# preparado para auditoría/cambios regulatorios. Sin romper retrocompatibilidad:
# ejecutar() sigue en proceso para ejemplos confiables del docente;
# lo no confiable debe usar ejecutar_no_confiable().
from __future__ import annotations

from . import api
from .config import DEFAULT_CONFIG, Config

AVISO_AULA = (
    "Política de aula: use --sandbox / ejecutar_no_confiable() para entregas de estudiantes."
)


def ejecutar_no_confiable(codigo: str, timeout: int = 5, config: Config = DEFAULT_CONFIG):
    """Ejecuta código de estudiante aislado por defecto."""
    return api.ejecutar_aislado(codigo, timeout=timeout, config=config)


def limites_aula() -> dict:
    """Retorna límites vigentes para actas de examen."""
    return DEFAULT_CONFIG.como_dict()
