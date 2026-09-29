# api.py — Fachada pública estable, basada en contratos
#
# Cubre: interoperable, desacoplado, versionable, retrocompatible,
# determinista, trazable, testeable, preparado para integración/automatización.
from __future__ import annotations

from dataclasses import dataclass

from .config import DEFAULT_CONFIG, Config
from .core import CompileRequest, CompileResult, compile_pure
from .observability import PipelineMetrics, new_run_id


@dataclass(frozen=True)
class ExecutionResult:
    """Resultado de fachada pública con trazabilidad."""

    ok: bool
    salida: tuple[str, ...]
    errores: tuple[str, ...]
    version: str
    run_id: str


def _a_result(res: CompileResult, run_id: str) -> ExecutionResult:
    return ExecutionResult(
        ok=res.ok, salida=res.salida, errores=res.errores, version=res.version, run_id=run_id
    )


def compilar(
    codigo: str, ruta: str = "<memoria>", config: Config = DEFAULT_CONFIG
) -> ExecutionResult:
    """Compila sin ejecutar (modo check)."""
    req = CompileRequest(ruta=ruta, codigo=codigo, version=config.compiler_version, modo="check")
    run_id = new_run_id()
    res = compile_pure(req)
    return _a_result(res, run_id)


def ejecutar(
    codigo: str,
    ruta: str = "<memoria>",
    entrada: tuple[str, ...] = (),
    config: Config = DEFAULT_CONFIG,
    metrics: PipelineMetrics | None = None,
) -> ExecutionResult:
    """Ejecuta un programa y retorna salida determinista."""
    req = CompileRequest(
        ruta=ruta, codigo=codigo, version=config.compiler_version, modo="run", entrada=entrada
    )
    run_id = new_run_id()
    res = compile_pure(req, metrics)
    return _a_result(res, run_id)


def analizar(
    codigo: str, ruta: str = "<memoria>", config: Config = DEFAULT_CONFIG
) -> ExecutionResult:
    """Analiza sin ejecutar, alias explícito de compilar."""
    req = CompileRequest(ruta=ruta, codigo=codigo, version=config.compiler_version, modo="check")
    run_id = new_run_id()
    res = compile_pure(req)
    return _a_result(res, run_id)


def tokens_de(
    codigo: str, ruta: str = "<memoria>", config: Config = DEFAULT_CONFIG
) -> ExecutionResult:
    """Retorna tokens como salida, sin ejecutar."""
    req = CompileRequest(ruta=ruta, codigo=codigo, version=config.compiler_version, modo="tokens")
    run_id = new_run_id()
    res = compile_pure(req)
    return _a_result(res, run_id)


def ejecutar_aislado(
    codigo: str,
    timeout: int = 5,
    config: Config = DEFAULT_CONFIG,
) -> ExecutionResult:
    """Ejecuta código no confiable en subproceso con límites.

    Seguro, atómico y portable. Retrocompatible: no cambia ejecutar().
    """
    import tempfile
    from pathlib import Path

    from .sandbox import run_sandboxed

    run_id = new_run_id()
    previo = compilar(codigo, config=config)
    if not previo.ok:
        return ExecutionResult(
            ok=False,
            salida=(),
            errores=previo.errores,
            version=config.compiler_version,
            run_id=run_id,
        )
    with tempfile.TemporaryDirectory() as tmp:
        ruta = str(Path(tmp) / "prog.inv")
        Path(ruta).write_text(codigo, encoding="utf-8")
        r = run_sandboxed(ruta, strategy="resource", timeout=timeout)
    if r.get("ok"):
        return ExecutionResult(
            ok=True,
            salida=(str(r.get("stdout", "")),),
            errores=(),
            version=config.compiler_version,
            run_id=run_id,
        )
    return ExecutionResult(
        ok=False,
        salida=(),
        errores=(str(r.get("stderr", "sandbox")),),
        version=config.compiler_version,
        run_id=run_id,
    )
