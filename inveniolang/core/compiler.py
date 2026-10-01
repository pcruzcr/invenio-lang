# core/compiler.py — Hexagonal pure core (Sprint 0 v3.0)
# Sin IO, sin print, sin sys — solo CompileRequest → CompileResult
# Auditoría v10.1: métricas por fase (PipelineMetrics) inyectadas opcionalmente
# — el núcleo sigue siendo puro: si metrics=None, el comportamiento es idéntico.
from __future__ import annotations

from contextlib import contextmanager

from ..errors import ErrorManager
from ..interpreter import Interpreter
from ..lexer import Lexer
from ..observability import PipelineMetrics, new_run_id, set_current_run
from ..parser import Parser
from ..semantic import SemanticAnalyzer
from ..type_checker import TypeChecker
from . import CompileRequest, CompileResult


def compile_pure(req: CompileRequest, metrics: PipelineMetrics | None = None) -> CompileResult:
    """Compila de forma pura, sin IO."""
    run_id = new_run_id()
    set_current_run(run_id, ruta=req.ruta, modo=req.modo)
    mide = metrics.mide if metrics else _mida_nula
    em = ErrorManager()
    em.set_archivo(req.ruta)
    with mide("lexer"):
        lx = Lexer(em)
        toks = lx.tokenizar(req.codigo, req.ruta)
    if em.hay_errores():
        return CompileResult(ok=False, errores=tuple(em.obtener_reportes()), version=req.version)
    with mide("parser"):
        p = Parser(lx, em)
        ast, _ = p.analizar(req.codigo, req.ruta)
    if em.hay_errores() or ast is None:
        return CompileResult(ok=False, errores=tuple(em.obtener_reportes()), version=req.version)
    with mide("semantico"):
        sem = SemanticAnalyzer(em)
        tabla = sem.analizar(ast)
    if em.hay_errores():
        return CompileResult(ok=False, errores=tuple(em.obtener_reportes()), version=req.version)
    with mide("tipos"):
        tc = TypeChecker(em, tabla)
        tc.verificar(ast)
    if em.hay_errores():
        return CompileResult(ok=False, errores=tuple(em.obtener_reportes()), version=req.version)
    if req.modo == "check":
        return CompileResult(ok=True, version=req.version)
    if req.modo == "tokens":
        return CompileResult(ok=True, salida=tuple(str(t) for t in toks), version=req.version)
    with mide("ejecucion"):
        interp = Interpreter(em, tabla)
        salida = interp.interpretar(
            ast, list(req.entrada) if req.entrada else None, usar_stdin=False
        )
    if em.hay_errores():
        return CompileResult(ok=False, errores=tuple(em.obtener_reportes()), version=req.version)
    return CompileResult(ok=True, salida=tuple(salida), version=req.version)


@contextmanager
def _mida_nula(_fase: str, **_meta):
    """No-op contextmanager: mantiene pureza cuando metrics no se inyecta."""
    yield
