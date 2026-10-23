"""Fachada pública estable de InvenioLang (patrón Facade).

Es el único punto de entrada recomendado para integrar el compilador (IDE,
LMS, CI, scripts, la propia CLI). Todas las funciones delegan en el núcleo
puro (:mod:`inveniolang.core`): ninguna vuelve a cablear las fases.

Ejecución y análisis (devuelven :class:`ExecutionResult`):

* :func:`compilar` — análisis estático completo, sin ejecutar.
* :func:`ejecutar` — ejecuta con entrada simulada (determinista, sin stdin).
* :func:`tokens_de` — tokens del léxico, aunque el programa no sea válido.
* :func:`ejecutar_aislado` — ejecuta código NO confiable en un subproceso
  con límites (``sandbox.py``); úsese para entregas de estudiantes.

Herramientas didácticas (``salida`` con el texto del informe; ``idioma`` es
``"es"`` o ``"en"``):

* :func:`complejidad` — cota O(·) por subrutina y su porqué.
* :func:`efectos` — subrutinas puras y efectos (pantalla, archivos, globales).
* :func:`ssa` — CFG + forma SSA del código de tres direcciones.
* :func:`uml` — diagrama de clases: PlantUML, Mermaid, SVG, JSON o texto
  accesible (INV-3212).
* :func:`ver_como` — vista del programa en Python/C/Java/C#/Pascal (Rosetta).
* :func:`formatear` — sangría canónica sin alterar ningún token.

Visualización paso a paso (INV-2005):

* :func:`trazar` — ejecuta el programa y devuelve una
  :class:`~inveniolang.visualizacion.modelo.Traza` (contrato JSON v1: pila de
  llamadas, montículo con ids estables, accesos y estructuras por paso).
* :func:`traza_html` — reproductor HTML autónomo de una traza o de un código.
* :func:`traza_svg` — SVG accesible de un paso de una traza o de un código.

Diagramas de flujo bidireccionales (INV-3008, ``docs/diagramas_de_flujo.md``):

* :func:`diagrama_flujo` — código → diagrama (JSON v1, SVG, Mermaid o texto).
* :func:`codigo_desde_flujo` — diagrama → código en español o inglés.

Programación por bloques (INV-4009, ``docs/bloques.md``):

* :func:`bloques` — código → bloques (JSON v1 o descripción accesible).
* :func:`codigo_desde_bloques` — bloques → código en español o inglés.
* :func:`catalogo_bloques` — catálogo de tipos, paleta y colores accesibles.

Diagramas UML bidireccionales (INV-3212, ``docs/uml.md``):

* :func:`codigo_desde_uml` — esqueleto InvenioLang que compila (es/en) a
  partir de un diagrama (modelo, JSON v1 o PlantUML).
* :func:`diagrama_objetos` — diagrama de objetos (SVG o texto) de un paso de
  una traza.

Cada resultado lleva ``run_id``: el mismo id de correlación que registran los
logs de ``observability`` para esa compilación (INV-1022).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .config import DEFAULT_CONFIG, Config
from .core import CompileRequest, CompileResult, analizar_fuente, compile_pure
from .modulos import CargadorMemoria
from .observability import PipelineMetrics, new_run_id, set_current_run

if TYPE_CHECKING:
    from .visualizacion.modelo import Traza

__all__ = [
    "ExecutionResult",
    "bloques",
    "catalogo_bloques",
    "codigo_desde_bloques",
    "codigo_desde_flujo",
    "codigo_desde_uml",
    "compilar",
    "complejidad",
    "diagrama_flujo",
    "diagrama_objetos",
    "efectos",
    "ejecutar",
    "ejecutar_aislado",
    "formatear",
    "ssa",
    "tokens_de",
    "traza_html",
    "traza_svg",
    "trazar",
    "uml",
    "ver_como",
]


@dataclass(frozen=True)
class ExecutionResult:
    """Resultado de la fachada pública con trazabilidad."""

    ok: bool
    salida: tuple[str, ...]
    errores: tuple[str, ...]
    version: str
    run_id: str


def _cargador(ruta: str, modulos: Mapping[str, str] | None) -> CargadorMemoria | None:
    """Módulos en memoria para anfitriones sin disco (web, LMS).

    Las claves relativas se resuelven junto a ``ruta``, igual que ``importar``.
    """
    if modulos is None:
        return None
    base = os.path.dirname(os.path.abspath(ruta))
    return CargadorMemoria({os.path.join(base, k): v for k, v in modulos.items()})


def _compilar(
    req: CompileRequest,
    metrics: PipelineMetrics | None = None,
    idioma: str | None = None,
    modulos: Mapping[str, str] | None = None,
) -> ExecutionResult:
    run_id = new_run_id()
    res: CompileResult = compile_pure(
        req, metrics, run_id=run_id, idioma=idioma, cargador=_cargador(req.ruta, modulos)
    )
    return ExecutionResult(res.ok, res.salida, res.errores, res.version, run_id)


def compilar(
    codigo: str,
    ruta: str = "<memoria>",
    config: Config = DEFAULT_CONFIG,
    idioma: str | None = None,
    modulos: Mapping[str, str] | None = None,
) -> ExecutionResult:
    """Compila sin ejecutar (léxico, sintaxis, semántica y tipos)."""
    req = CompileRequest(ruta, codigo, config.compiler_version, modo="check")
    return _compilar(req, idioma=idioma, modulos=modulos)


def ejecutar(
    codigo: str,
    ruta: str = "<memoria>",
    entrada: tuple[str, ...] = (),
    config: Config = DEFAULT_CONFIG,
    metrics: PipelineMetrics | None = None,
    idioma: str | None = None,
    modulos: Mapping[str, str] | None = None,
) -> ExecutionResult:
    """Ejecuta un programa con entrada simulada.

    ``idioma`` elige el idioma de los diagnósticos; ``modulos`` ({ruta: texto})
    sirve los ``importar`` desde memoria, sin tocar el disco.
    """
    req = CompileRequest(ruta, codigo, config.compiler_version, modo="run", entrada=entrada)
    return _compilar(req, metrics, idioma, modulos)


def tokens_de(
    codigo: str, ruta: str = "<memoria>", config: Config = DEFAULT_CONFIG
) -> ExecutionResult:
    """Retorna los tokens como salida, sin ejecutar."""
    return _compilar(CompileRequest(ruta, codigo, config.compiler_version, modo="tokens"))


def ejecutar_aislado(
    codigo: str,
    timeout: int = 5,
    config: Config = DEFAULT_CONFIG,
    entrada: tuple[str, ...] = (),
) -> ExecutionResult:
    """Ejecuta código no confiable en un subproceso con límites de CPU/memoria.

    Primero lo compila en proceso (sin ejecutarlo) para devolver diagnósticos
    oficiales; solo si es válido lo ejecuta en el sandbox con ``entrada``.
    """
    from .sandbox import run_sandboxed

    previo = compilar(codigo, config=config)
    if not previo.ok:
        return previo
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "prog.inv"
        ruta.write_text(codigo, encoding="utf-8")
        r = run_sandboxed(str(ruta), timeout=timeout, entrada=list(entrada))
    if r.get("ok"):
        salida: tuple[str, ...] = (str(r.get("stdout", "")),)
        return ExecutionResult(True, salida, (), config.compiler_version, previo.run_id)
    error = str(r.get("stderr") or r.get("stdout") or "sandbox")
    return ExecutionResult(False, (), (error,), config.compiler_version, previo.run_id)


def _herramienta(
    codigo: str,
    ruta: str,
    hasta: str,
    generar: Callable[[Any], str],
    config: Config,
    idioma: str | None = None,
) -> ExecutionResult:
    """Analiza hasta ``hasta`` y, si no hay errores, aplica ``generar`` al AST."""
    run_id = new_run_id()
    set_current_run(run_id, ruta=ruta, modo=f"herramienta:{hasta}")
    analisis = analizar_fuente(codigo, ruta, hasta=hasta, idioma=idioma)
    if not analisis.ok:
        errores = tuple(analisis.errores.obtener_reportes())
        return ExecutionResult(False, (), errores, config.compiler_version, run_id)
    return ExecutionResult(True, (generar(analisis.ast),), (), config.compiler_version, run_id)


def complejidad(
    codigo: str, ruta: str = "<memoria>", idioma: str | None = None, config: Config = DEFAULT_CONFIG
) -> ExecutionResult:
    """Cota de complejidad temporal por subrutina con su explicación."""
    from .complexity import analizar_complejidad, describir

    return _herramienta(
        codigo,
        ruta,
        "semantico",
        lambda ast: "\n".join(describir(analizar_complejidad(ast), idioma)),
        config,
        idioma,
    )


def efectos(
    codigo: str, ruta: str = "<memoria>", idioma: str | None = None, config: Config = DEFAULT_CONFIG
) -> ExecutionResult:
    """Pureza y efectos (transitivos) de cada subrutina."""
    from .effects import analizar_efectos, describir_efectos

    return _herramienta(
        codigo,
        ruta,
        "semantico",
        lambda ast: "\n".join(describir_efectos(analizar_efectos(ast), idioma)),
        config,
        idioma,
    )


def ssa(codigo: str, ruta: str = "<memoria>", config: Config = DEFAULT_CONFIG) -> ExecutionResult:
    """CFG en bloques básicos y forma SSA (φ + renombrado) del TAC de cada subrutina."""
    from . import ir
    from .ir_ssa import a_ssa, formatear_ssa

    def generar(ast: Any) -> str:
        subrutinas, _ = ir.generar_programa(ast)
        partes = []
        for nombre, (parametros, instrucciones) in subrutinas.items():
            partes.append(f"--- {nombre}({', '.join(parametros)}) ---")
            partes.append(formatear_ssa(a_ssa(instrucciones)))
        return "\n".join(partes)

    try:
        return _herramienta(codigo, ruta, "tipos", generar, config)
    except ir.NoSoportadoIR as e:
        return ExecutionResult(False, (), (str(e),), config.compiler_version, new_run_id())


def ver_como(
    lenguaje: str, codigo: str, ruta: str = "<memoria>", config: Config = DEFAULT_CONFIG
) -> ExecutionResult:
    """Vista Rosetta del programa en python, c, cpp, java, csharp o pascal."""
    from .viewer.rosetta import TranspilerFactory

    factoria = TranspilerFactory.get()
    return _herramienta(
        codigo, ruta, "parser", lambda ast: factoria.transpile(lenguaje.lower(), ast), config
    )


def formatear(
    codigo: str, ruta: str = "<memoria>", config: Config = DEFAULT_CONFIG
) -> ExecutionResult:
    """Sangría canónica; solo formatea programas léxicamente válidos."""
    from .formatter import formatear as _formatear

    run_id = new_run_id()
    analisis = analizar_fuente(codigo, ruta, hasta="lexer")
    if not analisis.ok:
        errores = tuple(analisis.errores.obtener_reportes())
        return ExecutionResult(False, (), errores, config.compiler_version, run_id)
    return ExecutionResult(True, (_formatear(codigo),), (), config.compiler_version, run_id)


def trazar(
    codigo: str,
    ruta: str = "<memoria>",
    entrada: tuple[str, ...] = (),
    idioma: str | None = None,
    max_pasos: int = 5000,
    modulos: Mapping[str, str] | None = None,
    ruta_fuente: str | None = None,
) -> Traza:
    """Traza paso a paso para visualizar estructuras y algoritmos (INV-2005).

    ``idioma`` ``None`` lo deduce de las palabras clave del programa;
    ``max_pasos`` (1..100 000) detiene la ejecución y marca la traza como
    truncada; ``modulos`` sirve ``importar`` desde memoria y ``ruta_fuente``
    desde disco. Para JSON: ``visualizacion.modelo.a_json(traza)``.
    """
    from .visualizacion.traza import trazar as _trazar

    return _trazar(
        codigo,
        ruta,
        entrada=entrada,
        idioma=idioma,
        max_pasos=max_pasos,
        modulos=modulos,
        ruta_fuente=ruta_fuente,
    )


def _como_traza(
    fuente: str | Traza | Mapping[str, Any],
    ruta: str,
    entrada: tuple[str, ...],
    idioma: str | None,
    max_pasos: int,
    modulos: Mapping[str, str] | None,
    ruta_fuente: str | None,
) -> Any:
    """Un ``str`` es CÓDIGO fuente (se traza); una Traza o su ``dict`` se usa tal cual."""
    if isinstance(fuente, str):
        return trazar(fuente, ruta, entrada, idioma, max_pasos, modulos, ruta_fuente)
    return fuente


def traza_html(
    fuente: str | Traza | Mapping[str, Any],
    ruta: str = "<memoria>",
    entrada: tuple[str, ...] = (),
    idioma: str | None = None,
    max_pasos: int = 5000,
    modulos: Mapping[str, str] | None = None,
    ruta_fuente: str | None = None,
) -> str:
    """Reproductor HTML autónomo (sin red) de ``fuente`` (INV-2009).

    ``fuente`` es código InvenioLang (se traza con :func:`trazar` y los mismos
    parámetros) o una traza ya hecha (``Traza`` o su ``dict``).
    """
    from .visualizacion import html_traza

    traza = _como_traza(fuente, ruta, entrada, idioma, max_pasos, modulos, ruta_fuente)
    return html_traza(traza, idioma)


def traza_svg(
    fuente: str | Traza | Mapping[str, Any],
    paso: int,
    ruta: str = "<memoria>",
    entrada: tuple[str, ...] = (),
    idioma: str | None = None,
    max_pasos: int = 5000,
    modulos: Mapping[str, str] | None = None,
    ruta_fuente: str | None = None,
    tema: str = "claro",
) -> str:
    """SVG del paso en la POSICIÓN ``paso`` (0..N-1) de ``fuente`` (INV-2009).

    Misma convención que ``visualizacion.traza_svg``; ``IndexError`` si el paso
    no existe. ``fuente``: código (se traza) o una traza ya hecha.
    """
    from .visualizacion import traza_svg as _traza_svg

    traza = _como_traza(fuente, ruta, entrada, idioma, max_pasos, modulos, ruta_fuente)
    return _traza_svg(traza, paso, idioma, tema)


# ---------------------------------------------------------------------------
# Diagramas de flujo (equipo FLUJO, INV-3008)
# ---------------------------------------------------------------------------


def diagrama_flujo(
    codigo: str,
    subrutina: str | None = None,
    formato: str = "json",
    idioma: str | None = None,
    ruta: str = "<memoria>",
    tema: str = "claro",
    modulos: Mapping[str, str] | None = None,
    ruta_fuente: str | None = None,
) -> str:
    """Diagrama de flujo de un programa válido (INV-3008).

    ``formato``: ``json`` (modelo v1 del programa completo, reconvertible con
    :func:`codigo_desde_flujo`), ``svg`` (accesible; ``tema`` claro, oscuro o
    auto), ``mermaid`` (``flowchart TD``) o ``texto`` (descripción accesible).
    ``subrutina`` elige un diagrama por su clave (``main``, ``suma``,
    ``Pila.apilar``); ``None`` dibuja todos. ``idioma`` (es/en) es el de los
    textos y etiquetas; ``None`` lo deduce del programa. Lanza
    ``flujo.ErrorFlujo`` si el programa no compila (con ``.diagnosticos``) o
    la subrutina no existe, y ``ValueError`` con un formato o tema inválido.
    """
    from . import flujo

    modelo = flujo.modelo_desde_codigo(
        codigo,
        idioma,
        ruta=ruta,
        cargador=_cargador(ruta, modulos),
        ruta_fuente=ruta_fuente,
    )
    return flujo.exportar(modelo, formato, subrutina, tema=tema)


def codigo_desde_flujo(modelo: Any, idioma: str | None = None) -> str:
    """Código InvenioLang de un diagrama (``ModeloFlujo``, su ``dict`` o JSON).

    ``idioma`` es el de las palabras clave del código (``None``: el del
    modelo). Lanza ``flujo.ErrorFlujo`` si el modelo no cumple el contrato v1.
    El código se genera aunque algún texto de una caja no compile; para
    comprobarlo úsese ``flujo.validar(modelo)``.
    """
    from . import flujo

    return flujo.codigo_desde_modelo(flujo.como_modelo(modelo), idioma)


# ================================================================ Bloques (Fase 4)
# INV-4009: el editor de bloques (Qt y web) y la CLI entran por aquí. Los
# bloques son el mismo árbol que el diagrama de flujo (docs/bloques.md).

FORMATOS_BLOQUES = ("json", "texto")


def bloques(
    codigo: str,
    formato: str = "json",
    idioma: str | None = None,
    ruta: str = "<memoria>",
    modulos: Mapping[str, str] | None = None,
    ruta_fuente: str | None = None,
) -> str:
    """Programa de bloques de un código válido (INV-4009).

    ``formato``: ``json`` (contrato v1, reconvertible con
    :func:`codigo_desde_bloques`) o ``texto`` (descripción accesible
    sangrada). ``idioma`` (es/en) es el de los bloques; ``None`` lo deduce
    del programa. Lanza ``flujo.ErrorFlujo`` (con ``.diagnosticos``) si el
    programa no compila y ``ValueError`` con un formato inválido.
    """
    from . import bloques as B  # noqa: N812 - alias corto del paquete

    if formato not in FORMATOS_BLOQUES:
        raise ValueError(f"formato inválido {formato!r}; válidos: {', '.join(FORMATOS_BLOQUES)}")
    modelo = B.bloques_desde_codigo(
        codigo, idioma, ruta=ruta, cargador=_cargador(ruta, modulos), ruta_fuente=ruta_fuente
    )
    return B.a_json(modelo) if formato == "json" else B.describir(modelo, modelo.idioma)


def codigo_desde_bloques(modelo: Any, idioma: str | None = None) -> str:
    """Código InvenioLang de un programa de bloques (``ModeloBloques``, ``dict`` o JSON).

    ``idioma`` es el de las palabras clave (``None``: el del modelo). Lanza
    ``bloques.ErrorBloques`` si el JSON no cumple el contrato v1 o si al
    programa le falta algo para escribirse (hueco vacío, campo sin valor).
    Para la validación completa con el compilador: ``bloques.validar``.
    """
    from . import bloques as B  # noqa: N812 - alias corto del paquete

    return B.codigo_desde_bloques(B.como_modelo(modelo), idioma)


def catalogo_bloques(idioma: str = "es") -> dict[str, Any]:
    """Catálogo de bloques (tipos, encaje, paleta, categorías y colores) en ``idioma``."""
    from . import bloques as B  # noqa: N812 - alias corto del paquete

    return B.catalogo_dict(idioma)


# ================================================================ UML (Fase 3)
# INV-3212: el diagrama de clases sale del AST de la fase ``modulos`` (antes de
# que el semántico expanda genéricos y tipos suma), pero solo después de
# comprobar que el programa completo es válido; los mismos ``modulos`` y
# ``ruta_fuente`` que ``trazar`` resuelven los ``importar``.


def uml(
    codigo: str,
    ruta: str = "<memoria>",
    formato: str = "plantuml",
    config: Config = DEFAULT_CONFIG,
    idioma: str | None = None,
    tema: str = "claro",
    modulos: Mapping[str, str] | None = None,
    ruta_fuente: str | None = None,
) -> ExecutionResult:
    """Diagrama de clases en ``formato``: plantuml, mermaid, svg, json o texto.

    Firma compatible con la anterior (``codigo, ruta, formato, config``).
    ``idioma`` decide cómo se escriben los tipos y el texto accesible
    (``None``: el de las palabras clave del programa) y el de los
    diagnósticos; ``tema`` (``claro``/``oscuro``) solo afecta al SVG.
    ``ValueError`` si el formato no existe.
    """
    from . import i18n
    from .uml import FORMATOS, exportar, modelo_desde_ast
    from .visualizacion.traza import detectar_idioma

    if formato not in FORMATOS:
        raise ValueError(f"formato UML inválido {formato!r}; válidos: {', '.join(FORMATOS)}")
    idi = i18n.normalizar_idioma(idioma) if idioma else detectar_idioma(codigo) or "es"
    run_id = new_run_id()
    set_current_run(run_id, ruta=ruta, modo="herramienta:uml")
    cargador = _cargador(ruta, modulos)
    analisis = analizar_fuente(
        codigo, ruta, hasta="semantico", idioma=idioma, cargador=cargador, ruta_fuente=ruta_fuente
    )
    if not analisis.ok:
        errores = tuple(analisis.errores.obtener_reportes())
        return ExecutionResult(False, (), errores, config.compiler_version, run_id)
    previo = analizar_fuente(
        codigo, ruta, hasta="modulos", idioma=idioma, cargador=cargador, ruta_fuente=ruta_fuente
    )
    modelo = modelo_desde_ast(previo.ast, idi)
    texto = exportar(modelo, formato, idi, tema)
    return ExecutionResult(True, (texto,), (), config.compiler_version, run_id)


def codigo_desde_uml(
    modelo_o_plantuml: Any, idioma: str | None = None, config: Config = DEFAULT_CONFIG
) -> ExecutionResult:
    """Esqueleto InvenioLang (``salida[0]``) a partir de un diagrama de clases (INV-3212).

    Acepta un ``uml.DiagramaClases``, su ``dict``, su JSON (texto que empieza
    por ``{``) o texto PlantUML del subconjunto de ``docs/uml.md``. ``idioma``
    (``es``/``en``) es el del código y los mensajes; ``None`` usa el del
    diagrama. El código se compila antes de devolverlo: ``ok`` solo es
    verdadero si compila. Si el diagrama no se puede leer o InvenioLang no
    puede expresarlo, ``errores`` explica por qué.
    """
    from . import i18n
    from .uml import ErrorUML, ModeloNoGenerable, cargar_diagrama, generar_codigo

    run_id = new_run_id()
    version = config.compiler_version
    mensajes = i18n.normalizar_idioma(idioma) if idioma else i18n.idioma_actual()
    try:
        modelo = cargar_diagrama(modelo_o_plantuml, mensajes)
    except ErrorUML as e:
        return ExecutionResult(False, (), (e.texto(mensajes),), version, run_id)
    idi = i18n.normalizar_idioma(idioma) if idioma else modelo.idioma
    try:
        codigo = generar_codigo(modelo, idi)
    except ModeloNoGenerable as e:
        return ExecutionResult(False, (), tuple(x.texto(idi) for x in e.errores), version, run_id)
    comprobado = compilar(codigo, "esqueleto.inv", config, idioma=idi)
    return ExecutionResult(comprobado.ok, (codigo,), comprobado.errores, version, comprobado.run_id)


def diagrama_objetos(
    codigo_o_traza: str | Traza | Mapping[str, Any],
    paso: int,
    formato: str = "svg",
    ruta: str = "<memoria>",
    entrada: tuple[str, ...] = (),
    idioma: str | None = None,
    max_pasos: int = 5000,
    modulos: Mapping[str, str] | None = None,
    ruta_fuente: str | None = None,
    tema: str = "claro",
) -> str:
    """Diagrama de objetos del paso en la POSICIÓN ``paso`` (0..N-1) (INV-3212).

    ``codigo_o_traza``: código (se traza con :func:`trazar`) o una traza ya
    hecha (``Traza`` o su ``dict``). ``formato``: ``svg`` o ``texto``.
    ``IndexError`` si el paso no existe; ``ValueError`` si el formato no.
    """
    from . import i18n
    from .uml import describir_objetos, svg_objetos
    from .visualizacion import normalizar_traza

    if formato not in ("svg", "texto"):
        raise ValueError(f"formato inválido {formato!r}; válidos: svg, texto")
    traza = _como_traza(codigo_o_traza, ruta, entrada, idioma, max_pasos, modulos, ruta_fuente)
    t = normalizar_traza(traza)
    idi = i18n.normalizar_idioma(idioma) if idioma else t["idioma"]
    total = len(t["pasos"])
    if not 0 <= paso < total:
        raise IndexError(i18n.t("VIS.error.paso_fuera", idi, n=paso, total=total))
    if formato == "texto":
        return describir_objetos(t["pasos"][paso], idi)
    return svg_objetos(t["pasos"][paso], idi, tema=tema)
