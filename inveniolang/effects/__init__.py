# effects — v8 effect system 100% — para azar/leer_archivo, pureza, análisis
from __future__ import annotations
from typing import Dict, Set, List, Any

Effect = str
effects: Dict[str, Set[str]] = {
    "azar": {"io", "random"},
    "random": {"io", "random"},
    "leer_archivo": {"io", "fs"},
    "read_file": {"io", "fs"},
    "escribir_archivo": {"io", "fs"},
    "write_file": {"io", "fs"},
    "agregar_archivo": {"io", "fs"},
    "append_file": {"io", "fs"},
    "leer": {"io"},
    "read": {"io"},
    "imprimir": {"io"},
    "print": {"io"},
}

PURE_FUNCS = {"int_a_float", "float_a_int", "longitud_texto", "subcadena", "raiz_cuadrada", "elevar", "absoluto"}


def effect_of(node: Any, tabla=None) -> Set[str]:
    from ..ast_nodes import FunctionCall, MethodCallExpr, Identifier

    eff: Set[str] = set()
    if isinstance(node, FunctionCall):
        eff.update(effects.get(node.nombre, set()))
        for arg in node.argumentos:
            eff.update(effect_of(arg, tabla))
    elif hasattr(node, "nombre") and isinstance(node, Identifier):
        pass
    # Recursión genérica
    for attr in (
        "izquierda",
        "derecha",
        "operando",
        "condicion",
        "si_verdadero",
        "si_falso",
        "valor",
        "indice",
        "fila",
        "columna",
    ):
        child = getattr(node, attr, None)
        if isinstance(child, list):
            for c in child:
                eff.update(effect_of(c, tabla))
        elif (
            child is not None
            and hasattr(child, "__class__")
            and child.__class__.__name__ in ("BinaryOp", "UnaryOp", "FunctionCall", "ArrayAccess")
        ):
            eff.update(effect_of(child, tabla))
    return eff


def is_pure(node: Any) -> bool:
    return len(effect_of(node)) == 0


def requires_io(node: Any) -> bool:
    return "io" in effect_of(node)
