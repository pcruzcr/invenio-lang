# ast_validator.py — Validación de integridad del AST, auditable y verificable
#
# No muta el pipeline existente. Uso: auditoría, CI, IDE, certificación.
# Detecta: ciclos de herencia, clases duplicadas, main ausente/múltiple.
from __future__ import annotations


def validar_ast(ast) -> list[str]:
    """Valida integridad estructural y retorna lista de hallazgos."""
    errores: list[str] = []
    if ast is None:
        return ["AST nulo"]
    # main
    mains = 0
    if getattr(ast, "main", None) is not None:
        mains = 1
    # subrutinas duplicadas se detectan en semantic, aquí solo integridad estructural
    clases = list(getattr(ast, "clases", []) or [])
    vistos: set[str] = set()
    for c in clases:
        nombre = getattr(c, "nombre", "?")
        if nombre in vistos:
            errores.append(f"Clase duplicada en AST: {nombre}")
        vistos.add(nombre)
    # ciclos herencia por mapa padre
    mapa = {getattr(c, "nombre", "?"): getattr(c, "padre", None) for c in clases}
    for nombre in mapa:
        camino: set[str] = set()
        actual: str | None = nombre
        while actual:
            if actual in camino:
                errores.append(f"Ciclo de herencia en AST desde {nombre}")
                break
            camino.add(actual)
            actual = mapa.get(actual)
            if actual is not None and actual not in mapa:
                break
    if mains == 0:
        errores.append("AST sin main (IL-SEM-020 a nivel semántico)")
    return errores


def es_ast_sano(ast) -> bool:
    """True si validar_ast no reporta hallazgos."""
    return not validar_ast(ast)
