# viewer/rosetta.py — Rosetta viewer con fidelidad estructurada (no compiler)
# Solo InvenioLang se ejecuta; el resto es vista educativa read-only.
# Cubre subconjunto estructurado: variables, asignacion, print, if/while/for,
# funciones/procedimientos, return/break/continue, llamadas, expresiones
# (binarias, unarias, ternario, literales). POO/arreglos/IR fuera de alcance
# se degradan a comentario, nunca a crash.
from __future__ import annotations

from typing import Any

from ..patterns import RegistryFactory, Strategy


def _tipo(t: Any, mapa: dict) -> str:
    return mapa.get(str(t), str(t))


class _BaseEmitter(Strategy):
    """Emisor estructurado compartido. Cada target define tipos y print."""

    TIPOS: dict = {}
    PRINT: str = "print"
    AND: str = "&&"
    OR: str = "||"
    NOT: str = "!"
    TRUE: str = "true"
    FALSE: str = "false"

    def execute(self, ast: Any, *a, **kw) -> str:
        return self.programa(ast)

    # ---- expresiones ----
    def _str(self, v: Any) -> str:
        s = str(v).replace("\\", "\\\\").replace('"', '\\"')
        s = s.replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
        return '"' + s + '"'

    def expr(self, n: Any) -> str:
        c = type(n).__name__
        if c == "Literal":
            v = n.valor
            if n.tipo_literal == "string":
                return self._str(v)
            if n.tipo_literal == "bool":
                return self.TRUE if v else self.FALSE
            return str(v)
        if c == "Identifier":
            return str(n.nombre)
        if c == "BinaryOp":
            op = str(n.operador)
            if op == "&&":
                op = self.AND
            elif op == "||":
                op = self.OR
            return f"({self.expr(n.izquierda)} {op} {self.expr(n.derecha)})"
        if c == "UnaryOp":
            op = str(n.operador)
            if op == "!":
                op = self.NOT
            e = self.expr(n.operando)
            return f"({op}{e})" if n.es_prefijo else f"({e}{op})"
        if c == "FunctionCall":
            args = ", ".join(self.expr(x) for x in (n.argumentos or []))
            return f"{n.nombre}({args})"
        if c == "TernaryExpr":
            v = self.expr(n.condicion)
            a = self.expr(n.si_verdadero)
            b = self.expr(n.si_falso)
            return f"({v} ? {a} : {b})"
        if c == "ArrayAccess":
            return f"{n.nombre}[{self.expr(n.indice)}]"
        if c in ("MemberAccess", "MethodCallExpr", "NewExpr", "ThisExpr", "NullExpr"):
            return f"/*{c}-no-soportado*/0"
        return f"/*expr-{c}*/0"

    def lvalue(self, n: Any) -> str:
        c = type(n).__name__
        if c == "VarLValue":
            return str(n.nombre)
        if c == "ArrayLValue":
            return f"{n.nombre}[{self.expr(n.indice)}]"
        if c == "MatrixLValue":
            return f"{n.nombre}[{self.expr(n.fila)}][{self.expr(n.columna)}]"
        return "/*lvalue*/x"

    # ---- sentencias (cada target implementa bloque) ----
    def programa(self, ast: Any) -> str:  # pragma: no cover - base
        raise NotImplementedError


class PythonTranspiler(_BaseEmitter):
    TIPOS = {"int": "int", "float": "float", "string": "str", "bool": "bool", "void": "None"}

    def programa(self, ast) -> str:
        out: list[str] = ["# InvenioLang -> Python (vista)"]
        for d in list(getattr(ast, "declaraciones_globales", []) or []):
            out.append(self.decl(d, 0))
        for s in list(getattr(ast, "subrutinas", []) or []):
            out.extend(self.func(s, 0))
        if getattr(ast, "main", None) is not None:
            out.append("def main():")
            out.extend(self.bloque(ast.main.bloque, 1))
        out.append("if __name__=='__main__': main()")
        return "\n".join(x for x in out if x is not None)

    def decl(self, n, nv: int) -> str:
        c = type(n).__name__
        pad = "    " * nv
        if c in ("VarDecl", "ConstDecl"):
            v = f" = {self.expr(n.init_expr)}" if n.init_expr is not None else ""
            return f"{pad}{n.nombre}{v}  # {n.tipo}"
        return f"{pad}pass  # {c}-no-soportado"

    def func(self, s, nv: int) -> list[str]:
        pad = "    " * nv
        args = ", ".join(p.nombre for p in (s.parametros or []))
        head = f"{pad}def {s.nombre}({args}):"
        body = self.bloque(s.bloque, nv + 1) or [pad + "    pass"]
        return [head, *body]

    def bloque(self, b, nv: int) -> list[str]:
        pad = "    " * nv
        out: list[str] = []
        for e in getattr(b, "elementos", []) or []:
            out.extend(self.stmt(e, nv))
        return out or [pad + "pass"]

    def stmt(self, e, nv: int) -> list[str]:
        pad = "    " * nv
        c = type(e).__name__
        if c in ("VarDecl", "ConstDecl"):
            return [self.decl(e, nv)]
        if c == "AssignStmt":
            return [f"{pad}{self.lvalue(e.lvalue)} {e.operador} {self.expr(e.expr)}"]
        if c == "PrintStmt":
            return [f"{pad}print({self.expr(e.expr)})"]
        if c == "ReadStmt":
            return [f"{pad}{e.nombre} = input()  # leer"]
        if c == "IfStmt":
            out = [f"{pad}if {self.expr(e.condicion)}:"]
            out.extend(self.bloque(e.bloque_then, nv + 1))
            if e.bloque_else is not None:
                out.append(f"{pad}else:")
                out.extend(self.bloque(e.bloque_else, nv + 1))
            return out
        if c == "WhileStmt":
            return [f"{pad}while {self.expr(e.condicion)}:", *self.bloque(e.bloque, nv + 1)]
        if c == "ForStmt":
            pre: list[str] = []
            init = self.for_init(e.init_stmt, nv)
            if init:
                pre.extend(init)
            cond = self.expr(e.cond_expr) if e.cond_expr is not None else "True"
            out = [*pre, f"{pad}while {cond}:"]
            out.extend(self.bloque(e.bloque, nv + 1))
            act = self.for_act(e.act_stmt, nv + 1)
            out.extend(act)
            return out
        if c == "ReturnStmt":
            return [f"{pad}return" + (f" {self.expr(e.expr)}" if e.expr is not None else "")]
        if c == "BreakStmt":
            return [f"{pad}break"]
        if c == "ContinueStmt":
            return [f"{pad}continue"]
        if c == "CallStmt":
            args = ", ".join(self.expr(x) for x in (e.argumentos or []))
            return [f"{pad}{e.nombre}({args})"]
        if c == "IncDecStmt":
            op = "+= 1" if e.operador == "++" else "-= 1"
            return [f"{pad}{e.nombre} {op}"]
        if c in ("SwitchStmt", "TryStmt", "DoWhileStmt", "ForEachStmt", "MatchStmt"):
            return [f"{pad}pass  # {c}-ver-InvenioLang"]
        return [f"{pad}pass  # {c}"]

    def for_init(self, n, nv: int) -> list[str]:
        if n is None:
            return []
        pad = "    " * nv
        c = type(n).__name__
        if c == "ForInitVar":
            v = f" = {self.expr(n.init_expr)}" if n.init_expr is not None else ""
            return [f"{pad}{n.nombre}{v}"]
        if c == "ForInitAsig":
            return [f"{pad}{self.lvalue(n.lvalue)} {n.operador} {self.expr(n.expr)}"]
        if c == "ForInitIncDec":
            op = "+= 1" if n.operador == "++" else "-= 1"
            return [f"{pad}{n.nombre} {op}"]
        return []

    def for_act(self, n, nv: int) -> list[str]:
        return self.for_init(n, nv)


class _CBraceEmitter(_BaseEmitter):
    TIPOS = {"int": "int", "float": "double", "string": "String", "bool": "boolean", "void": "void"}
    PRINT = "print"
    CABECERA: list[str] = []
    MAIN_HEAD: str = ""
    MAIN_TAIL: str = ""
    CLASE_ENV: list[str] = []

    def programa(self, ast) -> str:
        out: list[str] = list(self.CABECERA)
        for d in list(getattr(ast, "declaraciones_globales", []) or []):
            out.append(self.decl(d, 0))
        for s in list(getattr(ast, "subrutinas", []) or []):
            out.extend(self.func(s, 0))
        if getattr(ast, "main", None) is not None:
            out.append(self.MAIN_HEAD)
            out.extend(self.bloque(ast.main.bloque, 1))
            out.append(self.MAIN_TAIL)
        out.extend(self.CLASE_ENV)
        return "\n".join(x for x in out if x is not None)

    def decl(self, n, nv: int) -> str:
        pad = "    " * nv
        c = type(n).__name__
        if c in ("VarDecl", "ConstDecl"):
            t = _tipo(n.tipo, self.TIPOS)
            v = f" = {self.expr(n.init_expr)}" if n.init_expr is not None else ""
            const = "const " if c == "ConstDecl" else ""
            return f"{pad}{const}{t} {n.nombre}{v};"
        return f"{pad}// {c} no soportado en vista"

    def func(self, s, nv: int) -> list[str]:
        pad = "    " * nv
        ret = _tipo(getattr(s, "tipo_retorno", "void"), self.TIPOS)
        args = ", ".join(f"{_tipo(p.tipo, self.TIPOS)} {p.nombre}" for p in (s.parametros or []))
        head = f"{pad}static {ret} {s.nombre}({args}) {{"
        return [head, *self.bloque(s.bloque, nv + 1), f"{pad}}}"]

    def bloque(self, b, nv: int) -> list[str]:
        out: list[str] = []
        for e in getattr(b, "elementos", []) or []:
            out.extend(self.stmt(e, nv))
        return out

    def stmt(self, e, nv: int) -> list[str]:
        pad = "    " * nv
        c = type(e).__name__
        if c in ("VarDecl", "ConstDecl"):
            return [self.decl(e, nv)]
        if c == "AssignStmt":
            return [f"{pad}{self.lvalue(e.lvalue)} {e.operador} {self.expr(e.expr)};"]
        if c == "PrintStmt":
            return [f"{pad}{self.print_call(e.expr)};"]
        if c == "ReadStmt":
            return [f"{pad}// leer {e.nombre}"]
        if c == "IfStmt":
            out = [f"{pad}if ({self.expr(e.condicion)}) {{"]
            out.extend(self.bloque(e.bloque_then, nv + 1))
            out.append(f"{pad}}}")
            if e.bloque_else is not None:
                out.append(f"{pad}else {{")
                out.extend(self.bloque(e.bloque_else, nv + 1))
                out.append(f"{pad}}}")
            return out
        if c == "WhileStmt":
            return [
                f"{pad}while ({self.expr(e.condicion)}) {{",
                *self.bloque(e.bloque, nv + 1),
                f"{pad}}}",
            ]
        if c == "ForStmt":
            ini = self.for_cabecera(e.init_stmt)
            cond = self.expr(e.cond_expr) if e.cond_expr is not None else "true"
            act = self.for_cabecera(e.act_stmt)
            return [
                f"{pad}for ({ini}; {cond}; {act}) {{",
                *self.bloque(e.bloque, nv + 1),
                f"{pad}}}",
            ]
        if c == "ReturnStmt":
            return [f"{pad}return" + (f" {self.expr(e.expr)};" if e.expr is not None else ";")]
        if c == "BreakStmt":
            return [f"{pad}break;"]
        if c == "ContinueStmt":
            return [f"{pad}continue;"]
        if c == "CallStmt":
            args = ", ".join(self.expr(x) for x in (e.argumentos or []))
            return [f"{pad}{e.nombre}({args});"]
        if c == "IncDecStmt":
            return [f"{pad}{e.nombre}{e.operador};"]
        return [f"{pad}// {c} ver InvenioLang"]

    def print_call(self, node) -> str:
        return f"print({self.expr(node)})"

    def for_cabecera(self, n) -> str:
        if n is None:
            return ""
        c = type(n).__name__
        if c == "ForInitVar":
            t = _tipo(n.tipo, self.TIPOS)
            v = f" = {self.expr(n.init_expr)}" if n.init_expr is not None else ""
            return f"{t} {n.nombre}{v}"
        if c == "ForInitAsig":
            return f"{self.lvalue(n.lvalue)} {n.operador} {self.expr(n.expr)}"
        if c == "ForInitIncDec":
            return f"{n.nombre}{n.operador}"
        return ""


class CTranspiler(_CBraceEmitter):
    TIPOS = {"int": "int", "float": "double", "string": "char*", "bool": "bool", "void": "void"}
    CABECERA = ["// InvenioLang -> C (vista)", "#include <stdio.h>", "#include <stdbool.h>"]
    MAIN_HEAD = "int main(){"
    MAIN_TAIL = "return 0; }"

    def print_call(self, node) -> str:
        c = type(node).__name__
        if c == "Literal":
            if node.tipo_literal == "string":
                return f'printf("%s\\n", {self.expr(node)})'
            if node.tipo_literal == "float":
                return f'printf("%g\\n", {self.expr(node)})'
            if node.tipo_literal == "int":
                return f'printf("%d\\n", {self.expr(node)})'
            if node.tipo_literal == "bool":
                return f'printf("%d\\n", {self.expr(node)})'
        return f'printf("%d\\n", {self.expr(node)})  // ajustar formato según tipo'


class JavaTranspiler(_CBraceEmitter):
    TIPOS = {"int": "int", "float": "double", "string": "String", "bool": "boolean", "void": "void"}
    CABECERA = ["// InvenioLang -> Java (vista)", "public class Main {"]
    MAIN_HEAD = "  public static void main(String[] args) {"
    MAIN_TAIL = "  }"
    CLASE_ENV = ["}"]

    def print_call(self, node) -> str:
        return f"System.out.print({self.expr(node)})"


class CSharpTranspiler(_CBraceEmitter):
    TIPOS = {"int": "int", "float": "double", "string": "string", "bool": "bool", "void": "void"}
    CABECERA = ["// InvenioLang -> C# (vista)", "using System; class Program {"]
    MAIN_HEAD = "  static void Main(){"
    MAIN_TAIL = "  }"
    CLASE_ENV = ["}"]

    def print_call(self, node) -> str:
        return f"Console.Write({self.expr(node)})"


class PascalTranspiler(_BaseEmitter):
    TIPOS = {"int": "integer", "float": "real", "string": "string", "bool": "boolean", "void": ""}

    def programa(self, ast) -> str:
        out: list[str] = ["{ InvenioLang -> Pascal (vista) }", "program Main;"]
        for s in list(getattr(ast, "subrutinas", []) or []):
            out.extend(self.func(s))
        out.append("begin")
        if getattr(ast, "main", None) is not None:
            out.extend(self.bloque(ast.main.bloque, 1))
        out.append("end.")
        return "\n".join(out)

    def func(self, s) -> list[str]:
        args = "; ".join(f"{p.nombre}: {_tipo(p.tipo, self.TIPOS)}" for p in (s.parametros or []))
        ret = _tipo(getattr(s, "tipo_retorno", "void"), self.TIPOS)
        head = (
            f"function {s.nombre}({args}): {ret}; begin"
            if ret
            else f"procedure {s.nombre}({args}); begin"
        )
        return [head, *self.bloque(s.bloque, 1), "end;"]

    def bloque(self, b, nv: int) -> list[str]:
        out: list[str] = []
        for e in getattr(b, "elementos", []) or []:
            out.extend(self.stmt(e, nv))
        return out

    def stmt(self, e, nv: int) -> list[str]:
        pad = "  " * nv
        c = type(e).__name__
        if c in ("VarDecl", "ConstDecl"):
            t = _tipo(e.tipo, self.TIPOS)
            v = f" := {self.p_expr(e.init_expr)}" if e.init_expr is not None else ""
            return [f"{pad}{e.nombre}: {t}{v};"]
        if c == "AssignStmt":
            op = ":=" if e.operador == "=" else e.operador
            return [f"{pad}{self.lvalue(e.lvalue)} {op} {self.p_expr(e.expr)};"]
        if c == "PrintStmt":
            return [f"{pad}writeln({self.p_expr(e.expr)});"]
        if c == "IfStmt":
            out = [f"{pad}if {self.p_expr(e.condicion)} then begin"]
            out.extend(self.bloque(e.bloque_then, nv + 1))
            out.append(f"{pad}end")
            if e.bloque_else is not None:
                out.append(f"{pad}else begin")
                out.extend(self.bloque(e.bloque_else, nv + 1))
                out.append(f"{pad}end;")
            return out
        if c == "WhileStmt":
            return [
                f"{pad}while {self.p_expr(e.condicion)} do begin",
                *self.bloque(e.bloque, nv + 1),
                f"{pad}end;",
            ]
        if c == "ForStmt":
            out = [f"{pad}// for desazucarado a while"]
            out.extend(self.p_for_init(e.init_stmt, nv))
            cond = self.p_expr(e.cond_expr) if e.cond_expr is not None else "True"
            out.append(f"{pad}while {cond} do begin")
            out.extend(self.bloque(e.bloque, nv + 1))
            out.extend(self.p_for_act(e.act_stmt, nv + 1))
            out.append(f"{pad}end;")
            return out
        if c == "ReadStmt":
            return [f"{pad}readln({e.nombre});"]
        if c == "IncDecStmt":
            op = " + 1" if e.operador == "++" else " - 1"
            return [f"{pad}{e.nombre} := {e.nombre}{op};"]
        if c == "ReturnStmt":
            return [f"{pad}// return {self.p_expr(e.expr) if e.expr is not None else ''}"]
        if c == "BreakStmt":
            return [f"{pad}Break;"]
        if c == "ContinueStmt":
            return [f"{pad}Continue;"]
        if c == "CallStmt":
            args = ", ".join(self.p_expr(x) for x in (e.argumentos or []))
            return [f"{pad}{e.nombre}({args});"]
        return [f"{pad}// {c}"]

    def p_expr(self, n) -> str:
        c = type(n).__name__
        if c == "Literal" and n.tipo_literal == "bool":
            return "True" if n.valor else "False"
        if c == "BinaryOp" and n.operador in ("&&", "||", "!"):
            mapa = {"&&": "and", "||": "or", "!": "not"}
            return f"({self.p_expr(n.izquierda)} {mapa[str(n.operador)]} {self.p_expr(n.derecha)})"
        return self.expr(n)

    def p_for_init(self, n, nv: int) -> list[str]:
        if n is None:
            return []
        pad = "  " * nv
        c = type(n).__name__
        if c == "ForInitVar":
            t = _tipo(n.tipo, self.TIPOS)
            v = f" := {self.p_expr(n.init_expr)}" if n.init_expr is not None else ""
            return [f"{pad}{n.nombre}: {t}{v};"]
        if c == "ForInitAsig":
            return [f"{pad}{self.lvalue(n.lvalue)} := {self.p_expr(n.expr)};"]
        if c == "ForInitIncDec":
            op = " + 1" if n.operador == "++" else " - 1"
            return [f"{pad}{n.nombre} := {n.nombre}{op};"]
        return []

    def p_for_act(self, n, nv: int) -> list[str]:
        return self.p_for_init(n, nv)


class TranspilerFactory(RegistryFactory):
    """Factory de emisores Rosetta."""

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
    """Vista educativa: InvenioLang -> target. Solo vista, no compila."""
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
