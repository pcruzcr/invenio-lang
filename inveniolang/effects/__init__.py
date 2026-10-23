"""Sistema de efectos: qué subrutinas son puras y cuáles tocan el mundo exterior.

INV-1014: la versión anterior solo miraba un nodo ``FunctionCall`` aislado,
no veía ``imprimir``/``leer`` (que son SENTENCIAS, no llamadas), no seguía
las llamadas entre subrutinas y su ``is_pure(FunctionCall("int_a_float"))``
se probaba con ``or True``. Ahora el análisis es del programa completo:

* Efectos directos de cada subrutina: ``salida`` (imprimir), ``entrada``
  (leer), ``aleatorio`` (azar), ``archivo`` (builtins de archivo),
  ``estado_global`` (asigna una variable global) y ``modifica_parametro``
  (escribe en un arreglo/matriz recibido por referencia).
* Propagación por el grafo de llamadas hasta punto fijo: si ``f`` llama a
  ``g`` y ``g`` imprime, ``f`` también tiene efecto ``salida``.

Una subrutina sin efectos es *pura*: con los mismos argumentos devuelve
siempre lo mismo y se puede probar, memoizar o reordenar sin riesgo.
"""

from __future__ import annotations

from typing import Any

from ..ast_nodes import (
    ArrayDecl,
    ArrayLValue,
    AssignStmt,
    CallStmt,
    ConstDecl,
    ForEachStmt,
    ForInitVar,
    FunctionCall,
    IncDecStmt,
    MatrixDecl,
    MatrixLValue,
    PrintStmt,
    ReadStmt,
    VarDecl,
)
from ..complexity import recorrer
from ..i18n import t

__all__ = ["EFECTOS_BUILTIN", "analizar_efectos", "describir_efectos", "es_pura"]

EFECTOS_BUILTIN: dict[str, frozenset[str]] = {
    **dict.fromkeys(("azar", "random"), frozenset({"aleatorio"})),
    **dict.fromkeys(
        (
            "existe_archivo",
            "file_exists",
            "leer_archivo",
            "read_file",
            "escribir_archivo",
            "write_file",
            "agregar_archivo",
            "append_file",
        ),
        frozenset({"archivo"}),
    ),
}


def _locales(sub: Any) -> set[str]:
    nombres = {p.nombre for p in sub.parametros}
    for n in recorrer(sub.bloque):
        if isinstance(n, (VarDecl, ConstDecl, ArrayDecl, MatrixDecl, ForInitVar, ForEachStmt)):
            nombres.add(n.nombre)
    return nombres


def _efectos_directos(sub: Any, globales: set[str]) -> set[str]:
    efectos: set[str] = set()
    locales = _locales(sub)
    params_ref = {p.nombre for p in sub.parametros if p.es_arreglo or p.es_matriz}
    visibles_globales = globales - locales
    for n in recorrer(sub.bloque):
        if isinstance(n, PrintStmt):
            efectos.add("salida")
        elif isinstance(n, ReadStmt):
            efectos.add("entrada")
            if n.nombre in visibles_globales:
                efectos.add("estado_global")
        elif isinstance(n, (FunctionCall, CallStmt)):
            efectos |= EFECTOS_BUILTIN.get(n.nombre, frozenset())
        elif isinstance(n, (AssignStmt, IncDecStmt)):
            nombre = n.nombre if isinstance(n, IncDecStmt) else getattr(n.lvalue, "nombre", None)
            if nombre in visibles_globales:
                efectos.add("estado_global")
            elif isinstance(n, AssignStmt) and isinstance(n.lvalue, (ArrayLValue, MatrixLValue)):
                if nombre in params_ref:
                    efectos.add("modifica_parametro")
    return efectos


def analizar_efectos(ast: Any) -> dict[str, frozenset[str]]:
    """Efectos (transitivos) de cada subrutina y de ``main``."""
    subs: dict[str, Any] = {s.nombre: s for s in ast.subrutinas}
    if ast.main is not None:
        subs["main"] = ast.main
    globales = {
        d.nombre
        for d in list(ast.declaraciones_globales) + list(ast.declaraciones_posteriores)
        if hasattr(d, "nombre")
    }
    efectos = {nombre: _efectos_directos(s, globales) for nombre, s in subs.items()}
    # (llamado, pasa uno de mis arreglos/matrices por referencia)
    llamadas: dict[str, set[tuple[str, bool]]] = {}
    for nombre, s in subs.items():
        refs = {p.nombre for p in s.parametros if p.es_arreglo or p.es_matriz}
        llamadas[nombre] = {
            (n.nombre, any(getattr(a, "nombre", None) in refs for a in n.argumentos))
            for n in recorrer(s.bloque)
            if isinstance(n, (FunctionCall, CallStmt)) and n.nombre in subs
        }
    cambio = True
    while cambio:
        cambio = False
        for nombre, llamados in llamadas.items():
            heredados: set[str] = set()
            for llamado, pasa_ref in llamados:
                propios = set(efectos[llamado])
                # Que el llamado modifique SU parámetro solo afecta al llamador
                # si le pasó uno de los arreglos que a su vez recibió.
                if not pasa_ref:
                    propios.discard("modifica_parametro")
                heredados |= propios
            if not heredados <= efectos[nombre]:
                efectos[nombre] |= heredados
                cambio = True
    return {nombre: frozenset(e) for nombre, e in efectos.items()}


def es_pura(efectos: dict[str, frozenset[str]], subrutina: str) -> bool:
    """True si ``subrutina`` no tiene efectos (ni propios ni heredados)."""
    return not efectos[subrutina]


def describir_efectos(efectos: dict[str, frozenset[str]], idioma: str | None = None) -> list[str]:
    """Informe legible de la pureza de cada subrutina (catálogo i18n ``EFE.*``)."""
    return [
        f"{nombre}: "
        + (", ".join(t(f"EFE.{e}", idioma) for e in sorted(ef)) if ef else t("EFE.pura", idioma))
        for nombre, ef in efectos.items()
    ]
