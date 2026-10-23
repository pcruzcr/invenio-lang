"""Núcleo puro y hexagonal del compilador: contrato versionado + pipeline.

CompileRequest/CompileResult son el contrato estable (cambiarlos exige bump
minor, CONTRIBUTING §1). ``compile_pure`` y ``analizar_fuente`` (en
``core/compiler.py``) son la fachada única del pipeline.
"""

from dataclasses import dataclass

from .. import _version
from ..config import Config

COMPILER_VERSION = _version.__version__

MODOS_VALIDOS = frozenset({"run", "check", "tokens", "ast"})


@dataclass(frozen=True)
class CompileRequest:
    """Contrato de entrada puro y versionable."""

    ruta: str
    codigo: str
    version: str = COMPILER_VERSION
    modo: str = "run"  # run|check|tokens|ast
    entrada: tuple[str, ...] = ()
    # INV-5010: límites de ejecución de esta petición (iteraciones, segundos,
    # recursión). None = los globales del proceso (variables INVE_MAX_*).
    # Campo opcional al final: compatible con quien construye la petición
    # por posición.
    config: Config | None = None

    def __post_init__(self):
        """Rechaza modos desconocidos en vez de ejecutar el programa por defecto."""
        if self.modo not in MODOS_VALIDOS:
            raise ValueError(f"modo inválido {self.modo!r}; válidos: {sorted(MODOS_VALIDOS)}")


@dataclass(frozen=True)
class CompileResult:
    """Contrato de salida determinista."""

    ok: bool
    salida: tuple[str, ...] = ()
    errores: tuple[str, ...] = ()
    version: str = COMPILER_VERSION


# Contrato estable: cambio en CompileRequest requiere bump minor version.
from .compiler import FASES, Analisis, analizar_fuente, compile_pure  # noqa: E402

__all__ = [
    "FASES",
    "Analisis",
    "CompileRequest",
    "CompileResult",
    "analizar_fuente",
    "compile_pure",
]
