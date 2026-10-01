# studio/allinone.py — v10 IDE all-in-one fachada (viewer-only)
# Integra: algoritmos, estructuras, viewer/rosetta (solo vista), UML, flowchart, LSP, visual
# Solo InvenioLang se compila/ejecuta; el resto es Rosetta viewer para aprender (no compila)
from __future__ import annotations

from typing import Any

from ..complexity import analyze
from ..core import CompileRequest, compile_pure
from ..patterns import Facade
from ..viewer.rosetta import transpile as ver_como
from ..visual.uml import to_plantuml


class StudioFacade(Facade):
    """All-in-one: un punto para aprender todo (InvenioLang ejecutable + Rosetta viewer)."""

    def execute(self, codigo: str, target: str = "python", *a, **kw) -> dict[str, Any]:
        """Ejecuta la operación."""
        # 1. Compila solo InvenioLang (único ejecutable)
        req = CompileRequest(ruta="<studio>", codigo=codigo, modo="run")
        res = compile_pure(req)
        # 2. Ver como (Rosetta viewer, no compilación) — para aprender C/Python/Java/C#/Pascal/.NET
        trans = ver_como(target, codigo) if res.ok else ""
        # 3. UML si hay clases
        uml = ""
        try:
            from ..errors import ErrorManager
            from ..lexer import Lexer
            from ..parser import Parser

            em = ErrorManager()
            lx = Lexer(em)
            lx.tokenizar(codigo, "<uml>")
            p = Parser(lx, em)
            ast, _ = p.analizar(codigo, "<uml>")
            if ast and ast.clases:
                uml = to_plantuml(ast.clases)
        except Exception:
            uml = ""
        # 4. Complejidad
        comp = analyze(codigo)
        return {
            "ok": res.ok,
            "salida": res.salida,
            "errores": res.errores,
            "ver_como": trans[:500],
            "transpilado": trans[:500],
            "uml": uml[:800],
            "complejidad": comp,
            "nota_viewer": "Solo InvenioLang se ejecuta; ver_como es vista educativa",
        }


def demo_allinone() -> dict[str, Any]:
    """Demuestra el estudio todo-en-uno."""
    code = "clase Nodo { publico int valor; publico Nodo siguiente; } void main(){ imprimir(1); }"
    return StudioFacade().execute(code, target="java")
