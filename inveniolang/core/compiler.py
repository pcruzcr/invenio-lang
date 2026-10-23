"""Núcleo puro del pipeline: la fachada única (patrón Facade) del compilador.

Todo consumidor (``api.py``, CLI, LSP, analizadores didácticos, viewer Rosetta,
UML) llega al compilador por aquí, en vez de cablear por su cuenta
``Lexer → Parser → SemanticAnalyzer → TypeChecker``. Así hay UNA sola
definición del orden de fases, del corte ante el primer error de fase y de
la medición de métricas (INV-1022).

Contrato (CONTRIBUTING §1): sin IO, sin ``print``/``sys``. Las métricas por
fase (``PipelineMetrics``) se inyectan opcionalmente; si ``metrics`` es
``None`` el comportamiento es idéntico.

Dos niveles de API:

* :func:`analizar_fuente` — análisis estático hasta la fase pedida; devuelve
  los artefactos (tokens, AST, tabla de símbolos, ``ErrorManager``) para las
  herramientas que los necesitan.
* :func:`compile_pure` — ``CompileRequest → CompileResult``; contrato estable
  y determinista que además ejecuta el programa en modo ``run``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from ..errors import ErrorManager
from ..interpreter import Interpreter
from ..lexer import Lexer
from ..modulos import CargadorModulos, enlazar
from ..observability import PipelineMetrics, new_run_id, set_current_run
from ..parser import Parser
from ..semantic import SemanticAnalyzer
from ..type_checker import TypeChecker
from . import CompileRequest, CompileResult

# Fases del análisis estático, en orden. `analizar_fuente(hasta=...)` corta
# después de la fase indicada.
FASES = ("lexer", "parser", "modulos", "semantico", "tipos")


@dataclass
class Analisis:
    """Artefactos del análisis estático de un fuente.

    ``fase_fallida`` es la primera fase que registró errores (``None`` si el
    análisis llegó limpio hasta la fase pedida). ``tabla`` existe aunque el
    semántico haya fallado: herramientas como ``--tabla`` la muestran igual.
    """

    errores: ErrorManager
    tokens: list[tuple[Any, ...]] = field(default_factory=list)
    ast: Any = None
    tabla: Any = None
    fase_fallida: str | None = None

    @property
    def ok(self) -> bool:
        """True si ninguna fase ejecutada registró errores."""
        return self.fase_fallida is None


@contextmanager
def _mida_nula(_fase: str, **_meta: Any) -> Iterator[None]:
    """No-op: mantiene la pureza cuando no se inyectan métricas."""
    yield


def analizar_fuente(
    codigo: str,
    ruta: str = "<memoria>",
    *,
    hasta: str = "tipos",
    metrics: PipelineMetrics | None = None,
    idioma: str | None = None,
    cargador: CargadorModulos | None = None,
    ruta_fuente: str | None = None,
) -> Analisis:
    """Corre el análisis estático de ``codigo`` hasta la fase ``hasta``.

    Args:
        codigo: Fuente InvenioLang.
        ruta: Nombre que aparece en los diagnósticos ``[IL-XXX-NNN] ruta:l:c``.
        hasta: Última fase: ``lexer``, ``parser``, ``modulos``, ``semantico`` o ``tipos``.
        metrics: Métricas por fase opcionales (observabilidad).
        idioma: ``"es"``/``"en"`` para los diagnósticos (catálogo i18n, INV-1400);
            ``None`` usa ``INVENIO_IDIOMA`` o el español.
        cargador: Puerto ``modulos.CargadorModulos`` para los ``importar``
            (INV-1420); ``None`` usa el adaptador de disco.
        ruta_fuente: Ruta real del archivo, base para resolver ``importar``;
            por defecto ``ruta``.

    Returns:
        Un :class:`Analisis`; se detiene en la primera fase con errores.

    Raises:
        ValueError: si ``hasta`` no es una fase conocida.
    """
    if hasta not in FASES:
        raise ValueError(f"fase inválida {hasta!r}; válidas: {FASES}")
    ultima = FASES.index(hasta)
    mide = metrics.mide if metrics else _mida_nula
    em = ErrorManager(idioma=idioma)
    em.set_archivo(ruta)
    res = Analisis(errores=em)
    with mide("lexer"):
        lx = Lexer(em)
        res.tokens = lx.tokenizar(codigo, ruta)
    if em.hay_errores():
        res.fase_fallida = "lexer"
        return res
    if ultima < FASES.index("parser"):
        return res
    with mide("parser"):
        res.ast, _ = Parser(lx, em).analizar(codigo, ruta, enlazar=False)
    if em.hay_errores() or res.ast is None:
        res.fase_fallida = "parser"
        return res
    if ultima < FASES.index("modulos"):
        return res
    if res.ast.importaciones:
        with mide("modulos"):
            enlazar(res.ast, ruta_fuente or ruta, em, cargador)
        if em.hay_errores():
            res.fase_fallida = "modulos"
            return res
    if ultima < FASES.index("semantico"):
        return res
    with mide("semantico"):
        res.tabla = SemanticAnalyzer(em).analizar(res.ast)
    if em.hay_errores():
        res.fase_fallida = "semantico"
        return res
    if ultima < FASES.index("tipos"):
        return res
    with mide("tipos"):
        TypeChecker(em, res.tabla).verificar(res.ast)
    if em.hay_errores():
        res.fase_fallida = "tipos"
    return res


def compile_pure(
    req: CompileRequest,
    metrics: PipelineMetrics | None = None,
    *,
    run_id: str | None = None,
    idioma: str | None = None,
    cargador: CargadorModulos | None = None,
) -> CompileResult:
    """Compila (y en modo ``run`` ejecuta) de forma pura: ``CompileRequest → CompileResult``.

    Modos: ``tokens`` (solo léxico, aunque el programa no sea válido), ``ast``
    (``repr`` del árbol, sin ejecutar), ``check`` (análisis estático completo)
    y ``run`` (análisis + intérprete con ``req.entrada``; nunca lee stdin).

    Args:
        req: Petición inmutable y versionada.
        metrics: Métricas por fase opcionales.
        run_id: Identificador de correlación; si se omite se genera uno.
            INV-1022: ``api.py`` lo pasa para que el ``run_id`` que devuelve
            sea el mismo que registran los logs (antes había dos ids distintos).
        idioma: Idioma de los diagnósticos (INV-1400). Es un parámetro y no un
            campo de ``CompileRequest`` para no cambiar el contrato versionado.
        cargador: Puerto de lectura de módulos (INV-1420); el núcleo no abre
            archivos por sí mismo.

    Returns:
        Un ``CompileResult`` determinista con salida o diagnósticos oficiales.
    """
    set_current_run(run_id or new_run_id(), ruta=req.ruta, modo=req.modo)
    hasta = {"tokens": "lexer", "ast": "modulos"}.get(req.modo, "tipos")
    analisis = analizar_fuente(
        req.codigo, req.ruta, hasta=hasta, metrics=metrics, idioma=idioma, cargador=cargador
    )
    em = analisis.errores
    if not analisis.ok:
        return CompileResult(ok=False, errores=tuple(em.obtener_reportes()), version=req.version)
    if req.modo == "tokens":
        return CompileResult(
            ok=True, salida=tuple(str(t) for t in analisis.tokens), version=req.version
        )
    if req.modo == "ast":
        return CompileResult(ok=True, salida=(repr(analisis.ast),), version=req.version)
    if req.modo == "check":
        return CompileResult(ok=True, version=req.version)
    mide = metrics.mide if metrics else _mida_nula
    with mide("ejecucion"):
        interp = Interpreter(em, analisis.tabla)
        salida = interp.interpretar(analisis.ast, list(req.entrada) or None, usar_stdin=False)
    if em.hay_errores():
        # INV-4202: un error de ejecución ya no descarta lo que el programa
        # imprimió antes de fallar: sin esa salida parcial el estudiante no
        # sabe hasta dónde llegó (el estudio web y `--metrics` la muestran).
        return CompileResult(
            ok=False,
            salida=tuple(salida or ()),
            errores=tuple(em.obtener_reportes()),
            version=req.version,
        )
    return CompileResult(ok=True, salida=tuple(salida), version=req.version)
