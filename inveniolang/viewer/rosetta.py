# viewer/rosetta.py — Rosetta viewer con fidelidad estructurada (no compiler)
# Solo InvenioLang se ejecuta; el resto es vista educativa read-only.
# Cubre el subconjunto estructurado: variables, constantes, arreglos y
# matrices (declaración, parámetro, acceso y asignación), asignación,
# imprimir/leer, if/while/for, funciones/procedimientos, return/break/
# continue, llamadas y expresiones (binarias, unarias, ternario, literales).
# POO, switch/try/foreach/match y closures se degradan a comentario, nunca a
# crash.
#
# INV-4403: los parámetros arreglo salían sin corchetes (`int arr` en Java,
# C y C#; `arr: integer` en Pascal) y las declaraciones de arreglos/matrices
# y el acceso `m[i][j]` se degradaban a comentario, así que ningún programa
# con arreglos se veía bien. Además los tipos se perdían donde el lenguaje
# destino los necesita: `printf` siempre con `%d`, `7/3` en Python daba
# 2.333 (InvenioLang hace división entera), `&&`/`true` sin traducir a
# Python, `imprimir` añadía un salto de línea en C/Python/Pascal (InvenioLang
# no lo añade), las constantes globales de Java salían como `const` (no es
# Java) y `leer` era un comentario. Ahora cada emisor conoce el tipo (base +
# dimensiones) de cada variable visible y lo usa en firmas, declaraciones,
# lecturas y salidas.
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterator
from typing import Any

from ..patterns import RegistryFactory, Strategy

# Tipo de una variable: (tipo base de InvenioLang, dimensiones 0/1/2).
TipoVar = tuple[str, int]

_RELACIONALES = frozenset({"==", "!=", "<", ">", "<=", ">=", "&&", "||"})
_CONVERSIONES = {
    "int_a_float": "float",
    "float_a_int": "int",
    "int_a_texto": "string",
    "float_a_texto": "string",
    "bool_a_texto": "string",
}


def _tipo(t: Any, mapa: dict) -> str:
    return mapa.get(str(t), str(t))


def _dims_param(p: Any) -> int:
    return 2 if getattr(p, "es_matriz", False) else 1 if getattr(p, "es_arreglo", False) else 0


def _dims_decl(n: Any) -> int:
    return {"ArrayDecl": 1, "MatrixDecl": 2}.get(type(n).__name__, 0)


def _tams(n: Any) -> list[str]:
    return [str(n.filas), str(n.cols)] if _dims_decl(n) == 2 else [str(n.tam)]


def _nodos(raiz: Any) -> Iterator[Any]:
    """Todos los nodos del AST alcanzables desde ``raiz`` (sin repetir)."""
    vistos: set[int] = set()
    pendientes = [raiz]
    while pendientes:
        n = pendientes.pop()
        if isinstance(n, (list, tuple)):
            pendientes.extend(n)
            continue
        if not hasattr(n, "__dict__") or id(n) in vistos:
            continue
        vistos.add(id(n))
        yield n
        pendientes.extend(vars(n).values())


def _asignados(bloque: Any) -> set[str]:
    """Variables simples que un bloque reasigna (para el `global` de Python)."""
    nombres: set[str] = set()
    for n in _nodos(bloque):
        c = type(n).__name__
        if c in ("AssignStmt", "ForInitAsig") and type(n.lvalue).__name__ == "VarLValue":
            nombres.add(str(n.lvalue.nombre))
        elif c in ("IncDecStmt", "ForInitIncDec", "ReadStmt"):
            nombres.add(str(n.nombre))
    return nombres


class _BaseEmitter(Strategy):
    """Emisor estructurado compartido. Cada target define tipos, operadores y E/S."""

    TIPOS: dict = {}
    AND: str = "&&"
    OR: str = "||"
    NOT: str = "!"
    TRUE: str = "true"
    FALSE: str = "false"
    IGUAL: str = "=="
    DISTINTO: str = "!="

    def __init__(self) -> None:
        self.globales: dict[str, TipoVar] = {}
        self.locales: dict[str, TipoVar] = {}
        self.retornos: dict[str, str] = {}
        self.lee = False  # el programa usa leer(): Java necesita un lector
        self.subrutina = ""

    def execute(self, ast: Any, *a, **kw) -> str:
        """Ejecuta la operación."""
        self._preparar(ast)
        return self.programa(ast)

    # ---- tabla de tipos ----
    def _preparar(self, ast: Any) -> None:
        self.globales, self.locales = {}, {}
        self.retornos = {
            s.nombre: str(getattr(s, "tipo_retorno", "void"))
            for s in list(getattr(ast, "subrutinas", []) or [])
        }
        for d in self._globales(ast):
            self._registrar(d, self.globales)
        self.lee = any(type(n).__name__ == "ReadStmt" for n in _nodos(ast))

    @staticmethod
    def _globales(ast: Any) -> list:
        return list(getattr(ast, "declaraciones_globales", []) or []) + list(
            getattr(ast, "declaraciones_posteriores", []) or []
        )

    @staticmethod
    def _registrar(d: Any, tabla: dict[str, TipoVar]) -> None:
        c = type(d).__name__
        if c in ("VarDecl", "ConstDecl", "ArrayDecl", "MatrixDecl", "ForInitVar"):
            tabla[str(d.nombre)] = (str(d.tipo), _dims_decl(d))
        elif c == "Parametro":
            tabla[str(d.nombre)] = (str(d.tipo), _dims_param(d))

    def _entrar(self, s: Any) -> None:
        self.locales = {}
        self.subrutina = str(s.nombre)
        for p in s.parametros or []:
            self._registrar(p, self.locales)

    def tipo_var(self, nombre: Any) -> TipoVar | None:
        """Tipo (base, dimensiones) de una variable visible."""
        n = str(nombre)
        return self.locales.get(n) or self.globales.get(n)

    def tipo_expr(self, n: Any) -> str | None:
        """Tipo base de una expresión, o None si no se puede deducir."""
        c = type(n).__name__
        if c == "Literal":
            return str(n.tipo_literal)
        if c in ("Identifier", "ArrayAccess", "MatrixAccess"):
            t = self.tipo_var(n.nombre)
            return t[0] if t else None
        if c == "FunctionCall":
            return self.retornos.get(n.nombre) or _CONVERSIONES.get(n.nombre)
        if c == "BinaryOp":
            if n.operador in _RELACIONALES:
                return "bool"
            ti, td = self.tipo_expr(n.izquierda), self.tipo_expr(n.derecha)
            if "float" in (ti, td):
                return "float"
            return ti if ti == td else None
        if c == "UnaryOp":
            return "bool" if n.operador == "!" else self.tipo_expr(n.operando)
        if c == "TernaryExpr":
            return self.tipo_expr(n.si_verdadero)
        return None

    def _division_entera(self, n: Any) -> bool:
        return self.tipo_expr(n.izquierda) == "int" and self.tipo_expr(n.derecha) == "int"

    # ---- expresiones ----
    def _str(self, v: Any) -> str:
        s = str(v).replace("\\", "\\\\").replace('"', '\\"')
        s = s.replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
        return '"' + s + '"'

    def operador(self, n: Any) -> str:
        """Operador binario en la sintaxis del destino."""
        return {"&&": self.AND, "||": self.OR, "==": self.IGUAL, "!=": self.DISTINTO}.get(
            str(n.operador), str(n.operador)
        )

    def indexar(self, nombre: Any, indices: list[str]) -> str:
        """``a[i]`` / ``m[i][j]`` (C# usa ``m[i, j]`` para matrices)."""
        return str(nombre) + "".join(f"[{i}]" for i in indices)

    def expr(self, n: Any) -> str:
        """Traduce la expresión."""
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
            return f"({self.expr(n.izquierda)} {self.operador(n)} {self.expr(n.derecha)})"
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
            return self.indexar(n.nombre, [self.expr(n.indice)])
        if c == "MatrixAccess":
            return self.indexar(n.nombre, [self.expr(n.fila), self.expr(n.columna)])
        if c in ("MemberAccess", "MethodCallExpr", "NewExpr", "ThisExpr", "NullExpr"):
            return f"/*{c}-no-soportado*/0"
        return f"/*expr-{c}*/0"

    def lvalue(self, n: Any) -> str:
        """Traduce el destino."""
        c = type(n).__name__
        if c == "VarLValue":
            return str(n.nombre)
        if c == "ArrayLValue":
            return self.indexar(n.nombre, [self.expr(n.indice)])
        if c == "MatrixLValue":
            return self.indexar(n.nombre, [self.expr(n.fila), self.expr(n.columna)])
        return "/*lvalue*/x"

    def texto_salida(self, node: Any) -> str:
        """Expresión a imprimir; un lógico se muestra como InvenioLang: true/false."""
        if self.tipo_expr(node) == "bool":
            return self.bool_a_texto(self.expr(node))
        return self.expr(node)

    def bool_a_texto(self, e: str) -> str:
        """``true``/``false`` en minúsculas, como imprime InvenioLang."""
        return f'({e} ? "true" : "false")'

    def inicial(self, d: Any) -> list:
        """Valores iniciales de un arreglo (lista) o matriz (lista de filas)."""
        if _dims_decl(d) == 2:
            return [[self.expr(x) for x in fila] for fila in d.init_filas]
        return [self.expr(x) for x in d.init_exprs]

    # ---- sentencias (cada target implementa bloque) ----
    def programa(self, ast: Any) -> str:  # pragma: no cover - base
        """Traduce el programa."""
        raise NotImplementedError


class PythonTranspiler(_BaseEmitter):
    """Emisor Python (vista)."""

    TIPOS = {"int": "int", "float": "float", "string": "str", "bool": "bool", "void": "None"}
    AND, OR, NOT, TRUE, FALSE = "and", "or", "not ", "True", "False"
    _DEFECTO = {"int": "0", "float": "0.0", "string": '""', "bool": "False"}

    def programa(self, ast) -> str:
        """Traduce el programa."""
        out: list[str] = ["# InvenioLang -> Python (vista)"]
        for d in self._globales(ast):
            out.append(self.decl(d, 0))
        for s in list(getattr(ast, "subrutinas", []) or []):
            out.extend(self.func(s, 0))
        if getattr(ast, "main", None) is not None:
            out.extend(self.func(ast.main, 0))
            out.append("if __name__ == '__main__':")
            out.append("    main()")
        return "\n".join(out)

    def operador(self, n) -> str:
        """``/`` entre enteros es división entera en InvenioLang: ``//``."""
        if n.operador == "/" and self._division_entera(n):
            return "//"
        return super().operador(n)

    def expr(self, n) -> str:
        """Traduce la expresión (el ternario de Python es ``a if c else b``)."""
        if type(n).__name__ == "TernaryExpr":
            c, a, b = self.expr(n.condicion), self.expr(n.si_verdadero), self.expr(n.si_falso)
            return f"({a} if {c} else {b})"
        return super().expr(n)

    def bool_a_texto(self, e: str) -> str:
        """``true``/``false`` en minúsculas."""
        return f'("true" if {e} else "false")'

    def decl(self, n, nv: int) -> str:
        """Traduce la declaración."""
        c = type(n).__name__
        pad = "    " * nv
        self._registrar(n, self.locales if nv else self.globales)
        defecto = self._DEFECTO.get(str(getattr(n, "tipo", "")), "None")
        if c in ("VarDecl", "ConstDecl"):
            v = self.expr(n.init_expr) if n.init_expr is not None else defecto
            return f"{pad}{n.nombre} = {v}  # {n.tipo}"
        if c == "ArrayDecl":
            ini = self.inicial(n)
            v = f"[{', '.join(ini)}]" if ini else f"[{defecto}] * {n.tam}"
            return f"{pad}{n.nombre} = {v}  # {n.tipo}[{n.tam}]"
        if c == "MatrixDecl":
            filas = self.inicial(n)
            if filas:
                v = "[" + ", ".join("[" + ", ".join(f) + "]" for f in filas) + "]"
            else:
                v = f"[[{defecto}] * {n.cols} for _ in range({n.filas})]"
            return f"{pad}{n.nombre} = {v}  # {n.tipo}[{n.filas}][{n.cols}]"
        return f"{pad}pass  # {c}-no-soportado"

    def func(self, s, nv: int) -> list[str]:
        """Traduce la función (declara `global` lo que reasigna del ámbito global)."""
        self._entrar(s)
        pad = "    " * nv
        args = ", ".join(p.nombre for p in (s.parametros or []))
        head = f"{pad}def {s.nombre}({args}):"
        cuerpo = self.bloque(s.bloque, nv + 1)
        globales = sorted(
            n for n in _asignados(s.bloque) if n in self.globales and n not in self.locales
        )
        if globales:
            cuerpo.insert(0, f"{pad}    global {', '.join(globales)}")
        return [head, *cuerpo]

    def bloque(self, b, nv: int) -> list[str]:
        """Traduce el bloque."""
        pad = "    " * nv
        out: list[str] = []
        for e in getattr(b, "elementos", []) or []:
            out.extend(self.stmt(e, nv))
        return out or [pad + "pass"]

    def stmt(self, e, nv: int) -> list[str]:
        """Traduce la sentencia."""
        pad = "    " * nv
        c = type(e).__name__
        if c in ("VarDecl", "ConstDecl", "ArrayDecl", "MatrixDecl"):
            return [self.decl(e, nv)]
        if c == "AssignStmt":
            op = e.operador
            destino = self.tipo_var(getattr(e.lvalue, "nombre", ""))
            if op == "/=" and destino is not None and destino[0] == "int":
                op = "//="
            return [f"{pad}{self.lvalue(e.lvalue)} {op} {self.expr(e.expr)}"]
        if c == "PrintStmt":
            return [f'{pad}print({self.texto_salida(e.expr)}, end="")']
        if c == "ReadStmt":
            conv = {"int": "int(input())", "float": "float(input())", "bool": 'input() == "true"'}
            t = self.tipo_var(e.nombre)
            return [f"{pad}{e.nombre} = {conv.get(t[0] if t else '', 'input()')}"]
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
            out = list(self.for_init(e.init_stmt, nv))
            cond = self.expr(e.cond_expr) if e.cond_expr is not None else "True"
            out.append(f"{pad}while {cond}:")
            out.extend(self.bloque(e.bloque, nv + 1))
            out.extend(self.for_init(e.act_stmt, nv + 1))
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
        """Traduce el inicio (o la acción) del for."""
        if n is None:
            return []
        pad = "    " * nv
        c = type(n).__name__
        if c == "ForInitVar":
            self._registrar(n, self.locales)
            v = f" = {self.expr(n.init_expr)}" if n.init_expr is not None else ""
            return [f"{pad}{n.nombre}{v}"]
        if c == "ForInitAsig":
            return [f"{pad}{self.lvalue(n.lvalue)} {n.operador} {self.expr(n.expr)}"]
        if c == "ForInitIncDec":
            op = "+= 1" if n.operador == "++" else "-= 1"
            return [f"{pad}{n.nombre} {op}"]
        return []


class _CBraceEmitter(_BaseEmitter):
    TIPOS = {"int": "int", "float": "double", "string": "String", "bool": "boolean", "void": "void"}
    CABECERA: list[str] = []
    MAIN_HEAD: str = ""
    MAIN_TAIL: str = ""
    CLASE_ENV: list[str] = []
    # Prefijo de las declaraciones globales (Java/C#: miembros `static` de la clase).
    GLOBAL: str = ""

    def programa(self, ast) -> str:
        """Traduce el programa."""
        out: list[str] = list(self.cabecera())
        for d in self._globales(ast):
            out.append(self.decl(d, 0, global_=True))
        for s in list(getattr(ast, "subrutinas", []) or []):
            out.extend(self.func(s, 0))
        if getattr(ast, "main", None) is not None:
            self._entrar(ast.main)
            out.append(self.MAIN_HEAD)
            out.extend(self.bloque(ast.main.bloque, 1))
            out.append(self.MAIN_TAIL)
        out.extend(self.CLASE_ENV)
        return "\n".join(out)

    def cabecera(self) -> list[str]:
        """Líneas iniciales (includes, clase envolvente, lector de entrada)."""
        return list(self.CABECERA)

    # -- tipos --
    def tipo_arreglo(self, base: str, dims: int) -> str:
        """Tipo arreglo/matriz del destino (Java: ``int[]``, ``double[][]``)."""
        return _tipo(base, self.TIPOS) + "[]" * dims

    def param(self, p) -> str:
        """Parámetro con su tipo; los arreglos y matrices llevan sus corchetes."""
        return f"{self.tipo_arreglo(str(p.tipo), _dims_param(p))} {p.nombre}"

    def nuevo(self, base: str, tams: list[str]) -> str:
        """Creación de un arreglo vacío: ``new int[3]`` / ``new double[2][2]``."""
        return f"new {_tipo(base, self.TIPOS)}" + "".join(f"[{t}]" for t in tams)

    def literal_arreglo(self, valores: list) -> str:
        """Inicializador ``{1, 2}`` o ``{{1, 2}, {3, 4}}``."""
        partes = [self.literal_arreglo(v) if isinstance(v, list) else str(v) for v in valores]
        return "{" + ", ".join(partes) + "}"

    def constante(self, global_: bool) -> str:
        """Modificador de una constante escalar (Java: ``final``)."""
        return "static final " if global_ else "final "

    def decl(self, n, nv: int, global_: bool = False) -> str:
        """Traduce la declaración."""
        pad = "    " * nv
        c = type(n).__name__
        self._registrar(n, self.globales if global_ else self.locales)
        estatico = self.GLOBAL if global_ else ""
        if c in ("VarDecl", "ConstDecl"):
            t = _tipo(n.tipo, self.TIPOS)
            v = f" = {self.expr(n.init_expr)}" if n.init_expr is not None else ""
            mod = self.constante(global_) if c == "ConstDecl" else estatico
            return f"{pad}{mod}{t} {n.nombre}{v};"
        if c in ("ArrayDecl", "MatrixDecl"):
            return pad + self.decl_arreglo(n, estatico)
        return f"{pad}// {c} no soportado en vista"

    def decl_arreglo(self, n, estatico: str) -> str:
        """``int[] a = {1, 2};`` / ``double[][] m = new double[2][2];`` (Java)."""
        ini = self.inicial(n)
        valor = self.literal_arreglo(ini) if ini else self.nuevo(str(n.tipo), _tams(n))
        final = "final " if getattr(n, "es_constante", False) else ""
        tipo = self.tipo_arreglo(str(n.tipo), _dims_decl(n))
        return f"{estatico}{final}{tipo} {n.nombre} = {valor};"

    def func(self, s, nv: int) -> list[str]:
        """Traduce la función."""
        self._entrar(s)
        pad = "    " * nv
        ret = _tipo(getattr(s, "tipo_retorno", "void"), self.TIPOS)
        args = ", ".join(self.param(p) for p in (s.parametros or []))
        head = f"{pad}static {ret} {s.nombre}({args}) {{"
        return [head, *self.bloque(s.bloque, nv + 1), f"{pad}}}"]

    def bloque(self, b, nv: int) -> list[str]:
        """Traduce el bloque."""
        out: list[str] = []
        for e in getattr(b, "elementos", []) or []:
            out.extend(self.stmt(e, nv))
        return out

    def stmt(self, e, nv: int) -> list[str]:
        """Traduce la sentencia."""
        pad = "    " * nv
        c = type(e).__name__
        if c in ("VarDecl", "ConstDecl", "ArrayDecl", "MatrixDecl"):
            return [self.decl(e, nv)]
        if c == "AssignStmt":
            return [f"{pad}{self.lvalue(e.lvalue)} {e.operador} {self.expr(e.expr)};"]
        if c == "PrintStmt":
            return [f"{pad}{self.print_call(e.expr)};"]
        if c == "ReadStmt":
            return [f"{pad}{self.leer(e.nombre)};"]
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

    @abstractmethod
    def print_call(self, node) -> str:
        """Llamada de impresión del target."""

    @abstractmethod
    def leer(self, nombre) -> str:
        """Lectura de una variable según su tipo."""

    def for_cabecera(self, n) -> str:
        """Cabecera del for en C."""
        if n is None:
            return ""
        c = type(n).__name__
        if c == "ForInitVar":
            self._registrar(n, self.locales)
            t = _tipo(n.tipo, self.TIPOS)
            v = f" = {self.expr(n.init_expr)}" if n.init_expr is not None else ""
            return f"{t} {n.nombre}{v}"
        if c == "ForInitAsig":
            return f"{self.lvalue(n.lvalue)} {n.operador} {self.expr(n.expr)}"
        if c == "ForInitIncDec":
            return f"{n.nombre}{n.operador}"
        return ""


class CTranspiler(_CBraceEmitter):
    """Emisor C (vista; el mismo texto compila también como C++)."""

    TIPOS = {
        "int": "int",
        "float": "double",
        "string": "const char*",
        "bool": "bool",
        "void": "void",
    }
    CABECERA = ["// InvenioLang -> C (vista)", "#include <stdio.h>", "#include <stdbool.h>"]
    MAIN_HEAD = "int main(void) {"
    MAIN_TAIL = "    return 0;\n}"
    _FORMATOS = {"int": "%d", "float": "%g", "string": "%s", "bool": "%s"}
    _LECTURA = {"int": "%d", "float": "%lf"}

    def __init__(self) -> None:
        super().__init__()
        self.columnas: dict[str, str] = {}

    def _preparar(self, ast: Any) -> None:
        super()._preparar(ast)
        # C exige el número de columnas de un parámetro matriz (`double m[][C]`):
        # se toma de las matrices que declara el programa si todas coinciden.
        cols: dict[str, set[str]] = {}
        for n in _nodos(ast):
            if type(n).__name__ == "MatrixDecl":
                cols.setdefault(str(n.tipo), set()).add(str(n.cols))
        self.columnas = {t: next(iter(c)) for t, c in cols.items() if len(c) == 1}

    def constante(self, global_: bool) -> str:
        """``const`` (en C es un calificador, no una constante de compilación)."""
        return "const "

    def decl(self, n, nv: int, global_: bool = False) -> str:
        """Constante entera global como ``#define``: C la necesita para tamaños."""
        if global_ and type(n).__name__ == "ConstDecl" and str(n.tipo) == "int":
            self._registrar(n, self.globales)
            return f"#define {n.nombre} {self.expr(n.init_expr)}"
        return super().decl(n, nv, global_)

    def decl_arreglo(self, n, estatico: str) -> str:
        """``int a[3] = {1, 2, 3};`` / ``double m[2][2];``."""
        ini = self.inicial(n)
        valor = f" = {self.literal_arreglo(ini)}" if ini else ""
        const = "const " if getattr(n, "es_constante", False) else ""
        corchetes = "".join(f"[{t}]" for t in _tams(n))
        return f"{const}{_tipo(n.tipo, self.TIPOS)} {n.nombre}{corchetes}{valor};"

    def param(self, p) -> str:
        """``int arr[]``; una matriz necesita sus columnas: ``double m[][C]``."""
        dims = _dims_param(p)
        t = _tipo(p.tipo, self.TIPOS)
        if dims == 1:
            return f"{t} {p.nombre}[]"
        if dims == 2:
            cols = self.columnas.get(str(p.tipo), "/* columnas */")
            return f"{t} {p.nombre}[][{cols}]"
        return f"{t} {p.nombre}"

    def print_call(self, node) -> str:
        """``printf`` con el formato del tipo de la expresión."""
        fmt = self._FORMATOS.get(self.tipo_expr(node) or "")
        if fmt is None:
            return f'printf("%d", {self.expr(node)})  // ajustar formato según tipo'
        return f'printf("{fmt}", {self.texto_salida(node)})'

    def leer(self, nombre) -> str:
        """``scanf`` con el formato del tipo."""
        t = self.tipo_var(nombre)
        fmt = self._LECTURA.get(t[0] if t else "")
        if fmt is None:
            return f"// leer {nombre}: en C, texto y lógicos se leen con fgets"
        return f'scanf("{fmt}", &{nombre})'


class JavaTranspiler(_CBraceEmitter):
    """Emisor Java (vista)."""

    TIPOS = {"int": "int", "float": "double", "string": "String", "bool": "boolean", "void": "void"}
    CABECERA = ["// InvenioLang -> Java (vista)", "public class Main {"]
    MAIN_HEAD = "  public static void main(String[] args) {"
    MAIN_TAIL = "  }"
    CLASE_ENV = ["}"]
    GLOBAL = "static "

    def cabecera(self) -> list[str]:
        """Clase envolvente y, si el programa lee, un único ``Scanner``."""
        out = list(self.CABECERA)
        if self.lee:
            out.append("  static java.util.Scanner entrada = new java.util.Scanner(System.in);")
        return out

    def texto_salida(self, node) -> str:
        """Java ya imprime ``true``/``false`` en minúsculas."""
        return self.expr(node)

    def print_call(self, node) -> str:
        """Llamada de impresión del target."""
        return f"System.out.print({self.texto_salida(node)})"

    def leer(self, nombre) -> str:
        """Lectura con el ``Scanner`` según el tipo."""
        t = self.tipo_var(nombre)
        metodo = {"int": "nextInt()", "float": "nextDouble()", "bool": "nextBoolean()"}
        return f"{nombre} = entrada.{metodo.get(t[0] if t else '', 'next()')}"


class CSharpTranspiler(_CBraceEmitter):
    """Emisor C# (vista)."""

    TIPOS = {"int": "int", "float": "double", "string": "string", "bool": "bool", "void": "void"}
    CABECERA = ["// InvenioLang -> C# (vista)", "using System; class Program {"]
    MAIN_HEAD = "  static void Main(){"
    MAIN_TAIL = "  }"
    CLASE_ENV = ["}"]
    GLOBAL = "static "

    def tipo_arreglo(self, base: str, dims: int) -> str:
        """C# usa matrices rectangulares: ``double[,]``."""
        return _tipo(base, self.TIPOS) + {0: "", 1: "[]", 2: "[,]"}[dims]

    def nuevo(self, base: str, tams: list[str]) -> str:
        """``new double[2, 2]``."""
        return f"new {_tipo(base, self.TIPOS)}[{', '.join(tams)}]"

    def indexar(self, nombre: Any, indices: list[str]) -> str:
        """``m[i, j]`` en una matriz rectangular."""
        return f"{nombre}[{', '.join(indices)}]"

    def constante(self, global_: bool) -> str:
        """``const`` (implícitamente estática dentro de la clase)."""
        return "const "

    def decl_arreglo(self, n, estatico: str) -> str:
        """Un arreglo constante es ``static readonly`` (``const`` no admite arreglos)."""
        if getattr(n, "es_constante", False) and estatico:
            estatico = "static readonly "
        ini = self.inicial(n)
        valor = self.literal_arreglo(ini) if ini else self.nuevo(str(n.tipo), _tams(n))
        return f"{estatico}{self.tipo_arreglo(str(n.tipo), _dims_decl(n))} {n.nombre} = {valor};"

    def print_call(self, node) -> str:
        """Llamada de impresión del target."""
        return f"Console.Write({self.texto_salida(node)})"

    def leer(self, nombre) -> str:
        """Lectura de una línea convertida al tipo."""
        t = self.tipo_var(nombre)
        conv = {"int": "int.Parse", "float": "double.Parse", "bool": "bool.Parse"}
        f = conv.get(t[0] if t else "")
        return f"{nombre} = {f}(Console.ReadLine())" if f else f"{nombre} = Console.ReadLine()"


class PascalTranspiler(_BaseEmitter):
    """Emisor Pascal (vista, dialecto Free Pascal/Delphi)."""

    TIPOS = {"int": "integer", "float": "real", "string": "string", "bool": "boolean", "void": ""}
    AND, OR, NOT, TRUE, FALSE, IGUAL, DISTINTO = "and", "or", "not ", "True", "False", "=", "<>"

    def programa(self, ast) -> str:
        """Traduce el programa."""
        out: list[str] = ["{ InvenioLang -> Pascal (vista) }", "program Main;"]
        matrices = sorted(
            {
                str(p.tipo)
                for s in (getattr(ast, "subrutinas", []) or [])
                for p in (s.parametros or [])
                if _dims_param(p) == 2
            }
        )
        if matrices:
            out.append("type")
            for t in matrices:
                out.append(f"  {self._tipo_matriz(t)} = array of array of {_tipo(t, self.TIPOS)};")
        for d in self._globales(ast):
            out.append(self.decl_global(d))
        for s in list(getattr(ast, "subrutinas", []) or []):
            out.extend(self.func(s))
        out.append("begin")
        if getattr(ast, "main", None) is not None:
            self._entrar(ast.main)
            out.extend(self.bloque(ast.main.bloque, 1))
        out.append("end.")
        return "\n".join(out)

    def _tipo_matriz(self, base: str) -> str:
        return "TMatriz" + _tipo(base, self.TIPOS).capitalize()

    def _tipo_decl(self, n) -> str:
        t = _tipo(n.tipo, self.TIPOS)
        if _dims_decl(n) == 1:
            return f"array[0..{n.tam} - 1] of {t}"
        if _dims_decl(n) == 2:
            return f"array[0..{n.filas} - 1, 0..{n.cols} - 1] of {t}"
        return t

    def _valor_inicial(self, d) -> str:
        """Valor inicial: expresión, ``(1, 2)`` o ``((1, 2), (3, 4))``; "" si no hay."""
        if _dims_decl(d):
            ini = self.inicial(d)
            if not ini:
                return ""
            filas = [f"({', '.join(f)})" if isinstance(f, list) else str(f) for f in ini]
            return f"({', '.join(filas)})"
        expr = getattr(d, "init_expr", None)
        return self.expr(expr) if expr is not None else ""

    def decl_global(self, d) -> str:
        """``const N = 3;`` / ``var x: integer;`` en la cabecera del programa."""
        self._registrar(d, self.globales)
        c = type(d).__name__
        if c == "ConstDecl":
            return f"const {d.nombre} = {self.expr(d.init_expr)};"
        if c in ("VarDecl", "ArrayDecl", "MatrixDecl"):
            v = self._valor_inicial(d)
            return f"var {d.nombre}: {self._tipo_decl(d)}{' = ' + v if v else ''};"
        return f"{{ {c} no soportado en vista }}"

    def param(self, p) -> str:
        """``var arr: array of integer``; una matriz usa un tipo con nombre."""
        dims = _dims_param(p)
        if dims == 2:
            return f"var {p.nombre}: {self._tipo_matriz(str(p.tipo))}"
        if dims == 1:
            return f"var {p.nombre}: array of {_tipo(p.tipo, self.TIPOS)}"
        return f"{p.nombre}: {_tipo(p.tipo, self.TIPOS)}"

    def func(self, s) -> list[str]:
        """Traduce la función."""
        self._entrar(s)
        args = "; ".join(self.param(p) for p in (s.parametros or []))
        ret = _tipo(getattr(s, "tipo_retorno", "void"), self.TIPOS)
        head = (
            f"function {s.nombre}({args}): {ret}; begin"
            if ret
            else f"procedure {s.nombre}({args}); begin"
        )
        return [head, *self.bloque(s.bloque, 1), "end;"]

    def bloque(self, b, nv: int) -> list[str]:
        """Traduce el bloque."""
        out: list[str] = []
        for e in getattr(b, "elementos", []) or []:
            out.extend(self.stmt(e, nv))
        return out

    def stmt(self, e, nv: int) -> list[str]:
        """Traduce la sentencia."""
        pad = "  " * nv
        c = type(e).__name__
        if c in ("VarDecl", "ConstDecl", "ArrayDecl", "MatrixDecl"):
            self._registrar(e, self.locales)
            v = self._valor_inicial(e)
            return [f"{pad}{e.nombre}: {self._tipo_decl(e)}{' := ' + v if v else ''};"]
        if c == "AssignStmt":
            op = ":=" if e.operador == "=" else e.operador
            return [f"{pad}{self.lvalue(e.lvalue)} {op} {self.expr(e.expr)};"]
        if c == "PrintStmt":
            return [f"{pad}write({self.texto_salida(e.expr)});"]
        if c == "IfStmt":
            out = [f"{pad}if {self.expr(e.condicion)} then begin"]
            out.extend(self.bloque(e.bloque_then, nv + 1))
            out.append(f"{pad}end")
            if e.bloque_else is not None:
                out.append(f"{pad}else begin")
                out.extend(self.bloque(e.bloque_else, nv + 1))
                out.append(f"{pad}end;")
            return out
        if c == "WhileStmt":
            return [
                f"{pad}while {self.expr(e.condicion)} do begin",
                *self.bloque(e.bloque, nv + 1),
                f"{pad}end;",
            ]
        if c == "ForStmt":
            out = [f"{pad}// for desazucarado a while"]
            out.extend(self.p_for_init(e.init_stmt, nv))
            cond = self.expr(e.cond_expr) if e.cond_expr is not None else "True"
            out.append(f"{pad}while {cond} do begin")
            out.extend(self.bloque(e.bloque, nv + 1))
            out.extend(self.p_for_init(e.act_stmt, nv + 1))
            out.append(f"{pad}end;")
            return out
        if c == "ReadStmt":
            return [f"{pad}readln({e.nombre});"]
        if c == "IncDecStmt":
            op = " + 1" if e.operador == "++" else " - 1"
            return [f"{pad}{e.nombre} := {e.nombre}{op};"]
        if c == "ReturnStmt":
            # Free Pascal/Delphi: Exit(valor) asigna el resultado y sale.
            return [f"{pad}Exit({self.expr(e.expr)});" if e.expr is not None else f"{pad}Exit;"]
        if c == "BreakStmt":
            return [f"{pad}Break;"]
        if c == "ContinueStmt":
            return [f"{pad}Continue;"]
        if c == "CallStmt":
            args = ", ".join(self.expr(x) for x in (e.argumentos or []))
            return [f"{pad}{e.nombre}({args});"]
        return [f"{pad}// {c}"]

    def operador(self, n) -> str:
        """``div``/``mod`` entre enteros; ``/`` real."""
        if n.operador == "/" and self._division_entera(n):
            return "div"
        if n.operador == "%":
            return "mod"
        return super().operador(n)

    def bool_a_texto(self, e: str) -> str:
        """``true``/``false`` en minúsculas (unidad SysUtils)."""
        return f"LowerCase(BoolToStr({e}, True))"

    def p_for_init(self, n, nv: int) -> list[str]:
        """Traduce el inicio (o la acción) del for en Pascal."""
        if n is None:
            return []
        pad = "  " * nv
        c = type(n).__name__
        if c == "ForInitVar":
            self._registrar(n, self.locales)
            t = _tipo(n.tipo, self.TIPOS)
            v = f" := {self.expr(n.init_expr)}" if n.init_expr is not None else ""
            return [f"{pad}{n.nombre}: {t}{v};"]
        if c == "ForInitAsig":
            return [f"{pad}{self.lvalue(n.lvalue)} := {self.expr(n.expr)};"]
        if c == "ForInitIncDec":
            op = " + 1" if n.operador == "++" else " - 1"
            return [f"{pad}{n.nombre} := {n.nombre}{op};"]
        return []


class TranspilerFactory(RegistryFactory):
    """Factory de emisores Rosetta."""

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
    """Vista educativa: InvenioLang -> target. Solo vista, no compila."""
    from ..core import analizar_fuente

    # INV-1022: el análisis pasa por la fachada única del núcleo.
    analisis = analizar_fuente(codigo, "<transpile>", hasta="parser")
    if not analisis.ok:
        return "\n".join(analisis.errores.obtener_reportes())
    return TranspilerFactory.get().transpile(target.lower(), analisis.ast)
