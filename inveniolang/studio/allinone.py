# studio/allinone.py — v10 IDE all-in-one fachada (viewer-only)
# Integra: algoritmos, estructuras, viewer/rosetta (solo vista), UML, flowchart, LSP, visual
# Solo InvenioLang se compila/ejecuta; el resto es Rosetta viewer para aprender (no compila)
from __future__ import annotations
from typing import Dict, Any
from ..patterns import Facade
from ..core import CompileRequest, compile_pure
from ..viewer.rosetta import transpile as ver_como
from ..visual.uml import to_plantuml
from ..complexity import analyze


class StudioFacade(Facade):
    """All-in-one: un punto para aprender todo (InvenioLang ejecutable + Rosetta viewer)."""

    def execute(self, codigo: str, target: str = "python", *a, **kw) -> Dict[str, Any]:
        # 1. Compila solo InvenioLang (único ejecutable)
        req = CompileRequest(ruta="<studio>", codigo=codigo, modo="run")
        res = compile_pure(req)
        # 2. Ver como (Rosetta viewer, no compilación) — para aprender C/Python/Java/C#/Pascal/.NET
        trans = ver_como(target, codigo) if res.ok else ""
        # 3. UML si hay clases
        uml = ""
        try:
            from ..lexer import Lexer
            from ..parser import Parser
            from ..errors import ErrorManager

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


def demo_allinone() -> Dict[str, Any]:
    code = "clase Nodo { publico int valor; publico Nodo siguiente; } void main(){ imprimir(1); }"
    return StudioFacade().execute(code, target="java")
