# transpiler — v10 Rosetta viewer (compat): solo InvenioLang se compila/ejecuta
# Para aprender C/Python/Java/C#/Pascal/.NET, usa viewer/rosetta.py (read-only)
# Este módulo se mantiene por compatibilidad y re-exporta viewer
from __future__ import annotations

from typing import Any

from ..patterns import RegistryFactory, Strategy

__all__ = [
    "CTranspiler",
    "CSharpTranspiler",
    "JavaTranspiler",
    "PascalTranspiler",
    "PythonTranspiler",
    "TranspileStrategy",
    "TranspilerFactory",
    "transpile",
]

# Re-export canonical viewer
try:
    from ..viewer.rosetta import transpile as _viewer_transpile
except Exception:  # noqa: BLE001 - viewer opcional en empaquetados mínimos
    _viewer_transpile = None


class TranspileStrategy(Strategy):
    """Estrategia transpile."""

    def execute(self, ast: Any, *a, **kw) -> str:
        """Ejecuta la operación."""
        raise NotImplementedError


class PythonTranspiler(TranspileStrategy):
    """Emisor Python (vista)."""

    def execute(self, ast, *a, **kw) -> str:
        """Ejecuta la operación."""
        out = ["# Transpilado desde InvenioLang 10.0 -> Python"]
        for sub in ast.subrutinas:
            args = ", ".join(p.nombre for p in sub.parametros)
            out.append(f"def {sub.nombre}({args}):")
            for e in sub.bloque.elementos:
                out.append(f"    pass  # {type(e).__name__}")
        out.append("def main():\n    pass\nif __name__=='__main__': main()")
        return "\n".join(out)


class CTranspiler(TranspileStrategy):
    """Emisor C (vista)."""

    def execute(self, ast, *a, **kw) -> str:
        """Ejecuta la operación."""
        out = ["// InvenioLang -> C (v10)", "#include <stdio.h>"]
        for sub in ast.subrutinas:
            if sub.tipo_retorno == "int":
                ret = "int"
            elif sub.tipo_retorno == "void":
                ret = "void"
            else:
                ret = sub.tipo_retorno
            args = ", ".join(f"{p.tipo} {p.nombre}" for p in sub.parametros)
            out.append(f"{ret} {sub.nombre}({args}) {{ return 0; }}")
        out.append("int main(){ return 0; }")
        return "\n".join(out)


class JavaTranspiler(TranspileStrategy):
    """Emisor Java (vista)."""

    def execute(self, ast, *a, **kw) -> str:
        """Ejecuta la operación."""
        out = ["// InvenioLang -> Java", "public class Main {"]
        for sub in ast.subrutinas:
            ret = sub.tipo_retorno if sub.tipo_retorno != "string" else "String"
            args = ", ".join(f"{p.tipo} {p.nombre}" for p in sub.parametros)
            out.append(f"  static {ret} {sub.nombre}({args}) {{ return 0; }}")
        out.append("  public static void main(String[] args) {}")
        out.append("}")
        return "\n".join(out)


class CSharpTranspiler(TranspileStrategy):
    """Emisor C# (vista)."""

    def execute(self, ast, *a, **kw) -> str:
        """Ejecuta la operación."""
        out = ["// InvenioLang -> C# (.NET)", "using System; class Program {"]
        for sub in ast.subrutinas:
            ret = sub.tipo_retorno
            args = ", ".join(f"{p.tipo} {p.nombre}" for p in sub.parametros)
            out.append(f"  static {ret} {sub.nombre}({args}) {{ return 0; }}")
        out.append("  static void Main(){ } }")
        return "\n".join(out)


class PascalTranspiler(TranspileStrategy):
    """Emisor Pascal (vista)."""

    def execute(self, ast, *a, **kw) -> str:
        """Ejecuta la operación."""
        out = ["{ InvenioLang -> Pascal }", "program Main;"]
        for sub in ast.subrutinas:
            out.append(f"function {sub.nombre}: integer; begin end;")
        out.append("begin end.")
        return "\n".join(out)


class TranspilerFactory(RegistryFactory):
    """Factoría transpiler."""

    _inst = None

    @classmethod
    def get(cls):
        """Retorna la instancia compartida."""
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
        """Traduce a otro lenguaje (vista)."""
        return self.create(target).execute(ast)


def transpile(target: str, codigo: str) -> str:
    """Traduce a otro lenguaje (vista)."""
    from ..errors import ErrorManager
    from ..lexer import Lexer
    from ..parser import Parser

    em = ErrorManager()
    lx = Lexer(em)
    lx.tokenizar(codigo, "<transpile>")
    p = Parser(lx, em)
    ast, _ = p.analizar(codigo, "<transpile>")
    if em.hay_errores() or ast is None:
        return "\n".join(em.obtener_reportes())
    return TranspilerFactory.get().transpile(target.lower(), ast)
