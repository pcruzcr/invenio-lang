# config.py — Configuración centralizada, trazable y gobernable
#
# Resuelve dispersión de límites entre cli.py, security.py e interpreter.py.
# Fuente única de verdad para: seguridad, recursos, determinismo y portabilidad.
# Sobreescribible por variables de entorno INVE_* para orquestación/CI.
from __future__ import annotations

import os
from dataclasses import dataclass, replace

from ._version import __version__


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Límites y versión gobernables del compilador."""

    max_fuente_bytes: int = 1 * 1024 * 1024
    max_archivo_builtin: int = 2 * 1024 * 1024
    max_array_elements: int = 100_000
    max_matrix_cells: int = 200_000
    max_matrix_dim: int = 10_000
    max_recursion: int = 500
    max_iteraciones: int = 1_000_000
    max_segundos: float = 5.0
    max_string_len: int = 100_000
    max_errores: int = 50
    ruta_max_len: int = 512
    compiler_version: str = __version__

    @classmethod
    def desde_entorno(cls) -> Config:
        """Construye config con overrides INVE_*."""
        base = cls()
        return replace(
            base,
            max_fuente_bytes=_env_int("INVE_MAX_FUENTE", base.max_fuente_bytes),
            max_archivo_builtin=_env_int("INVE_MAX_ARCHIVO", base.max_archivo_builtin),
            max_recursion=_env_int("INVE_MAX_RECURSION", base.max_recursion),
            max_iteraciones=_env_int("INVE_MAX_ITERS", base.max_iteraciones),
            max_segundos=_env_float("INVE_MAX_SEGS", base.max_segundos),
            max_errores=_env_int("INVE_MAX_ERRORES", base.max_errores),
        )

    def como_dict(self) -> dict:
        """Serializa config para observabilidad."""
        return {
            "max_fuente_bytes": self.max_fuente_bytes,
            "max_archivo_builtin": self.max_archivo_builtin,
            "max_array_elements": self.max_array_elements,
            "max_matrix_cells": self.max_matrix_cells,
            "max_matrix_dim": self.max_matrix_dim,
            "max_recursion": self.max_recursion,
            "max_iteraciones": self.max_iteraciones,
            "max_segundos": self.max_segundos,
            "max_string_len": self.max_string_len,
            "max_errores": self.max_errores,
            "ruta_max_len": self.ruta_max_len,
            "compiler_version": self.compiler_version,
        }


# La documentación de este módulo promete overrides por INVE_*, pero antes
# DEFAULT_CONFIG era `Config()` y `desde_entorno()` no se llamaba nunca.
DEFAULT_CONFIG = Config.desde_entorno()
