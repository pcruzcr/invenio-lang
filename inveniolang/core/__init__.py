# core puro — sin IO, hexagonal
from dataclasses import dataclass

COMPILER_VERSION = "10.0.0"


@dataclass(frozen=True)
class CompileRequest:
    """Contrato de entrada puro y versionable."""

    ruta: str
    codigo: str
    version: str = COMPILER_VERSION
    modo: str = "run"  # run|check|tokens|ast
    entrada: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompileResult:
    """Contrato de salida determinista."""

    ok: bool
    salida: tuple[str, ...] = ()
    errores: tuple[str, ...] = ()
    version: str = COMPILER_VERSION


# Contrato estable: cambio en CompileRequest requiere bump minor version.
from .compiler import compile_pure  # noqa: E402

__all__ = ["CompileRequest", "CompileResult", "compile_pure"]
