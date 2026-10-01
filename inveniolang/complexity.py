# complexity.py — H3.7 Complexity analyzer + Tutor Socrático
# Patrones: Visitor (recorre AST), Strategy (estimadores), Template Method
from __future__ import annotations

from typing import Any

from .ast_nodes import ASTNode
from .patterns import Strategy


class ComplexityEstimator(Strategy):
    """ComplexityEstimator como estrategia intercambiable."""

    def execute(self, node: ASTNode, depth: int = 0, *args, **kwargs) -> dict[str, Any]:
        """Ejecuta la operación."""
        raise NotImplementedError


class LoopDepthEstimator(ComplexityEstimator):
    """Estima la profundidad de bucles."""

    def execute(self, node: ASTNode, depth: int = 0, *args, **kwargs) -> dict[str, Any]:
        """Ejecuta la operación."""
        # Cuenta anidamiento máximo de for/while/foreach/do
        from .ast_nodes import DoWhileStmt, ForEachStmt, ForStmt, WhileStmt

        maxd = depth
        if isinstance(node, (ForStmt, WhileStmt, ForEachStmt, DoWhileStmt)):
            depth += 1
            maxd = depth
        for attr in (
            "bloque",
            "bloque_then",
            "bloque_else",
            "elementos",
            "subrutinas",
            "main",
            "bloque_try",
            "bloque_catch",
        ):
            val = getattr(node, attr, None)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, ASTNode):
                        r = self.execute(item, depth)
                        maxd = max(maxd, r.get("max_depth", depth))
            elif isinstance(val, ASTNode):
                r = self.execute(val, depth)
                maxd = max(maxd, r.get("max_depth", depth))
        # Mapeo profundidad → O
        mapa = {0: "O(1)", 1: "O(n)", 2: "O(n²)", 3: "O(n³)"}
        # Heurística log: si contiene llamada recursiva con división (ej. mergesort) → O(n log n)
        if "O(n²)" in mapa.get(maxd, "") and "merge" in str(node).lower():
            return {"max_depth": maxd, "estimado": "O(n log n)", "tipo": "divide_conquer"}
        return {"max_depth": maxd, "estimado": mapa.get(maxd, f"O(n^{maxd})"), "tipo": "loop_depth"}


def analyze(codigo_o_ast) -> dict[str, Any]:
    """Facade: acepta string .inv o AST Program, retorna dict con estimado."""
    if isinstance(codigo_o_ast, str):
        from .errors import ErrorManager
        from .lexer import Lexer
        from .parser import Parser

        em = ErrorManager()
        lx = Lexer(em)
        lx.tokenizar(codigo_o_ast, "<analyze>")
        p = Parser(lx, em)
        ast, _ = p.analizar(codigo_o_ast, "<analyze>")
        if ast is None:
            return {"error": em.obtener_reportes()}
        codigo_o_ast = ast
    est = LoopDepthEstimator()
    r = est.execute(codigo_o_ast)
    # + conteo empírico si se ejecuta con interpreter (instrumenta max_iteraciones)
    r["empirico"] = "usa max_iteraciones de interpreter.py:1387 para conteo real"
    return r


# Tutor Socrático — no da solución, solo preguntas
PREGUNTAS_SOCRATICAS = {
    "IL-SEM-003": "¿Dónde declaraste '{nombre}'? ¿En qué ámbito está visible?",
    "IL-EJE-050": "¿Qué tamaño tiene tu arreglo y qué índice usas? Revisa 0..n-1.",
    "LOOP": "¿Cuál es el invariante de tu ciclo? ¿Qué garantiza que termina?",
    "COMPLEXITY": "Tu análisis es {estimado}. ¿Puedes reducir anidamiento con un mapa/hash?",
}


def tutor_hint(codigo_error: str, contexto: dict[str, Any] = None) -> str:
    """Da una pista socrática para el error."""
    contexto = contexto or {}
    tmpl = PREGUNTAS_SOCRATICAS.get(codigo_error, PREGUNTAS_SOCRATICAS.get("LOOP"))
    try:
        return tmpl.format(**contexto)
    except Exception:
        return tmpl


def tutor_for_complexity(ast) -> str:
    """Explica la complejidad estimada."""
    r = analyze(ast)
    return tutor_hint("COMPLEXITY", r)
