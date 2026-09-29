# transpiler — v10 Rosetta viewer (compat): solo InvenioLang se compila/ejecuta
# Para aprender C/Python/Java/C#/Pascal/.NET, usa viewer/rosetta.py (read-only)
# Este módulo se mantiene por compatibilidad y re-exporta viewer
from __future__ import annotations
from typing import Dict, Any
from ..patterns import Strategy, RegistryFactory
from ..ast_nodes import *

# Re-export canonical viewer
try:
    from ..viewer.rosetta import transpile as _viewer_transpile, TranspilerFactory as _VF
except Exception:
    _viewer_transpile = None


class TranspileStrategy(Strategy):
    def execute(self, ast: Any, *a, **kw) -> str:
        raise NotImplementedError


class PythonTranspiler(TranspileStrategy):
    def execute(self, ast, *a, **kw) -> str:
        out = ["# Transpilado desde InvenioLang 10.0 -> Python"]
        for sub in ast.subrutinas:
            args = ", ".join(p.nombre for p in sub.parametros)
            out.append(f"def {sub.nombre}({args}):")
            for e in sub.bloque.elementos:
                out.append(f"    pass  # {type(e).__name__}")
        out.append("def main():\n    pass\nif __name__=='__main__': main()")
        return "\n".join(out)


class CTranspiler(TranspileStrategy):
    def execute(self, ast, *a, **kw) -> str:
        out = ["// InvenioLang -> C (v10)", "#include <stdio.h>"]
        for sub in ast.subrutinas:
            ret = "int" if sub.tipo_retorno == "int" else "void" if sub.tipo_retorno == "void" else sub.tipo_retorno
            args = ", ".join(f"{p.tipo} {p.nombre}" for p in sub.parametros)
            out.append(f"{ret} {sub.nombre}({args}) {{ return 0; }}")
        out.append("int main(){ return 0; }")
        return "\n".join(out)


class JavaTranspiler(TranspileStrategy):
    def execute(self, ast, *a, **kw) -> str:
        out = ["// InvenioLang -> Java", "public class Main {"]
        for sub in ast.subrutinas:
            ret = sub.tipo_retorno if sub.tipo_retorno != "string" else "String"
            args = ", ".join(f"{p.tipo} {p.nombre}" for p in sub.parametros)
            out.append(f"  static {ret} {sub.nombre}({args}) {{ return 0; }}")
        out.append("  public static void main(String[] args) {}")
        out.append("}")
        return "\n".join(out)


class CSharpTranspiler(TranspileStrategy):
    def execute(self, ast, *a, **kw) -> str:
        out = ["// InvenioLang -> C# (.NET)", "using System; class Program {"]
        for sub in ast.subrutinas:
            ret = sub.tipo_retorno
            args = ", ".join(f"{p.tipo} {p.nombre}" for p in sub.parametros)
            out.append(f"  static {ret} {sub.nombre}({args}) {{ return 0; }}")
        out.append("  static void Main(){ } }")
        return "\n".join(out)


class PascalTranspiler(TranspileStrategy):
    def execute(self, ast, *a, **kw) -> str:
        out = ["{ InvenioLang -> Pascal }", "program Main;"]
        for sub in ast.subrutinas:
            out.append(f"function {sub.nombre}: integer; begin end;")
        out.append("begin end.")
        return "\n".join(out)


class TranspilerFactory(RegistryFactory):
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = cls()
            cls._inst.register("python", lambda: PythonTranspiler())
            cls._inst.register("c", lambda: CTranspiler())
            cls._inst.register("cpp", lambda: CTranspiler())
            cls._inst.register("java", lambda: JavaTranspiler())
            cls._inst.register("csharp", lambda: CSharpTranspiler())
            cls._inst.register("pascal", lambda: PascalTranspiler())
        return cls._inst

    def transpile(self, target: str, ast) -> str:
        return self.create(target).execute(ast)


def transpile(target: str, codigo: str) -> str:
    from ..lexer import Lexer
    from ..parser import Parser
    from ..errors import ErrorManager

    em = ErrorManager()
    lx = Lexer(em)
    lx.tokenizar(codigo, "<transpile>")
    p = Parser(lx, em)
    ast, _ = p.analizar(codigo, "<transpile>")
    if em.hay_errores() or ast is None:
        return "\n".join(em.obtener_reportes())
    return TranspilerFactory.get().transpile(target.lower(), ast)
